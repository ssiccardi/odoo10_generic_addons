
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PurchaseConfigSettings(models.TransientModel):
    _inherit = 'purchase.config.settings'

    purchase_order_show_residual = fields.Selection([
        (0, "Non mostrare il saldo imponibile nella vista lista degli ordini acquisto"),
        (1, "Mostrare il saldo imponibile nella vista lista degli ordini acquisto"),
        ], "Mostra saldo imponibile",  default=0)


    @api.multi
    def set_purchase_order_show_residual_defaults(self):
        return self.env['ir.values'].sudo().set_default(
            'purchase.config.settings', 'purchase_order_show_residual',
            self.purchase_order_show_residual
        )
