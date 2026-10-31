'use strict';

var _extends = Object.assign || function (target) { for (var i = 1; i < arguments.length; i++) { var source = arguments[i]; for (var key in source) { if (Object.prototype.hasOwnProperty.call(source, key)) { target[key] = source[key]; } } } return target; };

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var CorporateGovernance = function (_BlinkElement) {
    _inherits(CorporateGovernance, _BlinkElement);

    function CorporateGovernance(args) {
        _classCallCheck(this, CorporateGovernance);

        var _this = _possibleConstructorReturn(this, _BlinkElement.call(this));

        var attr = B.extractArgAttrs(args);
        _this.state = new B.State({
            colData: attr.colData || [],
            rowData: attr.rowData || [],
            hoverColData: attr.hoverData || [],
            hoverRevColData: attr.hoverRevData || []
        });
        var tableHead = "";
        var attachmentList = ['attachment', 'action', 'vrxbrlfilename', 'xbrl', 'txbrl file link', 'xbrl file link'];
        var quoteEquityDerivativeLink = ['FUTSTK', 'OPTSTK'];
        var quoteIndicesDerivativeLink = ['FUTIDX', 'OPTIDX'];
        var commodityLink = ['contract'];
        var commodityType = ['FUTBLN', 'FUTENR', 'FUTAGR', 'FUTBAS', 'OPTBAS', 'Bullion Futures', 'Energy Futures', 'Agri Futures', 'Base Metal Futures', 'Base Metal Options'];
        var currencyType = ["FUTCUR", "OPTCUR", "Currency Futures", "Currency Options"];
        var IRF = ["FUTIRT", "FUTIRC", "OPTIRC", "Interest Rate Futures"];
        var ltpName = ["lastprice", "ltp", "lastPrice", "ltpDIff", "ltpdiff"];

        var sortBy = function sortBy(key, id, condt, type) {
            sortType = sortType === "asc" ? "desc" : "asc";
            if (tableHead !== key) {
                sortType = "asc";
            }
            var els = document.querySelectorAll('.toggleIcon');
            for (var i = 0; i < els.length; i++) {
                els[i].classList.remove("asc", "desc");
                els[i].parentNode.setAttribute('aria-sort', 'none');
            }
            if (condt !== null) {
                document.getElementById(condt).classList.add(sortType);
                document.getElementById(condt).parentNode.setAttribute('aria-sort', sortType === 'asc' ? 'ascending' : 'descending');
            }

            var rowSortData = _this.state.rowData.sort(sortTable(key, sortType, type));
            tableHead = key;
            _this.state.rowData = rowSortData;
        };

        var sortTable = function sortTable(key, order, type) {
            return function (a, b) {
                if (b.priority > 0 || a.priority > 0) {
                    return 0;
                }
                if (!a.hasOwnProperty(key) || !b.hasOwnProperty(key)) {
                    return 0;
                }

                var varA = void 0,
                    varB = void 0;

                if (type === "date") {
                    var month = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
                    var defaultDate = "01-JAN-1900";
                    var aVal = a[key] === "-" ? defaultDate.split('-') : a[key].split('-');
                    var bVal = b[key] === "-" ? defaultDate.split('-') : b[key].split('-');

                    if (aVal[1].length > 2) {
                        aVal[1] = (month.indexOf(aVal[1].toUpperCase()) + 1).toString();
                    }
                    if (bVal[1].length > 2) {
                        bVal[1] = (month.indexOf(bVal[1].toUpperCase()) + 1).toString();
                    }

                    varA = new Date(aVal.reverse().join('-'));
                    varB = new Date(bVal.reverse().join('-'));
                } else {
                    varA = typeof a[key] === 'string' ? type === "number" || type === "quantity" ? parseFloat(a[key]) : a[key].toUpperCase() : a[key];
                    varB = typeof b[key] === 'string' ? type === "number" || type === "quantity" ? parseFloat(b[key]) : b[key].toUpperCase() : b[key];
                }

                var comparison = 0;
                if (varA > varB) {
                    comparison = 1;
                } else if (varA < varB) {
                    comparison = -1;
                }
                return order === 'desc' ? comparison * -1 : comparison;
            };
        };
        var tableId = _extends({}, attr.tableStyle);
        var dom = table(tableId, thead(tr({
            onStateChange: {
                state: _this.state, obj: 'colData', onChange: function onChange(e, v) {
                    e.empty();
                    var tableHeader = _this.state.colData.map(function (col, index) {
                        if (col.sort) {
                            var indexname = (tableId.id + "col" || "orderList") + index;
                            var headContent = th({
                                width: col.width, title: col.legend && col.legend, role: 'columnheader', 'aria-sort': "none" }, a({ "class": "toggleIcon", id: indexname, href: "#" }, {
                                on: {
                                    'click': function click(e) {
                                        e.preventDefault();
                                        sortBy(col.name, index, indexname, col.format || col.type);
                                    }
                                }
                            }, ""));
                            var subHeadContent = col.subHead !== "" ? '<span>' + col.subHead + '</span>' : "";
                            headContent.elem.children[0].innerHTML = col.heading + subHeadContent || '';
                            return headContent;
                        } else {
                            return th({ width: col.width }, col.heading || '', col.subHead !== "" ? span({}, col.subHead) : "");
                        }
                    });
                    B.renderAll(tableHeader, e);
                }
            }
        })), tbody({
            onStateChange: {
                state: _this.state, obj: 'rowData', onChange: function onChange(e, v) {
                    e.empty();
                    var rows = [];
                    if (_this.state.rowData.length > 0) {
                        if (_this.state.rowData[0] && _this.state.rowData[0].isloading) {
                            rows.push(tr(td({ colspan: _this.state.colData.length, class: 'text-center emptyRow' }, div({ "class": "loader-wrp" }, div({ "class": "spin-loader", "aria-hidden": "true" })))));
                        } else {
                            _this.state.rowData.forEach(function (row, t) {
                                var rowDomObj = void 0;
                                rowDomObj = tr(concatArr([{}], _this.state.colData.map(function (col, index) {
                                    if (col.name === "link") {
                                        return td({ width: col.width }, a({
                                            href: "#",
                                            on: {
                                                'click': function click(e) {
                                                    e.preventDefault();
                                                    showPopup("#Corp_Governance_modal", row['symbol'], row['name'], row['recordId'], row);
                                                }
                                            }
                                        }, "Details"), p({ class: 'mt-1' }, fileSizeRender(col.fileSizeKey, row)));
                                    }
                                    if (col.name === "cgTimeStamp" && row[col.name]) {
                                        return td({ width: col.width, class: "text-center" }, a({ href: "#", class: "show_link" }, row[col.name] || "-", div({ class: "hover_table" }, HoverTable({
                                            tableStyle: { width: "100%" },
                                            colData: _this.state.hoverColData || [],
                                            rowData: row || [],
                                            isHover: true
                                        }))));
                                    }
                                    if (col.name === "revisedDate" && row[col.name]) {
                                        return td({ width: col.width, class: "text-center" }, a({ href: "#", class: "show_link" }, row[col.name] || "-", div({ class: "hover_table" }, HoverTable({
                                            tableStyle: { width: "100%" },
                                            colData: _this.state.hoverRevColData || [],
                                            rowData: row || [],
                                            isHover: true
                                        }))));
                                    }
                                    if (col.name !== "today" && typeof row[col.name] === "undefined" || row[col.name] === null || row[col.name] === "-" /*|| parseFloat(row[col.name]) === 0*/) {
                                            return td({ width: col.width, class: 'text-center' }, "-");
                                        }
                                    var formatData = "";
                                    var className = "";
                                    if (typeof row[col.name] === "number") {
                                        className = "text-right";
                                        if (col.valueTyp && col.valueTyp !== null) {
                                            var dividedBy = parseInt(col.valueTyp);
                                            formatData = DecimalFixed(row[col.name] / dividedBy).toString();
                                        } else {
                                            formatData = DecimalFixed(row[col.name]).toString();
                                        }
                                    } else {
                                        if (col.name !== "today") {
                                            formatData = row[col.name].toString();
                                        }
                                    }
                                    if (col.type === "attachment") {
                                        var fileExtension = row[col.name].trim().match(/(\.\w+)$/g);
                                        fileExtension = fileExtension && fileExtension.length > 0 ? fileExtension[0] : fileExtension;
                                        if (fileExtension) {
                                            var fileIconPath = getFileIconPath(fileExtension);
                                            return td({
                                                width: col.width,
                                                class: 'text-center'
                                            }, a({
                                                href: row[col.name].toString(),
                                                target: row[col.name].substr(row[col.name].length - 4) === ".xml" ? "" : "_blank",
                                                "aria-label": row[col.title] + ' ATTACHMENT',
                                                title: row[col.title] + ' ATTACHMENT'
                                            }, {
                                                on: {
                                                    'click': function click(e) {
                                                        downloadXBRL(row[col.name].toString(), e);
                                                    }
                                                }
                                            }, img({ src: fileIconPath, alt: row[col.title] + ' ATTACHMENT', height: "22", width: "18" }, "")), p({ class: 'mt-1' }, fileSizeRender(col.fileSizeKey, row)));
                                        } else {
                                            return td({ width: col.width, class: 'text-center' }, "-");
                                        }
                                    }if (col.heading.toLowerCase() === "symbol" && row['priority'] !== 1) {
                                        if (IRF.indexOf(row["instrument"]) !== -1 || IRF.indexOf(row["instrumentType"]) !== -1) {
                                            return td({ width: col.width }, a({
                                                href: "/interest-rate-future-getquote?symbol=" + encodeURIComponent(row[col.name]) + "&identifier=" + row.identifier,
                                                target: "_blank"
                                            }, row[col.name]));
                                        } else if (quoteEquityDerivativeLink.indexOf(row["instrumentType"]) !== -1) {
                                            return td({ width: col.width }, a({
                                                href: "/get-quotes/derivatives?symbol=" + encodeURIComponent(row[col.name]) + "&identifier=" + encodeURIComponent(row.identifier),
                                                target: "_blank"
                                            }, row[col.name]));
                                        } else if (quoteIndicesDerivativeLink.indexOf(row["instrumentType"]) !== -1) {
                                            return td({ width: col.width }, a({
                                                href: "/get-quotes/derivatives?symbol=" + encodeURIComponent(row[col.name]) + "&identifier=" + encodeURIComponent(row.identifier),
                                                target: "_blank"
                                            }, row[col.name]));
                                        } else if (currencyType.indexOf(row["instrumentType"]) !== -1) {
                                            return td({ width: col.width }, a({
                                                href: "/currency-getquote?identifier=" + encodeURIComponent(row['identifier']),
                                                target: "_blank"
                                            }, row[col.name]));
                                        } else if (commodityType.indexOf(row["instrumentType"]) !== -1) {
                                            return td({ width: col.width }, a({
                                                href: "/commodity-getquote?symbol=" + encodeURIComponent(row[col.name]) + "&expiryDate=" + encodeURIComponent(row.expiryDate) + "&instrumentType=" + encodeURIComponent(row.instrumentType),
                                                target: "_blank"
                                            }, row[col.name]));
                                        } else {
                                            if (col.quoteType && col.quoteType === bondsKey) {
                                                return td({ width: col.width }, a({
                                                    href: '/get-quotes/' + col.quoteType + '?symbol=' + encodeURIComponent(row[col.name]) + '&series=' + encodeURIComponent(row['series']) + '&maturityDate=' + encodeURIComponent(row['maturity_date']),
                                                    target: "_blank"
                                                }, row[col.name]));
                                            }
                                            return td({ width: col.width }, a({
                                                href: "/get-quotes/" + (col.quoteType || getEquityType(row.meta)) + "?symbol=" + encodeURIComponent(row[col.name]),
                                                target: "_blank"
                                            }, row[col.name]));
                                        }
                                    } else {
                                        return td({ width: col.width, class: className }, formatData);
                                    }
                                })));
                                rows.push(rowDomObj);
                            });
                        }
                    } else {
                        rows.push(tr(td({ colspan: _this.state.colData.length, class: 'text-center emptyRow' }, 'No Records')));
                    }
                    B.renderAll(rows, e);
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

    return CorporateGovernance;
}(BlinkElement);

instantiate('CorporateGovernance', CorporateGovernance);