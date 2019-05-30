# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import datetime
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round, float_compare
from odoo.exceptions import UserError

import sys
reload(sys)
sys.setdefaultencoding('utf8')

class PackOperationLot(models.Model):
    _inherit = "stock.pack.operation.lot"
    
    str_qty_av = fields.Text('Quantity On Hand', related='lot_id.str_qty_av')
    from_make_to_order_move = fields.Boolean(compute='_is_from_make_to_order_move')
    
    @api.one
    def _is_from_make_to_order_move(self):
        if self.mapped('operation_id.linked_move_operation_ids.move_id').filtered(lambda x: x.procure_method == 'make_to_order'):
            self.from_make_to_order_move = True
        else:
            self.from_make_to_order_move = False
   
class PackOperation(models.Model):
    _inherit = "stock.pack.operation"
    
    @api.multi
    def save(self):
        ex = []
        for pack in self:
            if pack.location_id and pack.location_id.usage == 'internal':
                for pack_lot in pack.pack_lot_ids:
                    if pack_lot.lot_id:
                        qty = pack_lot.lot_id.product_id.uom_id._compute_quantity(
                                            sum(pack_lot.lot_id.quant_ids.filtered(lambda x: x.location_id == pack.location_id).mapped('qty')), pack.product_uom_id)
                        if float_compare(pack_lot.qty, qty, precision_rounding=pack.product_uom_id.rounding) > 0:
                            ex.append([pack_lot.lot_id.name, qty])
        if ex:
            msg_err = "Hai inserito per i seguenti lotti una quantità superiore alla disponibilità\n"
            msg_err += "Aggiorna la quantità in possesso o inserisci una quantità minore\n\n"
            for l in ex:
                msg_err += "- %s  disponibilità: %s\n"%(l[0],l[1])
            raise UserError(msg_err)
        return super(PackOperation,self).save()
