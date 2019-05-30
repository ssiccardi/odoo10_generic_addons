# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields

class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

#// Aggiunto flag Conto Bancario Default sulle banche
    default_bank = fields.Boolean('Default bank account',
            help=('Use this bank account as default one on invoices')
        )
