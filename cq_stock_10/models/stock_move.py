# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools.float_utils import float_compare
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.multi
    @api.constrains('product_uom_qty')
    def not_negative_quantity_constrain(self):
        for move in self:
            if float_compare(move.product_uom_qty, 0, precision_rounding=move.product_id.uom_id.rounding) <= 0:
                raise ValidationError(_('You cannot have a move with negative or null quantity'))

    @api.multi
    def do_unreserve(self):
        self.mapped('linked_move_operation_ids.operation_id').unlink()
        return super(StockMove, self).do_unreserve()

    @api.multi
    def action_cancel(self):
        self.mapped('linked_move_operation_ids.operation_id').unlink()
        return super(StockMove, self).action_cancel()
    
    @api.multi
    def action_assign_inpicking(self):
        self.action_assign()
        picking = self.mapped('picking_id')
        if picking:
            picking.do_prepare_partial()
        return True

    real_unit_cost = fields.Float('Real Unit Cost', compute='_compute_real_unit_cost', readonly=True, group_operator='avg')

    @api.one
    def _compute_real_unit_cost(self):
        value = 0
        for quant in self.quant_ids.filtered(lambda x: x.qty > 0):
            value += quant.qty * quant.real_unit_cost
        self.real_unit_cost = self.product_qty and value / self.product_qty or 0

    @api.multi
    def action_done(self):
        #al completamento del movimento scrivo sui quanti spostati il loro costo unitario reale dalla fattura, se c'è già
        #andrebbe fatta la stessa cosa in cq_mrp_production per i costi di produzione sommando i costi dei componenti
        res = super(StockMove,self).action_done()
        for move in self:
            product = move.product_id
            if move.purchase_line_id:
                price_unit = move.purchase_line_id._get_stock_move_price_unit()
                invoice_lines = move.purchase_line_id.invoice_lines.filtered(lambda x: x.product_id == product and x.invoice_id.type=='in_invoice')
                if invoice_lines:
                    qty = 0
                    price = 0
                    for invoice_line in invoice_lines:
                        if invoice_line.uom_id and invoice_line.uom_id!=product.uom_id:
                            qty += invoice_line.uom_id._compute_quantity(invoice_line.quantity, product.uom_id, round=False)
                        else:
                            qty += invoice_line.quantity
                        if invoice_line.invoice_id.currency_id != move.company_id.currency_id:
                            price += invoice_line.invoice_id.currency_id.compute(invoice_line.price_subtotal, move.company_id.currency_id, round=False)
                        else:
                            price += invoice_line.price_subtotal
                    if float_compare(qty, 0, precision_rounding = product.uom_id.rounding) > 0:
                        price_unit = price / qty
                move.sudo().quant_ids.write({'real_unit_cost': price_unit})   
        return res
