# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round, float_compare

import sys
reload(sys)
sys.setdefaultencoding('utf8')

class ProductionLot(models.Model):
    _inherit = 'stock.production.lot'
    
    str_qty_av = fields.Text('Quantity On Hand', compute='_str_qty_av')
    
    @api.one
    @api.depends('quant_ids.qty')
    def _str_qty_av(self):
        str_qty_av = []
        locations = []
        locations_mult = self.quant_ids.mapped('location_id').filtered(lambda x: x.usage == 'internal')
        for location in locations_mult:
            if location not in locations:
                locations.append(location)
        if locations:
            locations.sort()
            for location in locations:
                qty = sum(self.quant_ids.filtered(lambda x: x.location_id == location).mapped('qty'))
                if float_compare(qty, 0, precision_rounding=self.product_uom_id.rounding) > 0:
                    str_qty_av.append('%s: %s %s'%(location.name, 
                                                   str(qty).replace('.',','), 
                                                   self.product_uom_id.name))
        self.str_qty_av = '\n'.join(str_qty_av) or _('None')

