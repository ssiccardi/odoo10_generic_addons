# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare, float_round
from odoo.tools.translate import _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import UserError

class Quant(models.Model):

    _inherit = "stock.quant"
    
    #campo che contiene il costo reale del quanto basato sulle fatture o sugli ordini di produzione
    #si può anche valorizzare durante un import iniziale delle giacenze per avere una valorizzazione a fine anno coerente
    real_unit_cost = fields.Float('Real Unit Cost', group_operator='avg')
    
    @api.model
    def create(self, vals):
        if 'real_unit_cost' not in vals:
            product = self.env['product.product'].browse(vals.get('product_id',[]))
            vals['real_unit_cost'] = product and product.standard_price or 0
        return super(Quant, self).create(vals)
