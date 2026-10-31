"use strict";

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var Format11 = function (_BlinkElement) {
  _inherits(Format11, _BlinkElement);

  function Format11(args) {
    _classCallCheck(this, Format11);

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
      return div({ class: "col" }, table({ class: "table table-bordered" }, thead(tr(th({ width: "75%" }, "Description"), th("Amount (Rs. in lakhs)"))), tbody(tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Part 1")), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Revenue from operations")), tr(td("Revenue from operations"), format(data.re_net_sale)), tr(td("Other income"), format(data.re_oth_inc_new)), tr(td({ class: "bold" }, "Total income"), format(parseFloat(data.re_net_sale) + parseFloat(data.re_oth_inc_new))), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Expenses")), tr(td("(a) Cost of materials consumed"), format(data.re_rawmat_consump)), tr(td("(b) Purchases of stock-in-trade"), format(data.re_pur_trd_goods)), tr(td("(c) Changes in inventories of finished goods, work-in-progress and stock-in-trade"), format(data.re_int_new)), tr(td("(d) Employee benefits expense"), format(data.re_staff_cost)), tr(td("(e) Finance costs"), format(data.re_int_new)), tr(td("(f) Depreciation and amortisation expense"), format(data.re_depr_und_exp)), tr(td("(g) Other expenses"), format(data.re_oth_exp)), tr(td({ class: "bold" }, "Total Expenses"), format(data.re_oth_tot_exp)), tr(td({ class: "bold" }, "Profit / (Loss) before exceptional items and tax"), format(data.re_pro_bef_int_n_excep)), tr(td("Exceptional items"), format(data.re_excepn_items_new)), tr(td({ class: "bold" }, "Profit / (Loss) before tax"), format(data.re_pro_loss_bef_tax)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Tax Expenses")), tr(td("Current Tax"), format(data.re_curr_tax)), tr(td("Deferred Tax"), format(data.re_deff_tax)), tr(td({ class: "bold" }, "Total Tax expense"), format(data.re_tax)), tr(td("Net movement in regulatory deferral account balances related to profit or loss and the related deferred tax movement"), format(data.re_net_mov_reg)), tr(td({ class: "bold" }, "Profit (Loss) for the period from continuing operations"), format(data.re_proloss_ord_act)), tr(td({ class: "bold" }, "Profit / (loss) from discontinued operations"), format(data.re_pro_los_frm_dis_opr)), tr(td("Tax expense of discontinued operations"), format(data.re_tax_expens_of_dis_opr)), tr(td({ class: "bold" }, "Profit / (loss) from Discontinued operations (after tax)"), format(data.re_prolos_dis_opr_aftr_tax)), tr(td({ class: "bold" }, "Profit / (loss) for the period"), format(data.dis_opr_aftr_tax_plus_ord_act)), tr(td("Share of profit / (loss) of associates"), format(data.re_share_associate)), tr(td({ class: "bold" }, "Consolidated Net Profit / Loss for the period"), format(data.re_con_pro_loss)), tr(td("Other comprehensive income"), format(data.re_oth_cmpr_incm)), tr(td({ class: "bold" }, "Total comprehensive income"), format(data.re_tot_cmpr_incm)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Total profit or loss, attributable to")), tr(td("Profit or loss, attributable to owners of parent"), format(data.re_pl_own_par)), tr(td("Total profit or loss, attributable to non-controlling interests"), format(data.re_tot_pl_nci)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Total Comprehensive income for the period attributable to")), tr(td("Comprehensive income for the period attributable to owners of parent"), format(data.re_com_ic)), tr(td("Total comprehensive income for the period attributable to owners of parent non-controlling interests"), format(data.re_tot_com_ic)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Details of equity share capital")), tr(td("Paid-up equity share capital"), format(data.re_pdup)), tr(td("Face Value(in Rs.)"), format(data.re_face_val)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Details of debt securities")), tr(td("Paid-up debt capital"), format(data.re_paid_debt)), tr(td("Face value of debt securities (in Rs.)"), format(data.re_face_value_debt)), tr(td("Reserve excluding Revaluation Reserves as per balance sheet of previous accounting year"), format(data.re_res_reval)), tr(td("Debenture redemption reserve"), format(data.re_debt_rdmption)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Earnings per share")), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Earnings per equity share for continuing operations")), tr(td("Basic EPS for continuing operations"), format(data.re_bsc_eps_bfr_exi)), tr(td("Diluted EPS for continuing operations"), format(data.re_dil_eps_bfr_exi)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Earnings per equity share for discontinued operations")), tr(td("Basic EPS for continued and discontinued operations"), format(data.re_basic_eps)), tr(td("Diluted EPS for discontinued operations"), format(data.re_diluted_eps)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Earnings per equity share")), tr(td("Basic EPS for continued and discontinued operations"), format(data.re_basic_eps_for_cont_dic_opr)), tr(td("Diluted EPS for continued and discontinued operations"), format(data.re_dilut_eps_for_cont_dic_opr)), tr(td("Debt equity ratio (in %)"), format(data.re_debt_eqt_rat)), tr(td("Debt service coverage ratio (in %)"), format(data.re_debt_ser_cov)), tr(td("Interest service coverage ratio (in %)"), format(data.re_int_ser_cov)), tr(td("Disclosure of notes on financial results by banks"), format(data.re_desc_note_fin, true)), tr(td("Notes to Accounts"), td({ class: "text-right" }, a({ class: "link", href: _this.state.data.attachment_filename }, _this.state.data.attachment_filename ? span({ class: "fa fa-download" }, " Download") : "-"))))));
    };
    var getRightTable = function getRightTable() {
      if (_this.state.data.segmentData) {
        return div({ class: "col-4" }, table({ class: "table table-bordered" }, thead(tr(th({ colspan: "2" }, "Segment Reporting (₹ Lakhs)"))), tbody(concatArr([{}], getSegmentA(), getSegmentB(), getSegmentC(), getSegmentD(), [
          /*tr(
                            td('Disclosure of notes on segments (link)'),
                            td(
                                'Still to be dicusssed'
                            )
                        )*/
        ]))));
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
      addSubA.forEach(function (d) {
        trs.push(tr(td({ width: "200" }, d.priSegName), format(d.segValue)));
        addSubATotal = addSubATotal + parseFloat(d.segValue);
      });
      addSubS.forEach(function (d) {
        trs.push(tr(td({ width: "200" }, d.priSegName), format(d.segValue)));
        addSubATotal = addSubATotal - parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Net sales/Income from Operations"), format(addSubATotal)));
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
    var dom = div({}, getMetadata(), div({ class: "text-bold p-1 tableTitle mb-2 text-center" }, "Non Banking"), div({ class: "row" }, getLeftTable(), getRightTable()));

    //mandatory code for a BlinkUI component
    _this.args = dom.args;
    _this.elem = dom.elem;
    _this.elem.cmp = _this;
    //mandatory code for a BlinkUI component ends
    return _this;
  }

  return Format11;
}(BlinkElement);

instantiate("Format11", Format11);