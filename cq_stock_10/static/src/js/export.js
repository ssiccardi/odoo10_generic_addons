odoo.define('cq_stock_10', function (require) {
"use strict";

    var core = require('web.core');
    var ListView = require('web.ListView');
    var QWeb = core.qweb;

    var _t = core._t;

    ListView.include({

        render_buttons: function($node) {
            var ViewManager = this.ViewManager;
            this._super($node);
            if (ViewManager.active_view.type == 'list' && ViewManager.action.name == 'Margini Fornitori') {
                $node.append(QWeb.render('AddExportViewMainMargini'));
                $node.find('.o_sidebar_export_margini_xls').on('click', this.on_sidebar_export_margini_xls);
                if (this.dataset._model._context && this.dataset._model._context.search_default_lotgroup) {
                    $node.find('.o_sidebar_export_margini_xls_lots').on('click', this.on_sidebar_export_margini_xls_lots);
                }
                else {
                    $node.find('.o_sidebar_export_margini_xls_lots').css('display', 'none');
                }
            }
            if (ViewManager.active_view.type == 'list' && ViewManager.action.res_model == "stock.history") {
                $node.append(QWeb.render('AddExportStockHistory'));
                $node.find('.o_sidebar_stock_history_xls').on('click', this.on_sidebar_stock_history_xls);
                if (this.dataset._model._context && this.dataset._model._context.export_group_by_lot) {
                    $node.find('.o_sidebar_stock_history_xls_lots').on('click', this.on_sidebar_stock_history_xls_lots);
                }
                else {
                    $node.find('.o_sidebar_stock_history_xls_lots').css('display', 'none');
                }
            }
        },

        on_sidebar_export_margini_xls: function () {
            $.blockUI();
            this.session.get_file({
                url: '/cq_stock_10/exportmargini',
                data: {data: JSON.stringify({
                    domain: this.dataset._model._domain,
                    context: this.dataset.context || this.dataset._model._context,
                })},                
                complete: $.unblockUI
            });
        },

        on_sidebar_stock_history_xls: function () {
            $.blockUI();
            this.session.get_file({
                url: '/cq_stock_10/exportstockhistory',
                data: {data: JSON.stringify({
                    domain: this.dataset._model._domain,
                    context: this.dataset.context || this.dataset._model._context,
                })},                
                complete: $.unblockUI
            });
        },

        on_sidebar_export_margini_xls_lots: function () {
            $.blockUI();
            this.session.get_file({
                url: '/cq_stock_10/exportmargini',
                data: {data: JSON.stringify({
                    lotgruped: true,
                    domain: this.dataset._model._domain,
                    context: this.dataset.context || this.dataset._model._context,
                })},                
                complete: $.unblockUI
            });
        },

        on_sidebar_stock_history_xls_lots: function () {
            $.blockUI();
            this.session.get_file({
                url: '/cq_stock_10/exportstockhistory',
                data: {data: JSON.stringify({
                    lotgruped: true,
                    domain: this.dataset._model._domain,
                    context: this.dataset.context || this.dataset._model._context,
                })},                
                complete: $.unblockUI
            });
        },

    });

});
