'use strict';

B.on(document, 'allGood', function () {
    var cfcRefreshEl = document.getElementById('refreshHndlBtnFRFinEqu');
    if (cfcRefreshEl) {
        cfcRefreshEl.addEventListener('click', function (e) {
            e.preventDefault();
            CFRefresh('CFfinancialequity');
        });
    }

    var cfcRefreshEl2 = document.getElementById('refreshHndlBtnFRFinDebt');
    if (cfcRefreshEl2) {
        cfcRefreshEl2.addEventListener('click', function (e) {
            e.preventDefault();
            CFRefresh('CFfinancialdebt');
        });
    }

    var cfcRefreshEl3 = document.getElementById('refreshHndlBtnFRFinSME');
    if (cfcRefreshEl3) {
        cfcRefreshEl3.addEventListener('click', function (e) {
            e.preventDefault();
            CFRefresh('CFfinancialsme');
        });
    }

    var cfcRefreshEl4 = document.getElementById('refreshHndlBtnFRFinIns');
    if (cfcRefreshEl4) {
        cfcRefreshEl4.addEventListener('click', function (e) {
            e.preventDefault();
            CFRefresh('CFfinancialinsurance');
        });
    }

    var cfcRefreshEl5 = document.getElementById('refreshHndlBtnFRInvtReit');
    if (cfcRefreshEl5) {
        cfcRefreshEl5.addEventListener('click', function (e) {
            e.preventDefault();
            CFRefresh('CFfinancialinvitsreits');
        });
    }

    var closeFrPopEl = document.getElementById('closeFRPopEl');
    if (closeFrPopEl) {
        closeFrPopEl.addEventListener('click', function (e) {
            e.preventDefault();
            closeFRPopup();
        });
    }
    var downloadButtons = [{
        id: 'CFfinancialequity-download', handler: function handler(e) {
            e.preventDefault();
            downloadCSV('CFfinancialequity-download');
        }
    }, {
        id: 'CFfinancialdebt-download', handler: function handler(e) {
            e.preventDefault();
            downloadCSV('CFfinancialdebt-download');
        }
    }, {
        id: 'CFfinancialsme-download', handler: function handler(e) {
            e.preventDefault();
            downloadCSV('CFfinancialsme-download');
        }
    }, {
        id: 'CFfinancialinsurance-download', handler: function handler(e) {
            e.preventDefault();
            downloadCSV('CFfinancialinsurance-download');
        }
    }, {
        id: 'CFfinancialinvitsreits-download', handler: function handler(e) {
            e.preventDefault();
            downloadCSV('CFfinancialinvitsreits-download');
        }
    }];

    downloadButtons.forEach(function (btn) {
        var element = document.getElementById(btn.id);
        if (element) {
            element.addEventListener('click', btn.handler);
        }
    });
});