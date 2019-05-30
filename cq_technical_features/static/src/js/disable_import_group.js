/* 
  Inibito "Importa" (sia da vista che da python) per gli utenti
  che non appartengono al gruppo Importazione di file CSV.
  Estratto dal modulo https://github.com/OCA/server-tools/tree/10.0/base_import_security_group
*/
odoo.define('web.ListImport', function (require) {
    "use strict";
    var core = require('web.core');
    var ListView = require('web.ListView');
    var Model = require('web.Model');

    ListView.prototype.defaults.import_enabled = false;
    ListView.include(/** @lends instance.web.ListView# */{

        load_list: function (data, grouped) {

            var self = this;
            var Users = new Model('res.users');

            var result = this._super.apply(this, arguments);
            Users.call('has_group', ['cq_technical_features.group_import_csv'])
                .then(function (result) {
                    var import_enabled = result;
                    self.options.import_enabled = import_enabled;

                    if (import_enabled === false) {
                        if (self.$buttons) {
                            self.$buttons.find('.o_button_import').remove();
                        }
                    }
                });
            return result;
        }
    });
});
