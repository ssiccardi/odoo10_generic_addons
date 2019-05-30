# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2014
#    Stefano Siccardi creativiquadrati snc
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import fields, models, api, SUPERUSER_ID, _
from datetime import datetime, date
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from dateutil.parser import parse
from odoo.tools.float_utils import float_is_zero, float_compare
from lxml import etree
import json

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.multi
    @api.depends(
        'currency_id', 'amount_untaxed', 'amount_total',
        'order_line.invoice_lines.invoice_id.state'
    )
    def _compute_residual(self):
        ''' Compute order residual amount not invoiced yet '''
        for order in self:
            residual = order.amount_total
            residual_untaxed = order.amount_untaxed
            inv_states = ['open', 'paid']
            invoices = order.sudo().invoice_ids.filtered(
                lambda i: i.type == 'in_invoice' and i.state in inv_states
            )
            for inv in invoices:
                if order.currency_id == inv.currency_id:
                    residual -= inv.amount_total
                    residual_untaxed -= inv.amount_untaxed
                else:
                    inv_total_converted = inv.currency_id.compute(
                        inv.amount_total, order.currency_id
                    )
                    inv_untaxed_converted = inv.currency_id.compute(
                        inv.amount_untaxed, order.currency_id
                    )
                    residual -= inv_total_converted
                    residual_untaxed -= inv_untaxed_converted

            precision = order.currency_id.rounding
            if float_compare(residual_untaxed, 0., precision_digits=precision) < 0.:
                order.residual_untaxed = 0.
            else:
                order.residual_untaxed = residual_untaxed
            if float_compare(residual, 0., precision_digits=precision) < 0.:
                order.residual_total = 0.
            else:
                order.residual_total = residual

    @api.depends('state', 'order_line.qty_invoiced', 'order_line.qty_received', 'order_line.product_qty')
    def _get_invoiced(self):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for order in self:
            if order.state not in ('purchase', 'done'):
                order.invoice_status = 'no'
                continue

            if any(float_compare(line.qty_invoiced, line.product_qty if line.product_id.purchase_method == 'purchase' else line.qty_received, precision_digits=precision) == -1 for line in order.order_line):
                order.invoice_status = 'to invoice'
            elif all(float_compare(line.qty_invoiced, line.product_qty if line.product_id.purchase_method == 'purchase' else line.qty_received, precision_digits=precision) >= 0 for line in order.order_line) and order.invoice_ids:
                order.invoice_status = 'invoiced'
            else:
                order.invoice_status = 'no'

    name = fields.Char('Order Reference', required=True, index=True, copy=False, default=_('New'))
    date_approve = fields.Date(readonly=False, index=False)
    residual_untaxed = fields.Monetary(
        string='Untaxed Residual', store=True, readonly=True,
        compute='_compute_residual', track_visibility='always',
        help="Untaxed order amount that is not invoiced yet"
    )
    residual_total = fields.Monetary(
        string='Total Residual', store=True, readonly=True,
        compute='_compute_residual', track_visibility='always',
        help="Total order amount (including taxes) that is not invoiced yet"
    )

    #//Eredita purchase.order
    #//Crea diversi picking dallo stesso ordine di acquisto, uno per ogni data prevista di arrivo dei prodotti
    @api.multi
    def _create_picking(self):
        StockPicking = self.env['stock.picking']
        for order in self.filtered(lambda x: any([ptype in ['product', 'consu'] for ptype in x.order_line.mapped('product_id.type')])):
            lines_to_move = order.order_line.filtered(lambda x: x.product_id and x.product_id.type in ['product', 'consu'])
            mul_order_date_planned = lines_to_move.mapped(lambda x: parse(x.date_planned).date())
            order_date_planned = []
            for tdate in mul_order_date_planned:
                if tdate not in order_date_planned:
                    order_date_planned.append(tdate)
            order_date_planned.sort()
            #date planned su purchase.order.line è obbligatoria ma non si sa mai
            if order_date_planned:
                for date_planned in order_date_planned:
                    lines_to_move_date = lines_to_move.filtered(lambda x: parse(x.date_planned).date() == date_planned)
                    pickings = lines_to_move_date.mapped('move_ids.picking_id').filtered(lambda x: x.state not in ('done','cancel'))
                    if not pickings:
                        res = order._prepare_picking()
                        picking = StockPicking.create(res)
                    else:
                        picking = pickings[0]
                    moves = lines_to_move_date._create_stock_moves(picking)
                    moves = moves.filtered(lambda x: x.state not in ('done', 'cancel')).action_confirm()
                    moves.force_assign()
                    picking.message_post_with_view('mail.message_origin_link',
                        values={'self': picking, 'origin': order},
                        subtype_id=self.env.ref('mail.mt_note').id)
            else:
                super(PurchaseOrder, [order])._create_picking()
        return True

    #scrive la data di conferma
    @api.multi
    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        for order in self:
            if not order.date_approve:
                order.date_approve = datetime.today().strftime(DEFAULT_SERVER_DATE_FORMAT)
        return res


    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(PurchaseOrder, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )
        ''' Change invisible attribute on Residual_untaxed field
        '''
        IrValues = self.env['ir.values']
        #~ order_tree_id = self.env['ir.model.data'].get_object_reference(
            #~ 'purchase', 'purchase_order_tree'
        #~ )[1]
        order_tree_id = self.env['ir.model.data'].get_object_reference(
            'cq_purchase_10', 'purchase_order_tree_cq'
        )[1]
        purchase_order_show_residual = IrValues.get_default(
            'purchase.config.settings', 'purchase_order_show_residual'
        )
        doc = etree.XML(res['arch'])

        if view_type == 'tree' and (view_id in [order_tree_id, None]):
            residual_nodes = doc.xpath("//field[@name='residual_untaxed']")
            if purchase_order_show_residual == 0 or \
               (
                purchase_order_show_residual == 1 and
                not self.env.context.get('show_purchase', False)
               ):
                for node in residual_nodes:
                    node.set("invisible", "True")
                    modifiers = json.loads(node.get("modifiers"))
                    modifiers['tree_invisible'] = True
                    node.set("modifiers", json.dumps(modifiers))
            else:
                for node in residual_nodes:
                    node.set("invisible", "False")
                    modifiers = json.loads(node.get("modifiers"))
                    modifiers['tree_invisible'] = False
                    node.set("modifiers", json.dumps(modifiers))
        res['arch'] = etree.tostring(doc)
        return res


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.onchange('product_qty', 'product_uom')
    def _onchange_quantity(self):
        if not self.product_id:
            return

        seller = self.product_id._select_seller(
            partner_id=self.partner_id,
            quantity=self.product_qty,
            date=self.order_id.date_order and self.order_id.date_order[:10],
            uom_id=self.product_uom)

        if seller and not self.date_planned: #cambiando quantità, aggiorna la data prevista solo se non è impostata
            self.date_planned = self._get_date_planned(seller).strftime(DEFAULT_SERVER_DATETIME_FORMAT)

        price_unit = self.env['account.tax']._fix_tax_included_price(seller.price, self.product_id.supplier_taxes_id, self.taxes_id) if seller else 0.0
        if price_unit and seller and self.order_id.currency_id and seller.currency_id != self.order_id.currency_id:
            price_unit = seller.currency_id.compute(price_unit, self.order_id.currency_id)

        if seller and self.product_uom and seller.product_uom != self.product_uom:
            price_unit = seller.product_uom._compute_price(price_unit, self.product_uom)

        self.price_unit = price_unit

    @api.multi
    @api.depends('order_id.state', 'move_ids.state')
    def _compute_qty_received(self):
        for line in self:
            if line.order_id.state not in ['purchase', 'done']:
                line.qty_received = 0.0
                continue
            if line.product_id.type not in ['consu', 'product']:
                line.qty_received = line.product_qty
                continue
            total = 0.0
            for move in line.move_ids:
                if move.state == 'done':
                    if not move.origin_returned_move_id:
                        total += move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom)
                    else:
                        total -= move.product_uom._compute_quantity(move.product_uom_qty, line.product_uom)
            line.qty_received = total   

class SuppliferInfo(models.Model):
    _inherit = "product.supplierinfo"
    _order = 'sequence, product_id, min_qty desc, price'

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_tmpl_id = self.product_id.product_tmpl_id

