# -*- coding: utf-8 -*-
# © 2016 Opener B.V. (<https://opener.am>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

#from openerp import models
from odoo import api, models
import logging
_logger = logging.getLogger(__name__)


class Base(models.AbstractModel):
    _inherit = 'base'

    def user_has_groups(self, groups):
        """ Return True for users in the technical features group when
        membership of the original group is checked, even if debug mode
        is not enabled.
        """
        if ('base.group_no_one' in groups.split(',') and
                self.env.user.has_group(
                    'cq_technical_features.group_technical_features')):
            return True
        return super(Base, self).user_has_groups(groups)


#// Inibito "Importa" sia da vista che da python) per gli utenti che non appartengono
#// che non appartengono al gruppo Importazione di file CSV.
# Estratto dal modulo https://github.com/OCA/server-tools/tree/10.0/base_import_security_group
    @api.model
    def load(self, fields, data):
        '''Overriding this method we only allow its execution
        if current user belongs to the group allowed for CSV data import.
        An exception is raised otherwise, and also log the import attempt.
        '''
        current_user = self.env.user
        allowed_group = 'cq_technical_features.group_import_csv'
        allowed_group_id = self.env.ref(
            allowed_group,
            raise_if_not_found=False
        )
        if not allowed_group_id or current_user.has_group(allowed_group):
            res = super(Base, self).load(fields=fields, data=data)
        else:
            msg = ('User (ID: %s) is not allowed to import data '
                   'in model %s.') % (self.env.uid, self._name)
            _logger.info(msg)
            messages = []
            info = {}
            messages.append(
                dict(info, type='error', message=msg, moreinfo=None))
            res = {'ids': None, 'messages': messages}
        return res
