# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime
from dateutil import relativedelta
import time

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.addons.procurement.models import procurement
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_round, float_is_zero
from lxml import etree

class StockMove(models.Model):
    _inherit = "stock.move"
    
    @api.one
    @api.depends('procurement_id.sale_line_id.discount')
    def _get_sale_discount(self):
        procurement = self.procurement_id
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

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        #//rimuovo la colonna sconto dalle righe dei movimenti se il picking non è un out
        res = super(StockMove, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree':
            pickng_type = self.env['stock.picking.type'].browse(self._context.get('default_picking_type_id',[]))
            if not pickng_type or (pickng_type and pickng_type.code != 'outgoing'):
                doc = etree.XML(res['arch'])
                for node in doc.xpath("//field[@name='sale_discount']"):
                    node.getparent().remove(node)           
                res['arch'] = etree.tostring(doc)        
                res['fields'].pop('sale_discount',None)
        return res

    @api.multi
    def assign_picking(self):
        """ Try to assign the moves to an existing picking that has not been
        reserved yet and has the same procurement group, locations and picking
        type (moves should already have them identical). Otherwise, create a new
        picking to assign them to. """
        Picking = self.env['stock.picking']

        # If this method is called in batch by a write on a one2many and
        # at some point had to create a picking, some next iterations could
        # try to find back the created picking. As we look for it by searching
        # on some computed fields, we have to force a recompute, else the
        # record won't be found.
        self.recompute()

        for move in self:
            picking = Picking.search([
                ('group_id', '=', move.group_id.id),
                ('location_id', '=', move.location_id.id),
                ('location_dest_id', '=', move.location_dest_id.id),
                ('picking_type_id', '=', move.picking_type_id.id),
                ('printed', '=', False),
                ('min_date','=',move.date_expected),
                ('state', 'in', ['draft', 'confirmed', 'waiting', 'partially_available', 'assigned'])], limit=1)
            if not picking:
                picking = Picking.create(move._get_new_picking_values())
            move.write({'picking_id': picking.id})
        return True
    _picking_assign = assign_picking

    def _get_new_picking_values(self):
    
        return ({
            'origin': self.origin,
            'company_id': self.company_id.id,
            'move_type': self.group_id and self.group_id.move_type or 'direct',
            'partner_id': self.partner_id.id,
            'picking_type_id': self.picking_type_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'min_date':self.date_expected,
            'max_date':self.date_expected
        })

    _prepare_picking_assign = _get_new_picking_values

