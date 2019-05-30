# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_round, float_is_zero
from odoo.exceptions import UserError

class Picking(models.Model):
    _inherit = "stock.picking"

    set_column_qtydone_visible = fields.Boolean(compute='_compute_set_column_qtydone_visible')

    @api.multi
    @api.depends('pack_operation_product_ids.qty_done')
    def _compute_set_column_qtydone_visible(self):
        for pick in self:
            pick.set_column_qtydone_visible = any(pack.product_qty > pack.qty_done and not pack.lots_visible for pack in pick.pack_operation_product_ids)

    @api.one
    def set_column_qtydone(self):
        for pack in self.pack_operation_product_ids:
            if pack.product_id.tracking == 'none':
                if pack.product_qty > pack.qty_done:
                    pack.write({'qty_done': pack.product_qty})

    @api.multi
    def do_unreserve_reserve(self):
        """
          toglie la riserva dei quanti riservati ad altri picking per poterli riservare a questo
        """
        if self.env['ir.values'].get_default('res.config.settings', 'unreserve_priority_move'):
            order = "date desc"
        else:
            order = "date asc"
        pickings = self.filtered(lambda pick: pick.state in ('confirmed', 'partially_available'))
        for picking in pickings:
            for move in picking.move_lines:
                move.action_assign()
                if move.state != 'confirmed' or move.procure_method != 'make_to_stock':
                    continue
                rounding = move.product_id.uom_id.rounding
                quants = self.env['stock.quant'].search([('location_id', 'child_of', move.location_id.id), ('product_id', '=', move.product_id.id)])
                qty_available = sum(quants.mapped('qty'))
                if not self._context.get('force_unreserve_reserve') and float_compare(qty_available, move.product_qty, precision_rounding = rounding) < 0:
                    view_id = self.env.ref('cq_stock_10.popup_confim_unreserve_reserve').id
                    return {
                        'name': 'Conferma Azione',
                        'type': 'ir.actions.act_window',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_model': 'stock.picking',
                        'views': [(view_id, 'form')],
                        'view_id': view_id,
                        'target': 'new',
                        'res_id': self.ids[0],
                        'context': self._context}

                moves_to_unreserve = self.env['stock.move'].search([ ('picking_id','!=', picking.id),
                                                                     ('product_id', '=', move.product_id.id),
                                                                     ('procure_method', '=', 'make_to_stock'),
                                                                     ('state', 'in', ['confirmed','assigned']),
                                                                     ('reserved_availability', '>', 0),
                                                                     ('location_id', 'child_of', move.location_id.id) ], order=order)
                for moveu in moves_to_unreserve:
                    moveu.do_unreserve()
                    move.action_assign()
                    if move.state == 'assigned':
                        break
        return {'type': 'ir.actions.act_window_close'}

    @api.multi
    def action_cancel(self):
        self.mapped('pack_operation_ids').unlink()
        return super(Picking, self).action_cancel()

    @api.multi
    def unlink(self):
        if any(pick.state != 'cancel' and pick.move_lines for pick in self):
            raise UserError(_('You can only delete pickings in cancel state.'))
        return super(Picking, self).unlink()

    @api.multi
    def action_reconfirm(self):
        self.mapped('move_lines').filtered(lambda move: move.state == 'cancel').action_confirm()
        self.filtered(lambda picking: picking.location_id.usage in ('supplier', 'inventory', 'production')).force_assign()
        return True
