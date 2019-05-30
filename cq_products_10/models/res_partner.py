# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api


class Partner(models.Model):

    _inherit = 'res.partner'

    def _get_default_product_pricelist(self):
        pricelist_id = self.env['ir.model.data'].xmlid_to_res_id('product.list0')
        if not pricelist_id:
            pricelist_id = self.env['product.pricelist'].search([], limit=1)
            pricelist_id = pricelist_id and pricelist_id[0].id or False
        return pricelist_id
    #//eredito il campo listino sulla scheda cliente per non renderlo più calcolato
    #non è un campo property
    property_product_pricelist = fields.Many2one('product.pricelist', 'Sale Pricelist',  compute=False, inverse=False, default=_get_default_product_pricelist)

