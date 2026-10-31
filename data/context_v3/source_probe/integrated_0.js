B.on(document, 'allGood', function () {
    const navigationButtons = [
        {
            id: 'first1', handler: function (e) {
                e.preventDefault();
                onFirstClickIntegratedEQ();
            }
        },
        {
            id: 'prev1', handler: function (e) {
                e.preventDefault();
                onPrevClickIntegratedEQ();
            }
        },
        {
            id: 'next1', handler: function (e) {
                e.preventDefault();
                onNextClickIntegratedEQ();
            }
        },
        {
            id: 'last1', handler: function (e) {
                e.preventDefault();
                onLastClickIntegratedEQ();
            }
        },
        {
            id: 'first', handler: function (e) {
                e.preventDefault();
                onFirstClickIntegratedEQ();
            }
        },
        {
            id: 'prev', handler: function (e) {
                e.preventDefault();
                onPrevClickIntegratedEQ();
            }
        },
        {
            id: 'next', handler: function (e) {
                e.preventDefault();
                onNextClickIntegratedEQ();
            }
        },
        {
            id: 'last', handler: function (e) {
                e.preventDefault();
                onLastClickIntegratedEQ();
            }
        },



        {
            id: 'first3', handler: function (e) {
                e.preventDefault();
                onFirstClickIntegratedEQ();
            }
        },
        {
            id: 'prev3', handler: function (e) {
                e.preventDefault();
                onPrevClickIntegratedEQ();
            }
        },
        {
            id: 'next3', handler: function (e) {
                e.preventDefault();
                onNextClickIntegratedEQ();
            }
        },
        {
            id: 'last3', handler: function (e) {
                e.preventDefault();
                onLastClickIntegratedEQ();
            }
        },
        {
            id: 'first4', handler: function (e) {
                e.preventDefault();
                onFirstClickIntegratedEQ();
            }
        },
        {
            id: 'prev4', handler: function (e) {
                e.preventDefault();
                onPrevClickIntegratedEQ();
            }
        },
        {
            id: 'next4', handler: function (e) {
                e.preventDefault();
                onNextClickIntegratedEQ();
            }
        },
        {
            id: 'last4', handler: function (e) {
                e.preventDefault();
                onLastClickIntegratedEQ();
            }
        },
    ];

    navigationButtons.forEach(function (btn) {
        const element = document.getElementById(btn.id);
        if (element) {
            element.addEventListener('click', btn.handler);
        }
    });

    const cfcRefreshEl = document.getElementById('cfcRefreshHndlBtnCR1');
    if (cfcRefreshEl) {
        cfcRefreshEl.addEventListener('click', (e) => {
            e.preventDefault();
            CFRefresh('CFintegratedfiling')
        });
    }

    const cfcRefreshE2 = document.getElementById('cfcRefreshHndlBtnCR2');
    if (cfcRefreshE2) {
        cfcRefreshE2.addEventListener('click', (e) => {
            e.preventDefault();
            CFRefresh('CFintegratedfilingSME')
        });
    }


    const CFintegratedfilingDownload = document.getElementById('CFintegratedfiling-download');
    if (CFintegratedfilingDownload) {
        CFintegratedfilingDownload.addEventListener('click', (e) => {
            e.preventDefault();
            downloadCSV('CFintegratedfiling-download');
        });
    }

    const CFintegratedfilingSMEDownload = document.getElementById('CFintegratedfilingSME-download');
    if (CFintegratedfilingSMEDownload) {
        CFintegratedfilingSMEDownload.addEventListener('click', (e) => {
            e.preventDefault();
            downloadCSV('CFintegratedfilingSME-download');
        });
    }
})