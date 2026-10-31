'use strict';

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _possibleConstructorReturn(self, call) { if (!self) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return call && (typeof call === "object" || typeof call === "function") ? call : self; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function, not " + typeof superClass); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, enumerable: false, writable: true, configurable: true } }); if (superClass) Object.setPrototypeOf ? Object.setPrototypeOf(subClass, superClass) : subClass.__proto__ = superClass; }

var ShareHolderPatternTable = function (_BlinkElement) {
    _inherits(ShareHolderPatternTable, _BlinkElement);

    function ShareHolderPatternTable(args) {
        _classCallCheck(this, ShareHolderPatternTable);

        var _this = _possibleConstructorReturn(this, _BlinkElement.call(this));

        var attr = B.extractArgAttrs(args);
        _this.state = new B.State({
            colData: attr.colData || [],
            rowData: attr.rowData || [],
            grpData: attr.grpData || false,
            grpMeta: attr.grpMeta || {},
            hoverColData: attr.hoverData || []
        });
        var attachmentList = ['attachment', 'action', 'vrxbrlfilename', 'xbrl', 'txbrl file link', 'xbrl file link'];

        var getAriaHeader = function getAriaHeader(value, rowData) {
            var grpData = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : false;

            try {
                var ariaHeadVal = value || '-';
                if (ariaHeadVal.indexOf(':') >= 0) {
                    var headerSplitVal = ariaHeadVal.split(':');
                    var dynamicVal = rowData[headerSplitVal[1]];
                    ariaHeadVal = '' + headerSplitVal[0] + dynamicVal + headerSplitVal[2];
                }
                if (grpData) {
                    ariaHeadVal = (rowData.key || "") + ' - ' + ariaHeadVal;
                }
                return ariaHeadVal;
            } catch (e) {
                console.log(e);
                return '-';
            }
        };

        var dom = tbody({
            onStateChange: {
                state: _this.state, obj: 'rowData', onChange: function onChange(e, v) {
                    e.empty();
                    var rows = [];
                    if (_this.state.rowData.length > 0) {
                        if (_this.state.rowData[0] && _this.state.rowData[0].isloading) {
                            rows.push(tr(td({
                                colspan: _this.state.colData.length,
                                class: "text-center emptyRow"
                            }, div({ class: "loader-wrp" }, div({ class: "spin-loader", "aria-hidden": "true" })))));
                        } else {
                            _this.state.rowData.forEach(function (row, t) {
                                var rowDomObj = void 0;
                                rowDomObj = tr(concatArr([{}], _this.state.colData.map(function (col, index) {
                                    if (col.name && col.name === "name") {
                                        return td({ width: col.width, headers: getAriaHeader(col && col.ariaHeader && col.ariaHeader, row, _this.state.grpData) }, a({
                                            href: "#",
                                            on: {
                                                'click': function click(e) {
                                                    shareHolderPopup("#shareholding_modal", row['symbol'], row['name'], row['recordId'], row);
                                                }
                                            }
                                        }, row[col.name]));
                                    }
                                    if (col.name === "broadcastDate") {
                                        return td({ width: col.width, class: "text-center" }, a({ href: "#", class: "show_link" }, row[col.name] || "-", div({ class: "hover_table" }, HoverTable({
                                            tableStyle: { width: "100%" },
                                            colData: _this.state.hoverColData || [],
                                            rowData: row || [],
                                            isHover: true
                                        }))));
                                    }
                                    if (col.name !== "today" && typeof row[col.name] === "undefined" || row[col.name] === null || row[col.name] === "-") {
                                        //|| parseFloat(row[col.name]) === 0
                                        return td({ width: col.width, class: 'text-center', headers: getAriaHeader(col && col.ariaHeader && col.ariaHeader, row, _this.state.grpData) }, "-");
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
                                    if (col.format === "number" || col.type === "quantity" || col.format === "quantity" || col.format === "currNumber" || col.align === "right") {
                                        className = col.isBold ? "bold text-right" : "text-right";
                                    }
                                    var columnVal = typeof nestedObjVal === "undefined" ? row[col.name] : nestedObjVal;

                                    if (col.format === "quantity") {
                                        var val = parseFloat(columnVal);
                                        var _dividedBy = col.valueTyp && col.valueTyp !== null ? parseInt(col.valueTyp) : 1;
                                        formatData = DecimalFixed(val / _dividedBy, true);
                                    } else if (col.format === "number") {
                                        var _val = parseFloat(columnVal);
                                        var _dividedBy2 = col.valueTyp && col.valueTyp !== null ? parseInt(col.valueTyp) : 1;
                                        formatData = DecimalFixed(_val / _dividedBy2).toString();
                                    }
                                    if (col.type === "attachment") {
                                        var fileExtension = row[col.name].trim().match(/(\.\w+)$/g);
                                        fileExtension = fileExtension && fileExtension.length > 0 ? fileExtension[0] : fileExtension;
                                        if (fileExtension) {
                                            var fileIconPath = getFileIconPath(fileExtension);
                                            return td({ width: col.width, class: 'text-center', headers: getAriaHeader(col && col.ariaHeader && col.ariaHeader, row, _this.state.grpData) }, a({ href: row[col.name].toString(), target: row[col.name].substr(row[col.name].length - 4) === ".xml" ? "" : "_blank", 'aria-label': row[col.title] + ' ATTACHMENT', title: row[col.title] + ' ATTACHMENT' }, {
                                                on: {
                                                    'click': function click(e) {
                                                        downloadXBRL(row[col.name].toString(), e);
                                                    }
                                                }
                                            }, img({ src: fileIconPath, alt: row[col.title] + ' ATTACHMENT', height: "22", width: "18" }, "")), p({ class: 'mt-1' }, fileSizeRender(col.fileSizeKey, row)));
                                        } else {
                                            return td({ width: col.width, class: 'text-center' }, "-");
                                        }
                                    } else {
                                        return td({ width: col.width, class: className, headers: getAriaHeader(col && col.ariaHeader && col.ariaHeader, row, _this.state.grpData) }, formatData);
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
        });
        //mandatory code for a BlinkUI component
        _this.args = dom.args;
        _this.elem = dom.elem;
        _this.elem.cmp = _this;
        //mandatory code for a BlinkUI component ends
        return _this;
    }

    return ShareHolderPatternTable;
}(BlinkElement);

instantiate('ShareHolderPatternTable', ShareHolderPatternTable);