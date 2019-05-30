# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleConfiguration(models.TransientModel):
    _inherit = 'sale.config.settings'

    not_check_unique_vat = fields.Selection([
        (0, "Partita IVA unica"),
        (1, "Nessun controllo")
        ], "Controllo partita IVA")

    @api.multi
    def set_not_check_unique_vat_defaults(self):
        return self.env['ir.values'].sudo().set_default(
            'sale.config.settings', 'not_check_unique_vat', self.not_check_unique_vat)
