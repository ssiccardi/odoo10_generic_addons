/* 
  Inibito "Esporta" per gli utenti che non appartengono al gruppo Importazione di file CSV.
  Estratto dal modulo https://github.com/onesteinbv/addons-onestein/tree/10.0/web_disable_export_group
*/
odoo.define("web_disable_export_group", function(require) {
"use strict";

    var core = require("web.core");
    var Sidebar = require("web.Sidebar");
    var _t = core._t;
    var Model = require("web.Model");
    var session = require("web.session");

    Sidebar.include({
        add_items: function(section_code, items) {
            var self = this;
            var _super = this._super;
            // Uncomment the code block below in order to allow superuser always viewing export button,
            // no matter whether it belongs to group_export_csv user group or not.
            /*if (session.is_superuser) {
                _super.apply(this, arguments);
            } else {*/
            var Users = new Model("res.users");
            Users.call("has_group", ["cq_technical_features.group_export_csv"]).done(function(can_export) {
                if (!can_export) {
                    var export_label = _t("Export");
                    var new_items = items;
                    if (section_code === "other") {
                        new_items = [];
                        for (var i = 0; i < items.length; i++) {
                            console.log("items[i]: ", items[i]);
                            if (items[i]["label"] !== export_label) {
                                new_items.push(items[i]);
                            }
                        }
                    }
                    if (new_items.length > 0) {
                        _super.call(self, section_code, new_items);
                    }
                } else {
                    _super.call(self, section_code, items);
                }
            });
            //}

        }
    });
});
