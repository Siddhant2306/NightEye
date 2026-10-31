"use strict";

var _extends = Object.assign || function (target) { for (var i = 1; i < arguments.length; i++) { var source = arguments[i]; for (var key in source) { if (Object.prototype.hasOwnProperty.call(source, key)) { target[key] = source[key]; } } } return target; };

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var ResultsComparison = function (_BlinkElement) {
    _inherits(ResultsComparison, _BlinkElement);

    function ResultsComparison(args) {
        _classCallCheck(this, ResultsComparison);

        var _this = _possibleConstructorReturn(this, _BlinkElement.call(this));

        var attr = B.extractArgAttrs(args);
        _this.state = new B.State({
            data: attr.data || {},
            keepEmptyAtStart: attr.keepEmptyAtStart || {}
        });
        function format(val) {
            if (typeof val === "undefined" || val === null) {
                return "-";
            }
            if (parseFloat(val)) {
                return DecimalFixed(val).toString();
            }
            return val;
        }
        var noData = function noData(_noData) {
            if (_this.state.keepEmptyAtStart) {
                _this.state.keepEmptyAtStart = false;
                return table(_extends({}, attr.tableStyle), tbody(tr()));
            } else {
                return table(_extends({}, attr.tableStyle), tbody(tr(td({ class: 'text-center emptyRow' }, _noData ? 'No Records' : 'Please enter a valid symbol'))));
            }
        };
        var _getRandomInt = function _getRandomInt(min, max) {
            return Math.floor(Math.random() * (max - min + 1)) + min;
        };
        function generateId() {
            var length = 8;
            var timestamp = +new Date();
            var ts = timestamp.toString();
            var parts = ts.split("").reverse();
            var id = "";

            for (var i = 0; i < length; i++) {
                var index = _getRandomInt(0, parts.length - 1);
                id += parts[index];
            }

            return id;
        }
        var readMore = function readMore(id, rowNo) {
            var elem = document.getElementById(id);
            var elemSel = document.querySelector("#" + id);
            elem.classList.toggle("eclipse");
            //const rowIndex = id.replace("readMore","");
            var txt = _this.state.data.resCmpData[parseInt(rowNo)]['re_desc_note_fin'];
            if (elemSel.classList.contains('eclipse')) {
                elem.nextElementSibling.innerText = "Read More";
                elem.innerHTML = txt.substr(0, 120) + '...';
            } else {
                elem.nextElementSibling.innerText = " Read Less";
                elem.innerHTML = txt;
            }
        };
        var getAriaHeader = function getAriaHeader(date, type, head, subHead) {
            try {
                var id = "";
                if (type == 'A') {
                    id = "audited";
                } else {
                    id = "unaudited";
                }
                id = date + " " + id + " " + head + " " + subHead;
                return id;
            } catch (e) {
                console.log(e);
                return '-';
            }
        };
        var Format14 = function Format14(data) {
            var len = (data.length + 1).toString();
            if (data.length === 0) {
                return noData(true);
            }
            return table(_extends({}, attr.tableStyle), thead(tr(concatArr([{ class: "withborder" }], [th({ width: '20%', id: "quarterEnded" }, 'QUARTER ENDED')], data.map(function (d) {
                return th({ class: "text-right", id: ("" + d.re_to_dt).toLowerCase() }, d.re_to_dt);
            }))), tr(concatArr([{ class: "withborder" }], [th({ width: '20%', id: "particulars" }, 'PARTICULARS')], data.map(function (d) {
                return th({ class: "text-right", id: d.re_res_type === 'A' ? 'audited' : 'unaudited'.toLowerCase() }, d.re_res_type === 'A' ? 'AUDITED' : 'UNAUDITED');
            })))), tbody(tr(td({ "colspan": len, class: "sectionCol", id: "revenueFromOperations" }, 'Revenue from operations')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars revenueFromOperations" }, 'Interest Income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Interest Income") }, format(d.re_interest_inc));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars revenueFromOperations" }, 'Dividend Income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Dividend Income") }, format(d.re_dividend_inc));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars revenueFromOperations" }, 'Rental Income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Rental Income") }, format(d.re_rental_inc));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars revenueFromOperations" }, 'Fees and commission Income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Fees and commission Income") }, format(d.re_fees_commission_inc));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars revenueFromOperations" }, 'Net gain on fair value changes')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Net gain on fair value changes") }, format(d.re_net_gain_fair_val_changes));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars revenueFromOperations" }, 'Net gain on derecognition of financial instruments under amortised cost category')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Net gain on derecognition of financial instruments under amortised cost category") }, format(d.re_net_gain_derecog_fin_inst));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars revenueFromOperations" }, 'Sale of products(including Excise Duty)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Sale of products(including Excise Duty)") }, format(d.re_sale_products));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars revenueFromOperations" }, 'Sale of services')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Sale of services") }, format(d.re_sale_services));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars revenueFromOperations" }, 'Others')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Others") }, format(d.re_others));
            }))), tr(concatArr([{}], [td({ width: '20%', class: 'bold', headers: "quarterEnded particulars revenueFromOperations" }, 'Total Revenue from operations (I)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Total Revenue from operations (I)") }, format(d.re_net_sale));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars revenueFromOperations" }, 'Other income (II)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Other income (II)") }, format(d.re_oth_inc_new));
            }))), tr(concatArr([{}], [td({ width: '20%', class: 'bold', headers: "quarterEnded particulars revenueFromOperations" }, 'Total Income (I + II)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "revenueFromOperations", "Total Income (I + II)") }, format(d.re_total_inc));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "expenses" }, 'Expenses')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Finance Costs')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Finance Costs") }, format(d.re_int_new));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Fees and commission expense')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Fees and commission expense") }, format(d.re_fees_commission_exp));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Net loss on fair value changes')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Net loss on fair value changes") }, format(d.re_net_loss_fair_val_changes));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Net loss on derecognition of financial instruments under amortised cost category')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Net loss on derecognition of financial instruments under amortised cost category") }, format(d.re_net_loss_derecog_fin_inst));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Impairment on financial instruments')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Impairment on financial instruments") }, format(d.re_impair_fin_instr));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Cost of materials consumed')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Cost of materials consumed") }, format(d.re_rawmat_consump));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Purchases of stock-in-trade')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Purchases of stock-in-trade") }, format(d.re_pur_trd_goods));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Changes in inventories of finished goods, work-in-progress and stock-in-trade')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Changes in inventories of finished goods, work-in-progress and stock-in-trade") }, format(d.re_inc_dre_sttr));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Employee benefits expense')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Employee benefits expense") }, format(d.re_staff_cost));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Depreciation and amortisation expense')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Depreciation and amortisation expense") }, format(d.re_depr_und_exp));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Other expenses')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Other expenses") }, format(d.re_oth_exp));
            }))), tr(concatArr([{}], [td({ width: '20%', class: 'bold', headers: "quarterEnded particulars expenses" }, 'Total Expenses (IV)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Total Expenses (IV)") }, format(d.re_oth_tot_exp));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Profit / (Loss) before exceptional items and tax (III - IV)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Profit / (Loss) before exceptional items and tax (III - IV)") }, format(d.re_pro_bef_int_n_excep));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Exceptional items (VI)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Exceptional items (VI)") }, format(d.re_excepn_items_new));
            }))), tr(concatArr([{}], [td({ width: '20%', class: 'bold', headers: "quarterEnded particulars expenses" }, 'Profit / (Loss) before tax (V-VI) (VII)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Profit / (Loss) before tax (V-VI) (VII)") }, format(d.re_pro_loss_bef_tax));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "taxExpenses" }, 'Tax Expenses')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Current Tax')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Current Tax") }, format(d.re_curr_tax));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Deferred Tax')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Deferred Tax") }, format(d.re_deff_tax));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Total Tax expense (VIII)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Total Tax expense (VIII)") }, format(d.re_tax));
            }))), tr(concatArr([{}], [td({ width: '20%', class: 'bold', headers: "quarterEnded particulars taxExpenses" }, 'Profit (Loss) for the period from continuing operations (VII- VIII)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Profit (Loss) for the period from continuing operations (VII- VIII)") }, format(d.re_proloss_ord_act));
            }))), tr(concatArr([{}], [td({ width: '20%', class: 'bold', headers: "quarterEnded particulars taxExpenses" }, 'Profit/(loss) from discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Profit/(loss) from discontinued operations") }, format(d.re_pro_los_frm_dis_opr));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Tax expense of discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Tax expense of discontinued operations") }, format(d.re_tax_expens_of_dis_opr));
            }))), tr(concatArr([{}], [td({ width: '20%', class: 'bold', headers: "quarterEnded particulars taxExpenses" }, 'Profit/(loss) from Discontinued operations (after tax)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Profit/(loss) from Discontinued operations (after tax)") }, format(d.re_prolos_dis_opr_aftr_tax));
            }))), tr(concatArr([{}], [td({ width: '20%', class: 'bold', headers: "quarterEnded particulars taxExpenses" }, 'Profit/(loss) for the period')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Profit/(loss) for the period") }, format(d.dis_opr_aftr_tax_plus_ord_act));
            }))), tr(concatArr([{}], [td({ width: '20%', class: 'bold', headers: "quarterEnded particulars taxExpenses" }, 'Share of profit/(loss) of associates')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Share of profit/(loss) of associates") }, format(d.re_share_associate));
            }))), tr(concatArr([{}], [td({ width: '20%', class: 'bold', headers: "quarterEnded particulars taxExpenses" }, 'Consolidated Net Profit/Loss for the period')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Consolidated Net Profit/Loss for the period") }, format(d.re_con_pro_loss));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Other comprehensive income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Other comprehensive income") }, format(d.re_oth_cmpr_incm));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Total comprehensive income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Total comprehensive income") }, format(d.re_tot_cmpr_incm));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Profit or loss, attributable to owners of parent')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Profit or loss, attributable to owners of parent") }, format(d.re_pl_own_par));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "totalProfitorLoss" }, 'Total profit or loss, attributable to')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars totalProfitorLoss" }, 'Total profit or loss, attributable to non-controlling interests')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "totalProfitorLoss", "Total profit or loss, attributable to non-controlling interests") }, format(d.re_tot_pl_nci));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars totalProfitorLoss" }, 'Comprehensive income for the period attributable to owners of parent')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "totalProfitorLoss", "Comprehensive income for the period attributable to owners of parent") }, format(d.re_com_ic));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "totalComprehensiveIncome" }, 'Total Comprehensive income for the period attributable to')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars totalComprehensiveIncome" }, 'Total comprehensive income for the period attributable to owners of parent non-controlling interests')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "totalComprehensiveIncome", "Total comprehensive income for the period attributable to owners of parent non-controlling interests") }, format(d.re_tot_com_ic));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars totalComprehensiveIncome" }, 'Paid-up equity share capital')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "totalComprehensiveIncome", "Paid-up equity share capital") }, format(d.re_pdup));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "detailsofEquityShareCapital" }, 'Details of equity share capital')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars detailsofEquityShareCapital" }, 'Face Value (in Rs.)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "detailsofEquityShareCapital", "Face Value (in Rs.)") }, format(d.re_face_val));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars detailsofEquityShareCapital" }, 'Basic EPS for continuing operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "detailsofEquityShareCapital", "Basic EPS for continuing operations") }, format(d.re_bsc_eps_bfr_exi));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "earningsPerEquityShare" }, 'Earnings per equity share')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShare" }, 'Diluted EPS for continuing operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShare", "Diluted EPS for continuing operations") }, format(d.re_dil_eps_bfr_exi));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShare" }, 'Basic EPS for discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShare", "Basic EPS for discontinued operations") }, format(d.re_basic_eps));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShare" }, 'Diluted EPS for discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShare", "Diluted EPS for discontinued operations") }, format(d.re_diluted_eps));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShare" }, 'Basic EPS for continued and discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShare", "Basic EPS for continued and discontinued operations") }, format(d.re_basic_eps_for_cont_dic_opr));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShare" }, 'Diluted EPS for continued and discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShare", "Diluted EPS for continued and discontinued operations") }, format(d.re_dilut_eps_for_cont_dic_opr));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShare" }, 'Disclosure of notes on financial results by banks')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShare", "Disclosure of notes on financial results by banks") }, format(d.re_desc_note_fin));
            })))));
        };
        var Format11 = function Format11(data) {
            var len = (data.length + 1).toString();
            if (data.length === 0) {
                return noData(true);
            }
            return table(_extends({}, attr.tableStyle), thead(tr(concatArr([{ class: "withborder" }], [th({ width: '20%', id: "quarterEnded" }, 'QUARTER ENDED')], data.map(function (d) {
                return th({ class: "text-right", id: ("" + d.re_to_dt).toLowerCase() }, d.re_to_dt);
            }))), tr(concatArr([{ class: "withborder" }], [th({ width: '20%', id: "particulars" }, 'PARTICULARS')], data.map(function (d) {
                return th({ class: "text-right", id: d.re_res_type === 'A' ? 'audited' : 'unaudited'.toLowerCase() }, d.re_res_type === 'A' ? 'AUDITED' : 'UNAUDITED');
            })))), tbody(tr(td({ "colspan": len, class: "sectionCol", id: "part1" }, 'Part 1')), tr(td({ "colspan": len, class: "sectionCol", id: "revenueFromOperations" }, 'Revenue from operations')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars part1 revenueFromOperations" }, 'Revenue from operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "part1 revenueFromOperations", "Revenue from operations") }, format(d.re_net_sale));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars part1 revenueFromOperations" }, 'Other income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "part1 revenueFromOperations", "Other income") }, format(d.re_oth_inc_new));
            }))), tr(concatArr([{ class: "highlightRow" }], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars part1 revenueFromOperations" }, 'Total income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "part1 revenueFromOperations", "Total income") }, format(parseInt(d.re_net_sale) + parseInt(d.re_oth_inc_new)));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "expenses" }, 'Expenses')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, '(a) Cost of materials consumed')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "(a) Cost of materials consumed") }, format(d.re_rawmat_consump));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, '(b) Purchases of stock-in-trade')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "(b) Purchases of stock-in-trade") }, format(d.re_pur_trd_goods));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, '(c) Changes in inventories of finished goods, work-in-progress and stock-in-trade')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "(c) Changes in inventories of finished goods, work-in-progress and stock-in-trade") }, format(d.re_int_new));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, '(d) Employee benefits expense')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "(d) Employee benefits expense") }, format(d.re_staff_cost));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, '(e) Finance costs')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "(e) Finance costs") }, format(d.re_int_new));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, '(f) Depreciation and amortisation expense')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "(f) Depreciation and amortisation expense") }, format(d.re_depr_und_exp));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, '(g) Other expenses')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "(g) Other expenses") }, format(d.re_oth_exp));
            }))), tr(concatArr([{ class: "highlightRow" }], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars expenses" }, 'Total Expenses')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Total Expenses") }, format(d.re_oth_tot_exp));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars expenses" }, 'Profit / (Loss) before exceptional items and tax')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Profit / (Loss) before exceptional items and tax") }, format(d.re_pro_bef_int_n_excep));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Exceptional items')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Exceptional items") }, format(d.re_excepn_items_new));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars expenses" }, 'Profit / (Loss) before tax')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Profit / (Loss) before tax") }, format(d.re_pro_loss_bef_tax));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "taxExpenses" }, 'Tax Expenses')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Current Tax')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Current Tax") }, format(d.re_curr_tax));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Deferred Tax')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Deferred Tax") }, format(d.re_deff_tax));
            }))), tr(concatArr([{ class: "highlightRow" }], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Total Tax expense')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Total Tax expense") }, format(d.re_tax));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Net movement in regulatory deferral account balances related to profit or loss and the related deferred tax movement')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Net movement in regulatory deferral account balances related to profit or loss and the related deferred tax movement") }, format(d.re_net_mov_reg));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Profit (Loss) for the period from continuing operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Profit (Loss) for the period from continuing operations") }, format(d.re_proloss_ord_act));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Profit / (loss) from discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Profit / (loss) from discontinued operations") }, format(d.re_pro_los_frm_dis_opr));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Tax expense of discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Tax expense of discontinued operations") }, format(d.re_tax_expens_of_dis_opr));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Profit / (loss) from Discontinued operations (after tax)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Profit / (loss) from Discontinued operations (after tax)") }, format(d.re_prolos_dis_opr_aftr_tax));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Profit / (loss) for the period')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Profit / (loss) for the period") }, format(d.dis_opr_aftr_tax_plus_ord_act));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Share of profit / (loss) of associates')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Share of profit / (loss) of associates") }, format(d.re_share_associate));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Consolidated Net Profit / Loss for the period')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Consolidated Net Profit / Loss for the period") }, format(d.re_con_pro_loss));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Other comprehensive income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Other comprehensive income") }, format(d.re_oth_cmpr_incm));
            }))), tr(concatArr([{ class: "highlightRow" }], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars taxExpenses" }, 'Total comprehensive income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "taxExpenses", "Total comprehensive income") }, format(d.re_tot_cmpr_incm));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "totalProfitLoss" }, 'Total profit or loss, attributable to')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars totalProfitLoss" }, 'Profit or loss, attributable to owners of parent')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "totalProfitLoss", "Profit or loss, attributable to owners of parent") }, format(d.re_pl_own_par));
            }))), tr(concatArr([{ class: "highlightRow" }], [td({ width: '20%', headers: "quarterEnded particulars totalProfitLoss" }, 'Total profit or loss, attributable to non-controlling interests')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "totalProfitLoss", "Total profit or loss, attributable to non-controlling interests") }, format(d.re_tot_pl_nci));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "totalComprehensiveIncome" }, 'Total Comprehensive income for the period attributable to')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars totalComprehensiveIncome" }, 'Comprehensive income for the period attributable to owners of parent')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "totalProfitLoss", "Comprehensive income for the period attributable to owners of parent") }, format(d.re_com_ic));
            }))), tr(concatArr([{ class: "highlightRow" }], [td({ width: '20%', headers: "quarterEnded particulars totalComprehensiveIncome" }, 'Total comprehensive income for the period attributable to owners of parent non-controlling interests')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "totalProfitLoss", "Total comprehensive income for the period attributable to owners of parent non-controlling interests") }, format(d.re_tot_com_ic));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "detailsofEquityShareCapital" }, 'Details of equity share capital')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars detailsofEquityShareCapital" }, 'Paid-up equity share capital')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "detailsofEquityShareCapital", "Paid-up equity share capital") }, format(d.re_pdup));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars detailsofEquityShareCapital" }, 'Face Value(in Rs.)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "detailsofEquityShareCapital", "Face Value(in Rs.)") }, format(d.re_face_val));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "detailsofDebtSecurities" }, 'Details of debt securities')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars detailsofDebtSecurities" }, 'Paid-up debt capital')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "detailsofDebtSecurities", "Paid-up debt capital") }, format(d.re_paid_debt));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars detailsofDebtSecurities" }, 'Face value of debt securities (in Rs.)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "detailsofDebtSecurities", "Face value of debt securities (in Rs.)") }, format(d.re_face_value_debt));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars detailsofDebtSecurities" }, 'Reserve excluding Revaluation Reserves as per balance sheet of previous accounting year')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "detailsofDebtSecurities", "Reserve excluding Revaluation Reserves as per balance sheet of previous accounting year") }, format(d.re_res_reval));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars detailsofDebtSecurities" }, 'Debenture redemption reserve')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "detailsofDebtSecurities", "Debenture redemption reserve") }, format(d.re_debt_rdmption));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "earningsPerShare" }, 'Earnings per share')), tr(td({ "colspan": len, class: "sectionCol", id: "earningsPerEquityShareForContinuingOperations" }, 'Earnings per equity share for continuing operations')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShareForContinuingOperations" }, 'Basic EPS for continuing operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShareForContinuingOperations", "Basic EPS for continuing operations") }, format(d.re_bsc_eps_bfr_exi));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShareForContinuingOperations" }, 'Diluted EPS for continuing operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShareForContinuingOperations", "Diluted EPS for continuing operations") }, format(d.re_dil_eps_bfr_exi));
            }))), tr(td({ "colspan": len, class: "sectionCol", headers: "earningsPerEquityShareForDiscontinuedOperations" }, 'Earnings per equity share for discontinued operations')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShareForDiscontinuedOperations" }, 'Basic EPS for continued and discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShareForDiscontinuedOperations", "Basic EPS for continued and discontinued operations") }, format(d.re_basic_eps));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShareForDiscontinuedOperations" }, 'Diluted EPS for discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShareForDiscontinuedOperations", "Diluted EPS for discontinued operations") }, format(d.re_diluted_eps));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "earningsPerEquityShare" }, 'Earnings per equity share')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShare" }, 'Basic EPS for continued and discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShare", "Basic EPS for continued and discontinued operations") }, format(d.re_basic_eps_for_cont_dic_opr));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShare" }, 'Diluted EPS for continued and discontinued operations')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShare", "Diluted EPS for continued and discontinued operations") }, format(d.re_dilut_eps_for_cont_dic_opr));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShare" }, 'Debt equity ratio (in %)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShare", "Debt equity ratio (in %)") }, format(d.re_debt_eqt_rat));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShare" }, 'Debt service coverage ratio (in %)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShare", "Debt service coverage ratio (in %)") }, format(d.re_debt_ser_cov));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsPerEquityShare" }, 'Interest service coverage ratio (in %)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsPerEquityShare", "Interest service coverage ratio (in %)") }, format(d.re_int_ser_cov));
            })))
            /*tr(
                concatArr([{}],
                    [td(
                        'Disclosure of notes on financial results by banks'
                    )],
                    //data.map(d => td(format(d.re_desc_note_fin))),
                    data.map((d, t) => {
                            //return td(format(d.re_desc_note_fin))
                            let bodyContent;
                            const formatData = format(d.re_desc_note_fin);
                            if(formatData.length > 120){
                                let uniqueId = generateId();
                                const readMoreTxt = a({ class: "readMore"}, {
                                    on: {
                                        'click': (e) => {
                                            readMore('readMore'+uniqueId+t, t)
                                        }
                                    }
                                }, "Read More");
                                bodyContent = td({width:'20%'}, span({class:'content eclipse', id: 'readMore'+uniqueId+t},""), readMoreTxt);
                                bodyContent.args[2].elem.innerHTML = formatData.substr(0, 120)+'...';
                            }else{
                                bodyContent = td({},"");
                                bodyContent.elem.innerHTML = formatData;
                            }
                            return bodyContent;
                        }
                    ),
                )
            ),
            tr(
                concatArr([{}],
                    [td(
                        'Notes to Accounts '
                   )],
                    data.map(d => td(format(d.re_desc_note_seg)))
                )
            ),*/
            ));
        };
        var Format10 = function Format10(data) {
            var len = (data.length + 1).toString();
            if (data.length === 0) {
                return noData(true);
            }
            return table(_extends({}, attr.tableStyle), thead(tr(concatArr([{ class: "withborder" }], [th({ width: '20%', id: "quarterEnded" }, 'QUARTER ENDED')], data.map(function (d) {
                return th({ class: "text-right" }, d.re_to_dt);
            }))), tr(concatArr([{ class: "withborder" }], [th({ width: '20%', id: "particulars" }, 'PARTICULARS')], data.map(function (d) {
                return th({ class: "text-right" }, d.re_res_type === 'A' ? 'AUDITED' : 'UNAUDITED');
            })))), tbody(tr(td({ "colspan": len, class: "sectionCol", id: "interestEarned" }, 'Interest Earned')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars interestEarned" }, 'Interest/Discount on Advances/Bills')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "interestEarned", "Interest/Discount on Advances/Bills") }, format(d.re_int_dis_adv_bills));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars interestEarned" }, 'Income on Investments')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "interestEarned", "Income on Investments") }, format(d.re_income_inv));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars interestEarned" }, 'Interest on Balances With RBI & Other Inter bank Funds')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "interestEarned", "Interest on Balances With RBI & Other Inter bank Funds") }, format(d.re_bal_rbi_oth_bnk_funds));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars interestEarned" }, 'Others')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "interestEarned", "Others") }, format(d.re_oth));
            }))), tr(concatArr([{ class: "highlightRow" }], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars interestEarned" }, 'Total Interest Earned')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "interestEarned", "Total Interest Earned") }, format(d.re_int_earned));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars interestEarned" }, 'Other Income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "interestEarned", "Other Income") }, format(d.re_oth_inc));
            }))), tr(concatArr([{ class: "highlightRow" }], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars interestEarned" }, 'Total Income')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "interestEarned", "Total Income") }, format(d.re_tot_inc));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "expenses" }, 'Expenses')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Interest Expended')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Interest Expended") }, format(d.re_int_expd));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars expenses" }, 'Operating Expenses')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Operating Expenses") }, format(d.re_oper_exp));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Employees cost')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Employees cost") }, format(d.re_prov_emp_pay));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Other Operating Expenses')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Other Operating Expenses") }, format(d.re_oth_oper_exp));
            }))), tr(concatArr([{ class: "highlightRow" }], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars expenses" }, 'Total Expenditure (excluding provisions and contingencies)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Total Expenditure (excluding provisions and contingencies)") }, format(d.re_tot_exp_exc_pro_cont));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars expenses" }, 'Operating Profit before provisions and contingencies')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Operating Profit before provisions and contingencies") }, format(d.re_oper_exp_bef_pro_cont));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Provisions (other than tax) and contingencies')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Provisions (other than tax) and contingencies") }, format(d.re_oth_pro_cont));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Exceptional items')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Exceptional itemss") }, format(d.re_excepn_items));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars expenses" }, 'Profit/(Loss) from Ordinary Activities before tax')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Profit/(Loss) from Ordinary Activities before tax") }, format(d.re_pro_loss_bef_tax));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Tax Expense')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Tax Expense") }, format(d.re_tax));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars expenses" }, 'Net Profit/(Loss) from Ordinary Activities after tax')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Net Profit/(Loss) from Ordinary Activities after tax") }, format(d.re_proloss_ord_act));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Extraordinary Items (net of tax expense)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Extraordinary Items (net of tax expense)") }, format(d.re_extraord_items));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars expenses" }, 'Net Profit/(Loss) for the period')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Net Profit/(Loss) for the period") }, format(d.re_net_profit));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Minority Interest')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Minority Interest") }, format(d.re_minority_int));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars expenses" }, 'Shares of Associates')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Shares of Associates") }, format(d.re_share_associate));
            }))), tr(concatArr([{}], [td({ class: "text-bold", width: '20%', headers: "quarterEnded particulars expenses" }, 'Consolidated Net Profit / Loss for the period')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "expenses", "Consolidated Net Profit / Loss for the period") }, format(d.re_con_pro_loss));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "detailsofEequityShareCapital" }, 'Details of equity share capital')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars detailsofEequityShareCapital" }, 'Paid-up Equity Share Capital')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "detailsofEequityShareCapital", "Paid-up Equity Share Capital") }, format(d.re_pdup));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars detailsofEequityShareCapital" }, 'Face Value (in Rs.)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "detailsofEequityShareCapital", "Face Value (in Rs.)") }, format(d.re_face_val));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars detailsofEequityShareCapital" }, 'Reserves excluding Revaluation Reserves as per balance sheet of previous accounting year')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "detailsofEequityShareCapital", "Reserves excluding Revaluation Reserves as per balance sheet of previous accounting year") }, format(d.re_res_reval));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "analyticalRatios" }, 'Analytical Ratios')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars analyticalRatios" }, 'Percentage of shares Held by Government of India')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "analyticalRatios", "Percentage of shares Held by Government of India") }, format(d.re_goi_per_shhd));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "capitalAdequacyRatio" }, 'Capital Adequacy Ratio')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars capitalAdequacyRatio" }, 'CET 1 ratio (in %)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "capitalAdequacyRatio", "CET 1 ratio (in %)") }, format(d.re_cet_1_ret));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars capitalAdequacyRatio" }, 'Capital Adequacy Ratio (Basel III) (in %)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "capitalAdequacyRatio", "Capital Adequacy Ratio (Basel III) (in %)") }, format(d.re_cap_ade_rat));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "earningsShareBeforeExtraordinaryItems" }, 'Earnings per share before extraordinary items')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsShareBeforeExtraordinaryItems" }, 'Basic EPS after Extraordinary items (in Rs.)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsShareBeforeExtraordinaryItems", "Basic EPS after Extraordinary items (in Rs.)") }, format(d.re_bsc_eps_bfr_exi));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsShareBeforeExtraordinaryItems" }, 'Diluted EPS after Extraordinary items (in Rs.)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsShareBeforeExtraordinaryItems", "Diluted EPS after Extraordinary items (in Rs.)") }, format(d.re_dil_eps_bfr_exi));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "earningsShareAfterExtraordinaryItems" }, 'Earnings per share after extraordinary items')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsShareAfterExtraordinaryItems" }, 'Basic EPS after Extraordinary items (in Rs.) ')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsShareAfterExtraordinaryItems", "Basic EPS after Extraordinary items (in Rs.)") }, format(d.re_basic_eps));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars earningsShareAfterExtraordinaryItems" }, 'Diluted EPS after Extraordinary items (in Rs.)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "earningsShareAfterExtraordinaryItems", "Diluted EPS after Extraordinary items (in Rs.)") }, format(d.re_diluted_eps));
            }))), tr(td({ "colspan": len, class: "sectionCol", id: "NPARatios" }, 'NPA Ratios')), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars NPARatios" }, 'Amount of gross non-performing assets')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "NPARatios", "Amount of gross non-performing assets") }, format(d.re_amt_grs_np_asst));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars NPARatios" }, 'Amount of net non-performing assets')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "NPARatios", "Amount of net non-performing assets") }, format(d.re_grs_npa));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars NPARatios" }, '% of gross NPAs')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "NPARatios", "% of gross NPAs") }, format(d.re_per_grs_npa));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars NPARatios" }, '% of Net NPA')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "NPARatios", "% of Net NPA") }, format(d.re_grs_npa_per));
            }))), tr(concatArr([{}], [td({ width: '20%', headers: "quarterEnded particulars NPARatios" }, 'Return on Assets (in %)')], data.map(function (d) {
                return td({ class: "text-right", headers: getAriaHeader(d.re_to_dt, d.re_res_type, "NPARatios", "Return on Assets (in %)") }, format(d.re_ret_asset));
            })))
            /*tr(
                concatArr([{}],
                    [td({width : '20%'},'Disclosure of notes on financial results by banks')],
                    //data.map(d => td({width : '20%'},format(d.re_desc_note_fin)))
                    data.map((d, t) => {
                            //return td(format(d.re_desc_note_fin))
                            let bodyContent;
                            const formatData = format(d.re_desc_note_fin);
                            if(formatData.length > 120){
                                let uniqueId = generateId();
                                const readMoreTxt = a({ class: "readMore"}, {
                                    on: {
                                        'click': (e) => {
                                            readMore('readMore'+uniqueId+t, t)
                                        }
                                    }
                                }, "Read More");
                                bodyContent = td({width:'20%'}, span({class:'content eclipse', id: 'readMore'+uniqueId+t},""), readMoreTxt);
                                bodyContent.args[2].elem.innerHTML = formatData.substr(0, 120)+'...';
                            }else{
                                bodyContent = td({},"");
                                bodyContent.elem.innerHTML = formatData;
                            }
                            return bodyContent;
                        }
                    )
                )
            ),
            tr(
                concatArr([{}],
                    [td({width : '20%'},'Notes to Accounts')],
                    data.map(d => td({width : '20%'},a({href: d.attachment_filename}, (d.attachment_filename ? 'click here' : '-'))))
                )
            ),*/
            ));
        };

        var dom = div({ class: "" }, div({ class: "customTable-widthCorp tableScroll financialComTable",
            onStateChange: {
                state: _this.state, obj: 'data', onChange: function onChange(e, v) {
                    e.empty();
                    var table = noData();
                    if (_this.state.data.hasOwnProperty('resCmpData')) {
                        if (_this.state.data.bankNonBnking === 'B') {
                            table = Format10(_this.state.data.resCmpData);
                        } else if (_this.state.data.bankNonBnking === 'N') {
                            table = Format11(_this.state.data.resCmpData);
                        } else if (_this.state.data.bankNonBnking === 'F') {
                            table = Format14(_this.state.data.resCmpData);
                        }
                    }
                    B.renderAll([table], e);
                }
            }
        }));
        //mandatory code for a BlinkUI component
        _this.args = dom.args;
        _this.elem = dom.elem;
        _this.elem.cmp = _this;
        //mandatory code for a BlinkUI component ends
        return _this;
    }

    return ResultsComparison;
}(BlinkElement);

instantiate('ResultsComparison', ResultsComparison);