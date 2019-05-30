# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields


class Partner(models.Model):
    _inherit = 'res.partner'

#// Aggiunto su partner il Conto Bancario su cui ricevere il pagamento a seconda del cliente
    default_bank_account_payment = fields.Many2one('res.partner.bank',
        'Default company bank account',
        help=('The default company bank account that will receive payments from this customer'),
    )
