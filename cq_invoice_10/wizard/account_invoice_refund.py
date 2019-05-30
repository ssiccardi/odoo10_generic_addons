# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2017 CQ Creativi Quadrati www.creativiquadrati.it
#
#    License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
#
##############################################################################

from odoo import models, fields, api, _
from odoo.tools.safe_eval import safe_eval
from odoo.exceptions import UserError


class AccountInvoiceRefund(models.TransientModel):

    _inherit = "account.invoice.refund"


#// Bottone Crea Nota Credito dalle fatture: la vista lista di ritorno non ha il filtro "Fatture"
#// in modo da mostrare anche le note credito
    @api.multi
    def compute_refund(self, mode='refund'):
        result = super(AccountInvoiceRefund, self).compute_refund(mode=mode)
        # Dopo aver splittato i menu Fatture e Note Credito, la vista lista delle fatture (quella standard)
        # ha il filtro dinamico "Fatture", che non mostra le note credito.
        if isinstance(result, dict):
            result_ctx = safe_eval( result.get('context', {}) )
            result_ctx.pop('search_default_invoices', None)
            result['context'] = result_ctx
        return result
