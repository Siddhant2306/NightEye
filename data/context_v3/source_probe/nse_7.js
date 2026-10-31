"use strict";

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var Format10 = function (_BlinkElement) {
  _inherits(Format10, _BlinkElement);

  function Format10(args) {
    _classCallCheck(this, Format10);

    var _this = _possibleConstructorReturn(this, _BlinkElement.call(this));

    var attr = B.extractArgAttrs(args);
    _this.state = new B.State({
      row: attr.row,
      data: attr.data || []
    });
    var row = _this.state.row;
    var data = _this.state.data.resultsData2;

    var getMetadata = function getMetadata() {
      var metadata = [{
        title: "Symbol",
        name: "symbol"
      }, {
        title: "Company",
        name: "companyName"
      }, {
        title: "Industry",
        name: "industry"
      }, {
        title: "Audited / Un-Audited",
        name: "audited"
      }, {
        title: "Cumulative / Non-Cumulative",
        name: "cumulative"
      }, {
        title: "Consolidated / Non-Consolidated",
        name: "consolidated"
      }, {
        title: "Period",
        name: "period"
      }, {
        title: "Relating to",
        name: "relatingTo"
      }, {
        title: "Financial Year",
        name: "financialYear"
      }, {
        title: "Period Ended",
        name: "toDate"
      }];
      var tData = [];
      metadata.forEach(function (d, index) {
        if (index % 2 === 0) {
          tData.push(tr(th(metadata[index].title), td(row[metadata[index].name]), th(metadata[index + 1].title), td(row[metadata[index + 1].name])));
        }
      });
      return table({ class: "table table-bordered" }, tbody(concatArr([{}], tData)));
    };
    function format(val) {
      var readmore = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : false;

      if (parseFloat(val) || parseFloat(val) === 0) {
        return td({ class: "text-align-right" }, parseFloat(val) === 0 ? val : DecimalFixed(val).toString());
      }
      if (val == null) {
        return td({ class: "text-align-right" }, "-");
      }
      if (val == "-") {
        return td({ class: "text-align-right" }, "-");
      }
      return td(readmore ? convertToReadMore(val) : val);
    }
    var getLeftTable = function getLeftTable() {
      return div({ class: "col" }, table({ class: "table table-bordered" }, thead(tr(th({ width: "75%" }, "Description"), th("Amount (Rs. in lakhs)"))), tbody(tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Interest Earned")), tr(td("Interest/Discount on Advances/Bills"), format(data.re_int_dis_adv_bills)), tr(td("Income on Investments"), format(data.re_income_inv)), tr(td("Interest on Balances With RBI & Other Inter bank Funds"), format(data.re_bal_rbi_oth_bnk_funds)), tr(td("Others"), format(data.re_oth)), tr(td({ class: "bold" }, "Total Interest Earned"), format(data.re_int_earned)), tr(td("Other Income"), format(data.re_oth_inc)), tr(td({ class: "bold" }, "Total Income"), format(data.re_tot_inc)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Expenses")), tr(td("Interest Expended"), format(data.re_int_expd)), tr(td({ class: "bold" }, "Operating Expenses"), format(data.re_oper_exp)), tr(td("Employees cost"), format(data.re_prov_emp_pay)), tr(td("Other Operating Expenses"), format(data.re_oth_oper_exp)), tr(td({ class: "bold" }, "Total Expenditure (excluding provisions and contingencies)"), format(data.re_tot_exp_exc_pro_cont)), tr(td({ class: "bold" }, "Operating Profit before provisions and contingencies"), format(data.re_oper_exp_bef_pro_cont)), tr(td("Provisions (other than tax) and contingencies"), format(data.re_oth_pro_cont)), tr(td("Exceptional items"), format(data.re_excepn_items)), tr(td({ class: "bold" }, "Profit/(Loss) from Ordinary Activities before tax"), format(data.re_pro_loss_bef_tax)), tr(td("Tax Expense"), format(data.re_tax)), tr(td({ class: "bold" }, "Net Profit/(Loss) from Ordinary Activities after tax"), format(data.re_proloss_ord_act)), tr(td("Extraordinary Items (net of tax expense)"), format(data.re_extraord_items)), tr(td({ class: "bold" }, "Net Profit/(Loss) for the period"), format(data.re_net_profit)), tr(td("Minority Interest"), format(data.re_minority_int)), tr(td("Shares of Associates"), format(data.re_share_associate)), tr(td({ class: "bold" }, "Consolidated Net Profit / Loss for the period"), format(data.re_con_pro_loss)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Details of equity share capital")), tr(td("Paid-up Equity Share Capital"), format(data.re_pdup)), tr(td("Face Value (in Rs.)"), format(data.re_face_val)), tr(td("Reserves excluding Revaluation Reserves as per balance sheet of previous accounting year"), format(data.re_res_reval)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Analytical Ratios")), tr(td("Percentage of shares Held by Government of India"), format(data.re_goi_per_shhd)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Capital Adequacy Ratio")), tr(td("CET 1 ratio (in %)"), format(data.re_cet_1_ret)), tr(td("Capital Adequacy Ratio (Basel III) (in %)"), format(data.re_cap_ade_rat)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Earnings per share before extraordinary items")), tr(td("Basic EPS after Extraordinary items (in Rs.)"), format(data.re_bsc_eps_bfr_exi)), tr(td("Diluted EPS after Extraordinary items (in Rs.)"), format(data.re_dil_eps_bfr_exi)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Earnings per share after extraordinary items")), tr(td("Basic EPS after Extraordinary items (in Rs.) "), format(data.re_basic_eps)), tr(td("Diluted EPS after Extraordinary items (in Rs.)"), format(data.re_diluted_eps)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "NPA Ratios")), tr(td("Amount of gross non-performing assets"), format(data.re_amt_grs_np_asst)), tr(td("Amount of net non-performing assets"), format(data.re_grs_npa)), tr(td("% of gross NPAs"), format(data.re_per_grs_npa)), tr(td("% of Net NPA"), format(data.re_grs_npa_per)), tr(td("Return on Assets (in %)"), format(data.re_ret_asset)), tr(td("Disclosure of notes on financial results by banks"), format(data.re_desc_note_fin, true)), tr(td("Notes to Accounts"), td({ class: "text-right" }, a({ class: "link", href: _this.state.data.attachment_filename }, _this.state.data.attachment_filename ? span({ class: "fa fa-download" }, " Download") : "-"))))));
    };
    var getRightTable = function getRightTable() {
      if (_this.state.data.segmentData) {
        return div({ class: "col-4" }, table({ class: "table table-bordered" }, thead(tr(th({ colspan: "2" }, "Segment Reporting (₹ Lakhs)"))), tbody(concatArr([{}], getSegmentA(), getSegmentB(), getSegmentC(), getSegmentD()))));
      } else {
        return div();
      }
    };
    var getSegmentA = function getSegmentA() {
      var segData = _this.state.data.segmentData.filter(function (d) {
        return d.segmentInfo === "A";
      });
      var addSubA = segData.filter(function (d) {
        return d.addSub === "A";
      });
      var addSubS = segData.filter(function (d) {
        return d.addSub === "S";
      });
      var trs = [tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Segment Revenue"))];
      var addSubATotal = 0;
      var addSubSTotal = 0;
      addSubA.forEach(function (d) {
        trs.push(tr(td({ width: "200" }, d.priSegName), format(d.segValue)));
        addSubATotal = addSubATotal + parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Total"), format(addSubATotal)));
      addSubS.forEach(function (d) {
        trs.push(tr(td(d.priSegName), format(d.segValue)));
        addSubSTotal = addSubSTotal + parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Net sales/Income from Operations"), format(addSubATotal - addSubSTotal)));
      return trs;
    };
    var getSegmentB = function getSegmentB() {
      var segData = _this.state.data.segmentData.filter(function (d) {
        return d.segmentInfo === "B";
      });
      var addSubA = segData.filter(function (d) {
        return d.addSub === "A";
      });
      var addSubS = segData.filter(function (d) {
        return d.addSub === "S";
      });
      var trs = [tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Segment Results"))];
      var addSubATotal = 0;
      var addSubSTotal = 0;
      addSubA.forEach(function (d) {
        trs.push(tr(td(d.priSegName), format(d.segValue)));
        addSubATotal = addSubATotal + parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Total"), format(addSubATotal)));
      addSubS.forEach(function (d) {
        trs.push(tr(td(d.priSegName), format(d.segValue)));
        addSubSTotal = addSubSTotal + parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Total profit before Tax"), format(addSubATotal - addSubSTotal)));
      return trs;
    };
    var getSegmentC = function getSegmentC() {
      var segData = _this.state.data.segmentData.filter(function (d) {
        return d.segmentInfo === "C";
      });
      var addSubA = segData.filter(function (d) {
        return d.addSub === "A";
      });
      var trs = [tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Segment Assets"))];
      var addSubATotal = 0;
      addSubA.forEach(function (d) {
        trs.push(tr(td(d.priSegName), format(d.segValue)));
        addSubATotal = addSubATotal + parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Total"), format(addSubATotal)));
      return trs;
    };
    var getSegmentD = function getSegmentD() {
      var segData = _this.state.data.segmentData.filter(function (d) {
        return d.segmentInfo === "D";
      });
      var addSubA = segData.filter(function (d) {
        return d.addSub === "A";
      });
      var trs = [tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, " Segment Liabilites"))];
      var addSubATotal = 0;
      addSubA.forEach(function (d) {
        trs.push(tr(td(d.priSegName), format(d.segValue)));
        addSubATotal = addSubATotal + parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Total"), format(addSubATotal)));
      return trs;
    };
    var dom = div({}, getMetadata(), div({ class: "text-bold p-1 tableTitle mb-2 text-center" }, "Banking"), div({ class: "row" }, getLeftTable(), getRightTable()));

    //mandatory code for a BlinkUI component
    _this.args = dom.args;
    _this.elem = dom.elem;
    _this.elem.cmp = _this;
    //mandatory code for a BlinkUI component ends
    return _this;
  }

  return Format10;
}(BlinkElement);

instantiate("Format10", Format10);