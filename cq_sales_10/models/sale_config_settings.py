
# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleConfiguration(models.TransientModel):
    _inherit = 'sale.config.settings'

    sale_order_partner_domain = fields.Selection([
        (0, "Mostra tutti i partner con flag È un cliente"),
        (1, "Mostra solo i partner con flag È un cliente e figli del Cliente"),
        ], "Filtri su Indirizzi",  default=1)
    sale_order_show_residual = fields.Selection([
        (0, "Non mostrare il saldo imponibile nella vista lista degli ordini vendita"),
        (1, "Mostrare il saldo imponibile nella vista lista degli ordini vendita"),
        ], "Mostra saldo imponibile",  default=0)

    @api.multi
    def set_sale_order_partner_domain_defaults(self):
        return self.env['ir.values'].sudo().set_default(
            'sale.config.settings', 'sale_order_partner_domain',
            self.sale_order_partner_domain
        )

    @api.multi
    def set_sale_order_show_residual_defaults(self):
        return self.env['ir.values'].sudo().set_default(
            'sale.config.settings', 'sale_order_show_residual',
            self.sale_order_show_residual
        )
