"use strict";

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var Format14 = function (_BlinkElement) {
  _inherits(Format14, _BlinkElement);

  function Format14(args) {
    _classCallCheck(this, Format14);

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
    function format5Data(val) {
      var readmore = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : false;

      if (val === null || val === undefined) {
        return td({ class: "" }, "-");
      }
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
      return div({ class: "col" }, table({ class: "table table-bordered" }, thead(tr(th({ width: "75%" }, "Description"), th("Amount (Rs. in lakhs)"))), tbody(tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Revenue from operations")), tr(td("Interest Income"), format5Data(data.re_interest_inc)), tr(td("Dividend Income"), format5Data(data.re_dividend_inc)), tr(td("Rental Income"), format5Data(data.re_rental_inc)), tr(td("Fees and commission Income"), format5Data(data.re_fees_commission_inc)), tr(td("Net gain on fair value changes"), format5Data(data.re_net_gain_fair_val_changes)), tr(td("Net gain on derecognition of financial instruments under amortised cost category"), format5Data(data.re_net_gain_derecog_fin_inst)), tr(td("Sale of products(including Excise Duty)"), format5Data(data.re_sale_products)), tr(td("Sale of services"), format5Data(data.re_sale_services)), tr(td("Others"), format5Data(data.re_others)), tr(td({ class: "bold" }, "Total Revenue from operations (I)"), format5Data(data.re_net_sale)), tr(td("Other income (II)"), format5Data(data.re_oth_inc_new)), tr(td({ class: "bold" }, "Total Income (I + II)"), format5Data(data.re_total_inc)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Expenses")), tr(td("Finance Costs"), format5Data(data.re_int_new)), tr(td("Fees and commission expense"), format5Data(data.re_fees_commission_exp)), tr(td("Net loss on fair value changes"), format5Data(data.re_net_loss_fair_val_changes)), tr(td("Net loss on derecognition of financial instruments under amortised cost category"), format5Data(data.re_net_loss_derecog_fin_inst)), tr(td("Impairment on financial instruments"), format5Data(data.re_impair_fin_instr)), tr(td("Cost of materials consumed"), format5Data(data.re_rawmat_consump)), tr(td("Purchases of stock-in-trade"), format5Data(data.re_pur_trd_goods)), tr(td("Changes in inventories of finished goods, work-in-progress and stock-in-trade"), format5Data(data.re_inc_dre_sttr)), tr(td("Employee benefits expense"), format5Data(data.re_staff_cost)), tr(td("Depreciation and amortisation expense"), format5Data(data.re_depr_und_exp)), tr(td("Other expenses"), format5Data(data.re_oth_exp)), tr(td({ class: "bold" }, "Total Expenses (IV)"), format5Data(data.re_oth_tot_exp)), tr(td("Profit / (Loss) before exceptional items and tax (III - IV)"), format5Data(data.re_pro_bef_int_n_excep)), tr(td("Exceptional items (VI)"), format5Data(data.re_excepn_items_new)), tr(td({ class: "bold" }, "Profit / (Loss) before tax (V-VI) (VII)"), format5Data(data.re_pro_loss_bef_tax)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Tax Expenses")), tr(td("Current Tax"), format5Data(data.re_curr_tax)), tr(td("Deferred Tax"), format5Data(data.re_deff_tax)), tr(td("Total Tax expense (VIII)"), format5Data(data.re_tax)), tr(td({ class: "bold" }, "Profit (Loss) for the period from continuing operations (VII- VIII)"), format5Data(data.re_proloss_ord_act)), tr(td({ class: "bold" }, "Profit/(loss) from discontinued operations"), format5Data(data.re_pro_los_frm_dis_opr)), tr(td("Tax expense of discontinued operations"), format5Data(data.re_tax_expens_of_dis_opr)), tr(td({ class: "bold" }, "Profit/(loss) from Discontinued operations (after tax)"), format5Data(data.re_prolos_dis_opr_aftr_tax)), tr(td({ class: "bold" }, "Profit/(loss) for the period"), format5Data(data.dis_opr_aftr_tax_plus_ord_act)), tr(td({ class: "bold" }, "Share of profit/(loss) of associates"), format5Data(data.re_share_associate)), tr(td("Consolidated Net Profit/Loss for the period"), format5Data(data.re_con_pro_loss)), tr(td("Other comprehensive income"), format5Data(data.re_oth_cmpr_incm)), tr(td("Total comprehensive income"), format5Data(data.re_tot_cmpr_incm)), tr(td("Profit or loss, attributable to owners of parent"), format5Data(data.re_pl_own_par)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Total profit or loss, attributable to")), tr(td("Total profit or loss, attributable to non-controlling interests"), format5Data(data.re_tot_pl_nci)), tr(td("Comprehensive income for the period attributable to owners of parent"), format5Data(data.re_com_ic)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Total Comprehensive income for the period attributable to")), tr(td("Total comprehensive income for the period attributable to owners of parent non-controlling interests"), format5Data(data.re_tot_com_ic)), tr(td("Paid-up equity share capital"), format5Data(data.re_pdup)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Details of equity share capital")), tr(td("Face Value (in Rs.)"), format5Data(data.re_face_val)), tr(td("Basic EPS for continuing operations"), format5Data(data.re_bsc_eps_bfr_exi)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Earnings per equity share")), tr(td("Diluted EPS for continuing operations"), format5Data(data.re_dil_eps_bfr_exi)), tr(td("Basic EPS for discontinued operations"), format5Data(data.re_basic_eps)), tr(td("Diluted EPS for discontinued operations"), format5Data(data.re_diluted_eps)), tr(td("Basic EPS for continued and discontinued operations"), format5Data(data.re_basic_eps_for_cont_dic_opr)), tr(td("Diluted EPS for continued and discontinued operations"), format5Data(data.re_dilut_eps_for_cont_dic_opr)), tr(td("Disclosure of notes on financial results by banks"), format5Data(data.re_desc_note_fin)), tr(td("Notes to Accounts"), td({ class: "text-right" }, a({ class: "link", href: _this.state.data.attachment_filename }, _this.state.data.attachment_filename ? span({ class: "fa fa-download" }, " Download") : "-"))))));
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
        trs.push(tr(td({ width: "200" }, d.priSegName), format5Data(d.segValue)));
        addSubATotal = addSubATotal + parseFloat(d.segValue);
      });
      addSubS.forEach(function (d) {
        trs.push(tr(td({ width: "200" }, d.priSegName), format5Data(d.segValue)));
        addSubATotal = addSubATotal - parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Net sales/Income from Operations"), format5Data(addSubATotal)));
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
        trs.push(tr(td(d.priSegName), format5Data(d.segValue)));
        addSubATotal = addSubATotal + parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Total"), format5Data(addSubATotal)));
      addSubS.forEach(function (d) {
        trs.push(tr(td(d.priSegName), format5Data(d.segValue)));
        addSubSTotal = addSubSTotal + parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Total profit before Tax"), format5Data(addSubATotal - addSubSTotal)));
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
        trs.push(tr(td(d.priSegName), format5Data(d.segValue)));
        addSubATotal = addSubATotal + parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Total"), format5Data(addSubATotal)));
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
        trs.push(tr(td(d.priSegName), format5Data(d.segValue)));
        addSubATotal = addSubATotal + parseFloat(d.segValue);
      });
      trs.push(tr(td({ class: "bold" }, "Total"), format5Data(addSubATotal)));
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

  return Format14;
}(BlinkElement);

instantiate("Format14", Format14);