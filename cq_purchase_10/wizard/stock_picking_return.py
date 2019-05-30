# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError

class StockReturnPicking(models.TransientModel):
    _inherit = "stock.return.picking"

    @api.multi
    def _create_returns(self):
        new_picking_id, pick_type_id = super(StockReturnPicking, self)._create_returns()
        new_picking = self.env['stock.picking'].browse([new_picking_id])
        new_picking.is_a_return_picking = True
        for move in new_picking.move_lines:
            move.purchase_line_id = move.origin_returned_move_id.purchase_line_id.id
        return new_picking_id, pick_type_id

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_a_return_picking = fields.Boolean("Is a return picking")

    @api.multi
    def create_in_refund(self):
        self.ensure_one()
        inv_obj = self.env['account.invoice']
        inv_line_obj = self.env['account.invoice.line']
        order = self.purchase_id
        invoice = inv_obj.create({
            'name': order.partner_ref or order.name,
            'origin': order.name,
            'type': 'in_refund',
            'journal_id': order.invoice_ids[0].journal_id.id if order.invoice_ids else inv_obj.with_context(type='in_refund').default_get(['journal_id'])['journal_id'],
            'reference': False,
            'account_id': order.partner_id.property_account_receivable_id.id,
            'partner_id': order.partner_id.id,
            'currency_id': order.currency_id.id,
            'payment_term_id': order.payment_term_id.id,
            'fiscal_position_id': order.fiscal_position_id.id or order.partner_id.property_account_position_id.id,
            'comment': order.notes})
        for move_line in self.move_lines:
            purchase_line = move_line.purchase_line_id
            if purchase_line:
                account = move_line.product_id.property_account_income_id or move_line.product_id.categ_id.property_account_income_categ_id
                account_id = account and account.id or False
                inv_invoice_line = len(purchase_line.invoice_lines)==1 and purchase_line.invoice_lines[0] or False
                inv_line_obj.create({
                    'name': inv_invoice_line and inv_invoice_line.name or purchase_line.name,
                    'origin': order.name,
                    'account_id': inv_invoice_line and inv_invoice_line.account_id.id or account_id,
                    'price_unit': inv_invoice_line.price_unit if inv_invoice_line else purchase_line.price_unit,
                    'quantity': move_line.product_uom._compute_quantity(move_line.product_uom_qty, purchase_line.product_uom),
                    'discount': 0.0,
                    'uom_id': purchase_line.product_uom.id,
                    'product_id': move_line.product_id.id,
                    'purchase_line_id': purchase_line.id,
                    'invoice_line_tax_ids': inv_invoice_line and [(6, 0, inv_invoice_line.invoice_line_tax_ids.ids)] or [(6, 0, purchase_line.taxes_id.ids)],
                    'account_analytic_id': inv_invoice_line and inv_invoice_line.account_analytic_id.id,
                    'invoice_id': invoice.id})
        # Use additional field helper function (for account extensions)
        for line in invoice.invoice_line_ids:
            line._set_additional_fields(invoice)
        invoice.compute_taxes()
        invoice.message_post_with_view('mail.message_origin_link',
                    values={'self': invoice, 'origin': order},
                    subtype_id=self.env.ref('mail.mt_note').id)
        action = self.env.ref('account.action_invoice_tree2').read()[0]
        action['views'] = [(self.env.ref('account.invoice_supplier_form').id, 'form')]
        action['res_id'] = invoice.id
        return action

