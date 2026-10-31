"use strict";

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var keysToExclude = ['sr_desc_note_fin'];

var FormatSMENonINDAS = function (_BlinkElement) {
    _inherits(FormatSMENonINDAS, _BlinkElement);

    function FormatSMENonINDAS(args) {
        _classCallCheck(this, FormatSMENonINDAS);

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
            return table({ class: "table table-bordered mt-5" }, tbody(concatArr([{}], tData)));
        };
        function format(val) {
            var readmore = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : false;
            var key = arguments[2];

            if ((parseFloat(val) || parseFloat(val) === 0) && !keysToExclude.includes(key)) {
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
            return div({ class: "col" }, table({ class: "table table-bordered" }, thead(tr(th({ width: "75%" }, "Description"), th("Amount (Rs. in lakhs)"))), tbody(tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Part 1")), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Revenue from operations")), tr(td("Revenue from operations"), format(data.sr_net_sale)), tr(td("Other income"), format(data.sr_oth_inc_new)), tr(td("Total income"), format(data.sr_total_inc)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Expenses")), tr(td("(a) Cost of materials consumed"), format(data.sr_rawmat_consump)), tr(td("(b) Purchase of stock-in-trade"), format(data.sr_pur_trd_goods)), tr(td("(c) Changes in inventories of finished goods, work-in-progress and stock-in-trade"), format(data.sr_inc_dre_sttr)), tr(td("(d) Employee benefits expense"), format(data.sr_staff_cost)), tr(td("(e) Finance costs"), format(data.sr_int_new)), tr(td("(f) Depreciation and amortisation expense"), format(data.sr_depr_und_exp)), tr(td("(g) Other expenses"), format(data.sr_oth_exp)), tr(td("Total Expenses"), format(data.sr_oth_tot_exp)), tr(td("Profit/(Loss) before exceptional items and tax"), format(data.sr_pro_aft_int_bef_excep)), tr(td("Exceptional items"), format(data.sr_excepn_items_new)), tr(td("Profit/(Loss) before tax"), format(data.sr_pro_loss_bef_tax)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Tax Expenses")), tr(td("Current Tax"), format(data.sr_curr_tax)), tr(td("Deferred Tax"), format(data.sr_deff_tax)), tr(td("Total Tax expense"), format(data.sr_tax)), tr(td("Net Profit/Loss for the period from continuing operations"), format(data.sr_proloss_ord_act)),
            // tr(td("Profit (Loss) for the period from continuing operations"), format(data.sr_pro_los_frm_dis_opr)),
            tr(td("Profit/(loss) from discontinued operations"), format(data.sr_pro_los_frm_dis_opr)), tr(td("Tax expense of discontinued operations"), format(data.sr_tax_expens_of_dis_opr)), tr(td("Profit/(loss) from Discontinued operations (after tax)"), format(data.sr_prolos_dis_opr_aftr_tax)), tr(td("Profit/(loss) for the period"), format(data.sr_net_profit)), tr(td("Share of profit/(loss) of associates"), format(data.sr_share_associate)), tr(td("Minority Interest"), format(data.sr_minority_int)), tr(td("Net Profit/Loss for the period"), format(data.sr_con_pro_loss)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Details of equity share capital")), tr(td("Paid-up equity share capital"), format(data.sr_pdup)), tr(td("Face Value (in Rs.)"), format(data.sr_face_val)), tr(td("Reserve excluding Revaluation Reserves as per balance sheet of previous accounting year"), format(data.sr_res_reval)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Earnings per share")), tr(td("Basic EPS"), format(data.sr_basic_eps_for_cont_dic_opr)), tr(td("Diluted EPS"), format(data.sr_dilut_eps_for_cont_dic_opr)), tr(td("Debt equity ratio (in %)"), format(data.sr_debt_eqt_rat)), tr(td("Debt service coverage ratio (in %)"), format(data.sr_debt_ser_cov)), tr(td("Interest service coverage ratio (in %)"), format(data.sr_int_ser_cov)), tr(td("Notes to Accounts"), format(data.sr_desc_note_fin, true, 'sr_desc_note_fin'))

            // tr(td("Notes to Accounts"), td({ class: "text-right" }, a(
            //     { class: "link", href: this.state.data.sr_desc_note_fin }, this.state.data.sr_desc_note_fin
            //     ? span({ class: "fa fa-download" }, " Download")
            //     : "-"
            // )
            // )
            // )
            )));
        };
        var dom = div({}, getMetadata(), div({ class: "text-bold p-1 tableTitle mb-2 text-center" }, "Non Banking - Non IND AS"), div({ class: "row" }, getLeftTable()));

        //mandatory code for a BlinkUI component
        _this.args = dom.args;
        _this.elem = dom.elem;
        _this.elem.cmp = _this;
        //mandatory code for a BlinkUI component ends
        return _this;
    }

    return FormatSMENonINDAS;
}(BlinkElement);

instantiate("FormatSMENonINDAS", FormatSMENonINDAS);

var FormatSMEINDAS = function (_BlinkElement2) {
    _inherits(FormatSMEINDAS, _BlinkElement2);

    function FormatSMEINDAS(args) {
        _classCallCheck(this, FormatSMEINDAS);

        var _this2 = _possibleConstructorReturn(this, _BlinkElement2.call(this));

        var attr = B.extractArgAttrs(args);
        _this2.state = new B.State({
            row: attr.row,
            data: attr.data || []
        });

        var row = _this2.state.row;
        var data = _this2.state.data.resultsData2;

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
            return table({ class: "table table-bordered mt-5" }, tbody(concatArr([{}], tData)));
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
            return div({ class: "col" }, table({ class: "table table-bordered" }, thead(tr(th({ width: "75%" }, "Description"), th("Amount (Rs. in lakhs)"))), tbody(tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Part 1")), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Revenue from operations")), tr(td("Revenue from operations"), format(data.sr_net_sale)), tr(td("Other income"), format(data.sr_oth_inc_new)), tr(td("Total income"), format(data.sr_total_inc)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Expenses")), tr(td("(a) Cost of materials consumed"), format(data.sr_rawmat_consump)), tr(td("(b) Purchase of stock-in-trade"), format(data.sr_pur_trd_goods)), tr(td("(c) Changes in inventories of finished goods, work-in-progress and stock-in-trade"), format(data.sr_inc_dre_sttr)), tr(td("(d) Employee benefits expense"), format(data.sr_staff_cost)), tr(td("(e) Finance costs"), format(data.sr_int_new)), tr(td("(f) Depreciation and amortisation expense"), format(data.sr_depr_und_exp)), tr(td("(g) Other expenses"), format(data.sr_oth_exp)), tr(td("Total Expenses"), format(data.sr_oth_tot_exp)), tr(td("Profit/(Loss) before exceptional items and tax"), format(data.sr_pro_aft_int_bef_excep)), tr(td("Exceptional items"), format(data.sr_excepn_items_new)), tr(td("Profit/(Loss) before tax"), format(data.sr_pro_loss_bef_tax)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Tax Expenses")), tr(td("Current Tax"), format(data.sr_curr_tax)), tr(td("Deferred Tax"), format(data.sr_deff_tax)), tr(td("Total Tax expense"), format(data.sr_tax)), tr(td("Net movement in regulatory deferral account balances related to profit or loss and the related deferred tax movement"), format(data.sr_net_mov_reg)), tr(td("Profit (Loss) for the period from continuing operations"), format(data.sr_proloss_ord_act)), tr(td("Profit/(loss) from discontinued operations"), format(data.sr_pro_los_frm_dis_opr)), tr(td("Tax expense of discontinued operations"), format(data.sr_tax_expens_of_dis_opr)), tr(td("Profit/(loss) from Discontinued operations (after tax)"), format(data.sr_prolos_dis_opr_aftr_tax)), tr(td("Profit/(loss) for the period"), format(data.sr_net_profit)), tr(td("Share of profit/(loss) of associates"), format(data.sr_share_associate)), tr(td("Net Profit/Loss for the period"), format(data.sr_con_pro_loss)), tr(td("Other comprehensive income"), format(data.sr_oth_cmpr_incm)), tr(td("Total comprehensive income"), format(data.sr_tot_cmpr_incm)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Total profit or loss, attributable to")), tr(td("Profit or loss, attributable to owners of parent"), format(data.sr_pl_own_par)), tr(td("Total profit or loss, attributable to non-controlling interests"), format(data.sr_tot_pl_nci)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Total Comprehensive income for the period attributable to")), tr(td("Comprehensive income for the period attributable to owners of parent"), format(data.sr_com_ic)), tr(td("Total comprehensive income for the period attributable to owners of parent non-controlling interests"), format(data.sr_tot_com_ic)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Details of equity share capital")), tr(td("Paid-up equity share capital"), format(data.sr_pdup)), tr(td("Face Value (in Rs.)"), format(data.sr_face_val)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Details of debt securities")), tr(td("Paid-up debt capital"), format(data.sr_paid_debt)), tr(td("Face value of debt securities (in Rs.)"), format(data.sr_face_value_debt)), tr(td("Reserve excluding Revaluation Reserves as per balance sheet of previous accounting year"), format(data.sr_res_reval)), tr(td("Debenture redemption reserve"), format(data.sr_debt_rdmption)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Earnings per share")), tr(td("Earnings per equity share for continuing operations")), tr(td("Basic EPS for continuing operations"), format(data.sr_bsc_eps_bfr_exi)), tr(td("Diluted EPS for continuing operations"), format(data.sr_dil_eps_bfr_exi)), tr(td("Earnings per equity share for discontinued operations")), tr(td("Basic EPS for continued and discontinued operations"), format(data.sr_basic_eps_for_cont_dic_opr)), tr(td("Diluted EPS for discontinued operations"), format(data.sr_diluted_eps)), tr(td({ colspan: "2", class: "section", style: "font-weight:bold" }, "Earnings per equity share")), tr(td("Basic EPS for continued and discontinued operations"), format(data.sr_basic_eps_for_cont_dic_opr)), tr(td("Diluted EPS for continued and discontinued operations"), format(data.sr_dilut_eps_for_cont_dic_opr)), tr(td("Debt equity ratio (in %)"), format(data.sr_debt_eqt_rat)), tr(td("Debt service coverage ratio (in %)"), format(data.sr_debt_ser_cov)), tr(td("Interest service coverage ratio (in %)"), format(data.sr_int_ser_cov)), tr(td("Notes to Accounts"), td({ class: "text-right" }, a({ class: "link", href: _this2.state.data.attachment_filename }, _this2.state.data.attachment_filename ? span({ class: "fa fa-download" }, " Download") : "-"))))));
        };
        var dom = div({}, getMetadata(), div({ class: "text-bold p-1 tableTitle mb-2 text-center" }, "Non Banking - IND AS"), div({ class: "row" }, getLeftTable()));

        //mandatory code for a BlinkUI component
        _this2.args = dom.args;
        _this2.elem = dom.elem;
        _this2.elem.cmp = _this2;
        //mandatory code for a BlinkUI component ends
        return _this2;
    }

    return FormatSMEINDAS;
}(BlinkElement);

instantiate("FormatSMEINDAS", FormatSMEINDAS);