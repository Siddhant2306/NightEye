"""Causal feature groups; no new row dropping, cross ranks exclude held-out peers."""
from pathlib import Path
import numpy as np
import pandas as pd
from src.XGBoost.context_features import lagged_join
from src.context_sources import SECTOR_FOR
from src.fetch_research_data import NEW_HOLDOUTS

GROUPS={"F1":"momentum","F2":"risk","F3":"technical","F4":"volume",
        "F5":"context","F6":"regime","F7":"cross_section"}


def stock_features(history):
    h=history.sort_index()
    c,v=h.close,h.volume
    r=np.log(c).diff()
    out=pd.DataFrame(index=h.index)
    groups={name:[] for name in list(GROUPS.values())+["calendar"]}
    registry={}
    def add(group,name,value,source,lookback,formula):
        name="v2_"+name
        out[name]=value
        groups[group].append(name)
        registry[name]=dict(group=group,source=source,lookback=lookback,formula=formula,
            availability="After origin session closes; current/past values only",
            missing="NaN on insufficient history/invalid denominator; native tree handling or training-only LSTM imputation")
    for w in [1,2,3,5,10,21,63,126,252]:
        add("momentum",f"momentum_{w}",np.log(c/c.shift(w)),"adjusted close",w,"log(close/lagged close)")
    add("momentum","acceleration_21",np.log(c/c.shift(21))-np.log(c.shift(21)/c.shift(42)),"close",42,"current minus previous 21-session log return")
    for w in [5,10,20,50,100,200]:
        ma=c.rolling(w).mean()
        add("momentum",f"ma_distance_{w}",c/ma-1,"close",w,"close/SMA-1")
        if w in [20,50,200]: add("momentum",f"ma_slope_{w}",ma/ma.shift(5)-1,"close",w+5,"SMA/SMA[5 sessions ago]-1")
    for fast,slow in [(5,20),(20,50)]:
        add("momentum",f"ma_cross_{fast}_{slow}",c.rolling(fast).mean()/c.rolling(slow).mean()-1,"close",slow,"fast SMA / slow SMA - 1")
    high252=c.rolling(252).max()
    drawdown=c/high252-1
    add("momentum","distance_high_252",drawdown,"close",252,"close/rolling max-1")
    add("momentum","distance_low_252",c/c.rolling(252).min()-1,"close",252,"close/rolling min-1")
    add("momentum","max_drawdown_63",drawdown.rolling(63).min(),"close",314,"minimum trailing-high drawdown in last 63 sessions")
    add("momentum","recovery_21",drawdown-drawdown.rolling(21).min(),"close",272,"current drawdown minus worst recent drawdown")
    for w in [5,10,21,63,126]:
        add("risk",f"std_{w}",r.rolling(w).std(),"close",w+1,"sample std of daily log return")
    add("risk","ewm_std_21",r.ewm(span=21,min_periods=21,adjust=False).std(),"close",22,"exponentially weighted daily log-return std")
    valid=(h.high>=h.low)&(h.low>0)
    tr=pd.concat([h.high-h.low,(h.high-c.shift()).abs(),(h.low-c.shift()).abs()],axis=1).max(axis=1).where(valid)
    add("risk","atr_pct_14",tr.rolling(14).mean()/c,"OHLC",15,"14-session mean true range / close")
    add("risk","high_low_range",((h.high-h.low)/c).where(valid),"OHLC",1,"(high-low)/close")
    add("risk","gap",np.log(h.open/c.shift()),"open,close",2,"log(open / previous close)")
    add("risk","intraday",np.log(c/h.open),"open,close",1,"log(close/open)")
    parkinson=np.sqrt((np.log(h.high/h.low).where(valid)**2).rolling(21).mean()/(4*np.log(2)))
    add("risk","parkinson_21",parkinson,"high,low",21,"sqrt(mean(log(high/low)^2)/(4 log 2)); invalid OHLC -> NaN")
    for side,part in [("upside",r.clip(lower=0)),("downside",r.clip(upper=0))]:
        add("risk",f"{side}_std_21",part.rolling(21).std(),"close",22,"std of returns clipped at zero")
    add("risk","downside_deviation_21",np.sqrt((r.clip(upper=0)**2).rolling(21).mean()),"close",22,"sqrt(mean(min(log return,0)^2))")
    add("risk","skew_63",r.rolling(63).skew(),"close",64,"sample skew, at least 63 returns")
    add("risk","kurtosis_63",r.rolling(63).kurt(),"close",64,"sample excess kurtosis, at least 63 returns")
    add("risk","vol_expansion",r.rolling(5).std()/r.rolling(63).std().replace(0,np.nan),"close",64,"5-session / 63-session volatility")
    change=c.diff()
    for w in [14,21]:
        gain=change.clip(lower=0).ewm(alpha=1/w,adjust=False,min_periods=w).mean()
        loss=(-change.clip(upper=0)).ewm(alpha=1/w,adjust=False,min_periods=w).mean()
        value=gain/(gain+loss).replace(0,np.nan)
        add("technical",f"rsi_{w}",value,"close",w+1,"Wilder-smoothed gains/(gains+losses), 0..1")
    macd=c.ewm(span=12,adjust=False).mean()-c.ewm(span=26,adjust=False).mean()
    add("technical","macd_histogram",(macd-macd.ewm(span=9,adjust=False).mean())/c,"close",35,"(MACD - signal)/close")
    low,high=h.low.rolling(14).min(),h.high.rolling(14).max()
    add("technical","stochastic_14",(c-low)/(high-low).replace(0,np.nan),"high,low,close",14,"(close-14-session low)/(high-low)")
    mean,sd=c.rolling(20).mean(),c.rolling(20).std()
    add("technical","bollinger_z",(c-mean)/sd.replace(0,np.nan),"close",20,"(close-SMA20)/std20")
    add("technical","bollinger_width",4*sd/mean,"close",20,"four standard deviations / SMA20")
    up,down=h.high.diff(),-h.low.diff()
    plus=up.where((up>down)&(up>0),0).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    minus=down.where((down>up)&(down>0),0).ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    dx=(plus-minus).abs()/(plus+minus).replace(0,np.nan)
    add("technical","adx_14",dx.ewm(alpha=1/14,adjust=False,min_periods=14).mean(),"high,low",28,"Wilder average abs(+DM - -DM)/(+DM + -DM), normalized 0..1")
    meanv,sdv=v.rolling(21).mean(),v.rolling(21).std()
    add("volume","volume_log_change",np.log1p(v).diff(),"volume",2,"log(1+volume) change; not a price return")
    add("volume","relative_volume_21",v/meanv.replace(0,np.nan)-1,"volume",21,"volume/rolling average-1")
    add("volume","volume_z_63",(v-v.rolling(63).mean())/v.rolling(63).std().replace(0,np.nan),"volume",63,"volume z-score")
    add("volume","pvt_21",(r*v).rolling(21).sum()/v.rolling(21).sum().replace(0,np.nan),"close,volume",22,"volume-weighted daily log returns over 21 sessions")
    signed=np.sign(r)*v
    add("volume","obv_pressure_21",signed.rolling(21).sum()/v.rolling(21).sum().replace(0,np.nan),"close,volume",22,"rolling signed volume / total volume; normalized OBV slope")
    for side,mask in [("positive",r>0),("negative",r<0)]:
        add("volume",f"{side}_volume_share_21",v.where(mask,0).rolling(21).sum()/v.rolling(21).sum().replace(0,np.nan),"close,volume",22,"volume share in positive/negative sessions")
    add("volume","volume_volatility_expansion",(v/meanv.replace(0,np.nan))/(r.rolling(5).std()/r.rolling(63).std().replace(0,np.nan)).replace(0,np.nan),"close,volume",64,"relative volume divided by short/long volatility ratio; not full liquidity")
    add("calendar","weekday_sin",np.sin(2*np.pi*h.index.day_of_week/5),"session date",0,"sin(weekday*2pi/5)")
    add("calendar","weekday_cos",np.cos(2*np.pi*h.index.day_of_week/5),"session date",0,"cos(weekday*2pi/5)")
    add("calendar","month_sin",np.sin(2*np.pi*h.index.month/12),"session date",0,"sin(month*2pi/12)")
    add("calendar","month_cos",np.cos(2*np.pi*h.index.month/12),"session date",0,"cos(month*2pi/12)")
    add("calendar","quarter_sin",np.sin(2*np.pi*h.index.quarter/4),"session date",0,"cyclical quarter")
    add("calendar","month_end",h.index.is_month_end.astype(float),"session date",0,"calendar month end, not future last trading day")
    add("calendar","financial_year_end",((h.index.month==3)&(h.index.day>=25)).astype(float),"session date",0,"last calendar week of Indian financial year")
    return out.replace([np.inf,-np.inf],np.nan),groups,registry


def context_features(frame,history,context,ticker):
    out=pd.DataFrame(index=frame.index)
    groups={"context":[],"regime":[]}
    registry={}
    def add(group,name,value,source,lookback,formula):
        name="v2_"+name;out[name]=value;groups[group].append(name)
        registry[name]=dict(group=group,source=source,lookback=lookback,formula=formula,
            availability="Index observations eligible next calendar day; backward as-of; never future joined",
            missing="NaN on insufficient history, zero variance or stale data")
    for key,prefix in [("market","market"),(SECTOR_FOR[ticker],"sector")]:
        source=pd.read_csv(Path(context)/"indices"/f"{key}_prices.csv",parse_dates=["Date"]).set_index("Date").sort_index()
        signal=pd.DataFrame(index=source.index)
        signal["drawdown"]=source.close/source.close.rolling(252).max()-1
        signal["trend"]=source.close/source.close.rolling(50).mean()-1
        signal["return126"]=np.log(source.close/source.close.shift(126))
        lagged=lagged_join(frame.index,signal.reset_index())
        add("context",f"{prefix}_drawdown",lagged.drawdown,f"{prefix} index close",252,"close / past rolling high-1")
        add("context",f"{prefix}_trend",lagged.trend,f"{prefix} index close",50,"index close / SMA50-1")
        if prefix=="market": market126=lagged.return126
    stock=np.log(history.close).diff().shift(1).reindex(frame.index)
    for name,other in [("market",frame.market_return_1),("sector",None)]:
        if other is None:
            source=pd.read_csv(Path(context)/"indices"/f"{SECTOR_FOR[ticker]}_prices.csv",parse_dates=["Date"]).set_index("Date").sort_index()
            source["daily"]=np.log(source.close).diff()
            other=lagged_join(frame.index,source[["daily"]].reset_index()).daily
        add("context",f"{name}_correlation_63",stock.rolling(63).corr(other),"previous-session stock/index log return",63,"rolling Pearson correlation")
        if name=="market": add("context","market_beta_63",stock.rolling(63).cov(other)/other.rolling(63).var().replace(0,np.nan),"previous-session stock/market returns",63,"rolling covariance / market variance")
    add("context","relative_market_126",np.log(history.close/history.close.shift(126)).shift(1).reindex(frame.index)-market126,"previous-session stock and market returns",126,"stock 126-session log return minus market 126-session log return, both lagged")
    # Fixed thresholds are declared before validation, never quantiles fitted on future data.
    vol=frame.market_std_21
    add("regime","market_vol_state",pd.Series(np.select([vol<.008,vol>.016],[0.,2.],default=1.),index=frame.index).where(vol.notna()),"lagged market volatility",21,"fixed daily volatility bins: <0.8%, 0.8..1.6%, >1.6%")
    trend=out.v2_market_trend
    add("regime","market_trend_state",pd.Series(np.select([trend<-.03,trend>.03],[-1.,1.],default=0.),index=frame.index).where(trend.notna()),"lagged market trend",50,"fixed SMA50 distance bins: below -3%, within +/-3%, above +3%")
    add("regime","market_vol_expansion",frame.market_std_21/frame.market_std_63.replace(0,np.nan),"lagged market std",63,"short / long market volatility")
    add("regime","deep_market_drawdown",(out.v2_market_drawdown<-.15).astype(float).where(out.v2_market_drawdown.notna()),"lagged market drawdown",252,"drawdown below -15%, fixed threshold")
    add("regime","sector_trend_state",np.sign(out.v2_sector_trend),"lagged sector trend",50,"sign of sector SMA50 distance")
    return out.replace([np.inf,-np.inf],np.nan),groups,registry


def cross_features(panel,holdouts=NEW_HOLDOUTS):
    """Rank against observed training-company peers only, separately at each date."""
    out=pd.DataFrame(index=panel.index)
    definitions={"v2_momentum_rank":"v2_momentum_21","v2_volatility_rank":"v2_std_21",
                 "v2_volume_rank":"v2_relative_volume_21","v2_return_percentile":"v2_momentum_1"}
    arrays={name:np.full(len(panel),np.nan) for name in list(definitions)+["v2_sector_momentum_rank"]}
    tickers=panel.ticker.to_numpy()
    sectors=np.array([SECTOR_FOR[t] for t in tickers])
    reference=~panel.ticker.isin(holdouts).to_numpy()
    raw={column:panel[column].to_numpy() for column in definitions.values()}
    for positions in panel.groupby(level=0,sort=False).indices.values():
        positions=np.asarray(positions)
        for name,column in definitions.items():
            values=raw[column][positions]
            ref=values[reference[positions]&np.isfinite(values)]
            if len(ref)<5: continue
            ref=np.sort(ref);valid=np.isfinite(values)
            arrays[name][positions[valid]]=(np.searchsorted(ref,values[valid],side="left")+np.searchsorted(ref,values[valid],side="right"))/(2*len(ref))
        for sector in np.unique(sectors[positions]):
            mask=sectors[positions]==sector
            selected=positions[mask];values=raw["v2_momentum_21"][selected]
            ref=np.sort(values[reference[selected]&np.isfinite(values)])
            if len(ref)<2: continue
            valid=np.isfinite(values)
            arrays["v2_sector_momentum_rank"][selected[valid]]=(np.searchsorted(ref,values[valid],side="left")+np.searchsorted(ref,values[valid],side="right"))/(2*len(ref))
    for name,values in arrays.items(): out[name]=values
    registry={name:dict(group="cross_section",source="contemporaneous observable training-company OHLCV; held-out peers excluded",lookback=2 if name=="v2_return_percentile" else 22,
        availability="After all reference-peer closes at origin; current date only, no labels",formula="midrank percentile against finite eligible peers; sector version within static sector",
        missing="NaN if fewer than five market peers or two sector peers; never backfill absent peers") for name in arrays}
    return out,registry


ALIASES={**{f"v2_momentum_{w}":[f"tech_momentum_{w}",f"return_{w}"] for w in [1,5,21,63]},
    **{f"v2_ma_distance_{w}":[f"tech_ma_distance_{w}"] for w in [10,20]},
    **{f"v2_std_{w}":[f"tech_volatility_{w}",f"std_{w}"] for w in [5,10,21,63]},
    "v2_rsi_14":["tech_rsi"],"v2_bollinger_z":["tech_bollinger_z"],"v2_bollinger_width":["tech_bollinger_width"],
    "v2_volume_log_change":["tech_volume_log_change"],"v2_gap":["tech_overnight_gap"],"v2_intraday":["tech_intraday_return"],
    "v2_high_low_range":["tech_intraday_range"],"v2_month_sin":["tech_month_sin"],"v2_month_cos":["tech_month_cos"]}


def columns_for(base,groups,names):
    columns=list(base)
    for name in names:
        for column in groups[name]:
            if column not in columns and not any(alias in columns for alias in ALIASES.get(column,[])):
                columns.append(column)
    return columns
