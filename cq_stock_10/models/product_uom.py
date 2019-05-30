# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import math

from odoo import api, fields, models, tools, _

class ProductUoM(models.Model):
    _inherit = 'product.uom'

    decimal_places = fields.Integer(compute='_compute_decimal_places')

    @api.multi
    @api.depends('rounding')
    def _compute_decimal_places(self):
        for uom in self:
            if 0 < uom.rounding < 1:
                uom.decimal_places = int(math.ceil(math.log10(1/uom.rounding)))
            else:
                uom.decimal_places = 0
