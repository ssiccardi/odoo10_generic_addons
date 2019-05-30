# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _

from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round, float_compare


class PackOperation(models.Model):
    _inherit = "stock.pack.operation"

    @api.one
    @api.depends('linked_move_operation_ids.move_id.procurement_id.sale_line_id.discount')
    def _get_sale_discount(self):
        pack = self.linked_move_operation_ids
        if pack:
            move = pack[0].move_id
            if move:
                procurement = move.procurement_id
                if procurement:
                    sale_line = procurement.sale_line_id
                    if sale_line:
                        if sale_line.discount >= 100:
                            self.sale_discount = "Omaggio"
                        elif sale_line.prodotto_sconto:
                            self.sale_discount = "Cessione Gratuita"
                        elif sale_line.discount > 0:
                            self.sale_discount = str(sale_line.discount) + ' %'
    
    sale_discount = fields.Char(compute='_get_sale_discount', string='Sconto', readonly=True)
