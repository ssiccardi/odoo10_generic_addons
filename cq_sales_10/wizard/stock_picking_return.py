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
        return new_picking_id, pick_type_id

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    is_a_return_picking = fields.Boolean("Is a return picking")

    @api.multi
    def create_out_refund(self):
        self.ensure_one()
        inv_obj = self.env['account.invoice']
        inv_line_obj = self.env['account.invoice.line']
        order = self.sale_id
        invoice = inv_obj.create({
            'name': order.client_order_ref or order.name,
            'origin': order.name,
            'type': 'out_refund',
            'journal_id': inv_obj.with_context(type='out_refund').default_get(['journal_id'])['journal_id'],
            'reference': False,
            'account_id': order.partner_id.property_account_receivable_id.id,
            'partner_id': order.partner_invoice_id.id,
            'partner_shipping_id': order.partner_shipping_id.id,
            'currency_id': order.pricelist_id.currency_id.id,
            'payment_term_id': order.payment_term_id.id,
            'fiscal_position_id': order.fiscal_position_id.id or order.partner_id.property_account_position_id.id,
            'team_id': order.team_id.id,
            'comment': order.note})
        for move_line in self.move_lines:
            sale_line = move_line.procurement_id and move_line.procurement_id.sale_line_id or False
            if sale_line:
                account = move_line.product_id.property_account_income_id or move_line.product_id.categ_id.property_account_income_categ_id
                account_id = account and account.id or False
                inv_invoice_line = len(sale_line.invoice_lines)==1 and sale_line.invoice_lines[0] or False
                inv_line_obj.create({
                    'name': sale_line.name,
                    'origin': order.name,
                    'account_id': inv_invoice_line and inv_invoice_line.account_id.id or account_id,
                    'price_unit': inv_invoice_line and inv_invoice_line.price_unit or sale_line.price_unit,
                    'quantity': move_line.product_uom._compute_quantity(move_line.product_uom_qty, sale_line.product_uom),
                    'discount': 0.0,
                    'uom_id': sale_line.product_uom.id,
                    'product_id': move_line.product_id.id,
                    'sale_line_ids': [(6, 0, [sale_line.id])],
                    'invoice_line_tax_ids': inv_invoice_line and [(6, 0, inv_invoice_line.invoice_line_tax_ids.ids)] or [(6, 0, sale_line.tax_id.ids)],
                    'account_analytic_id':  inv_invoice_line and inv_invoice_line.account_analytic_id.id,
                    'invoice_id': invoice.id})
        # Use additional field helper function (for account extensions)
        for line in invoice.invoice_line_ids:
            line._set_additional_fields(invoice)
        invoice.compute_taxes()
        invoice.message_post_with_view('mail.message_origin_link',
                    values={'self': invoice, 'origin': order},
                    subtype_id=self.env.ref('mail.mt_note').id)
        action = self.env.ref('account.action_invoice_tree1').read()[0]
        action['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
        action['res_id'] = invoice.id
        return action

