# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import namedtuple
import time

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare
from odoo.addons.procurement.models import procurement
from odoo.exceptions import UserError
from lxml import etree

class Picking(models.Model):
    _inherit = "stock.picking"
    
    @api.one
    @api.depends('move_lines.partner_id')
    def _get_customer_dropship(self):
        move_partners = self.mapped('move_lines.partner_id')
        if move_partners:
            self.customer_dropship = move_partners[0]
        else:
            self.customer_dropship = False

    @api.one
    @api.depends('location_id', 'location_dest_id')
    def _is_a_dropship(self):
        if self.location_id.usage == 'supplier' and self.location_dest_id.usage == 'customer':
            self.is_a_dropship = True
        else:
            self.is_a_dropship = False    
    
    customer_dropship = fields.Many2one('res.partner', "Cliente dropship", compute="_get_customer_dropship", readonly=True, store=False)
    is_a_dropship = fields.Boolean("È un dropship", compute="_is_a_dropship", readonly=True, store=False)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        #//rimuovo la colonna sconto dalle righe delle operazioni se il movimento non è un out
        res = super(Picking, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            pickng_type = self.env['stock.picking.type'].browse(self._context.get('default_picking_type_id',[]))
            if pickng_type and pickng_type.code != 'outgoing':
                doc = etree.XML(res.get('fields',{}).get('pack_operation_product_ids',{}).get('views',{}).get('tree',{}).get('arch',{}))
                for node in doc.xpath("//field[@name='sale_discount']"):
                    node.getparent().remove(node)           
                res['fields']['pack_operation_product_ids']['views']['tree']['arch'] = etree.tostring(doc)
                res.get('fields',{}).get('pack_operation_product_ids',{}).get('views',{}).get('tree',{}).get('fields',{}).pop('sale_discount',None)
        return res

    #//eredita stock.picking e fa in modo che a ogni move corrisponda una pack.operation per la spedizione di prodotti uguali con diversi sconti, sia con disponibilità forzata o no e durante la creazione di un backorder
    def _prepare_pack_ops(self, quants, forced_qties):
        """ Prepare pack_operations, returns a list of dict to give at create """
        valid_quants = quants.filtered(lambda quant: quant.qty > 0)
        _Mapping = namedtuple('Mapping', ('product', 'package', 'owner', 'location', 'location_dst_id','move_id'))
        all_products = valid_quants.mapped('product_id') | self.env['product.product'].browse(set(m.product_id.id for m,q in forced_qties)) | self.move_lines.mapped('product_id')
        computed_putaway_locations = dict(
            (product, self.location_dest_id.get_putaway_strategy(product) or self.location_dest_id.id) for product in all_products)
        product_to_uom = dict((product.id, product.uom_id) for product in all_products)
        picking_moves = self.move_lines.filtered(lambda move: move.state not in ('done', 'cancel'))
        for move in picking_moves:
            # If we encounter an UoM that is smaller than the default UoM or the one already chosen, use the new one instead.
            if move.product_uom != product_to_uom[move.product_id.id] and move.product_uom.factor > product_to_uom[move.product_id.id].factor:
                product_to_uom[move.product_id.id] = move.product_uom
        if len(picking_moves.mapped('location_id')) > 1:
            raise UserError(_('The source location must be the same for all the moves of the picking.'))
        if len(picking_moves.mapped('location_dest_id')) > 1:
            raise UserError(_('The destination location must be the same for all the moves of the picking.'))
        pack_operation_values = []
        # find the packages we can move as a whole, create pack operations and mark related quants as done
        top_lvl_packages = valid_quants._get_top_level_packages(computed_putaway_locations)
        for pack in top_lvl_packages:
            pack_quants = pack.get_content()
            pack_operation_values.append({
                'picking_id': self.id,
                'package_id': pack.id,
                'product_qty': 1.0,
                'location_id': pack.location_id.id,
                'location_dest_id': computed_putaway_locations[pack_quants[0].product_id],
                'owner_id': pack.owner_id.id,
            })
            valid_quants -= pack_quants
        # Go through all remaining reserved quants and group by product, package, owner, source location and dest location
        # Lots will go into pack operation lot object
        qtys_grouped = {}
        lots_grouped = {}
        for quant in valid_quants:
            key = _Mapping(quant.product_id, quant.package_id, quant.owner_id, quant.location_id, computed_putaway_locations[quant.product_id], quant.reservation_id)
            qtys_grouped.setdefault(key, 0.0)
            qtys_grouped[key] += quant.qty
            if quant.product_id.tracking != 'none' and quant.lot_id:
                lots_grouped.setdefault(key, dict()).setdefault(quant.lot_id.id, 0.0)
                lots_grouped[key][quant.lot_id.id] += quant.qty
        # Do the same for the forced quantities (in cases of force_assign or incomming shipment for example)
        for move_f, qty in forced_qties:
            if qty <= 0.0:
                continue
            key = _Mapping(move_f.product_id, self.env['stock.quant.package'], self.owner_id, self.location_id, computed_putaway_locations[move_f.product_id], move_f)
            qtys_grouped.setdefault(key, 0.0)
            qtys_grouped[key] += qty
        # Create the necessary operations for the grouped quants and remaining qtys
        Uom = self.env['product.uom']
        move_id_to_vals = {}  # use it to create operations using the same order as the picking stock moves
        for mapping, qty in qtys_grouped.items():
            uom = product_to_uom[mapping.product.id]
            val_dict = {
                'picking_id': self.id,
                'product_qty': mapping.product.uom_id._compute_quantity(qty, uom),
                'product_id': mapping.product.id,
                'package_id': mapping.package.id,
                'owner_id': mapping.owner.id,
                'location_id': mapping.location.id,
                'location_dest_id': mapping.location_dst_id,
                'product_uom_id': uom.id,
                'pack_lot_ids': [
                    (0, 0, {'lot_id': lot, 'qty': 0.0, 'qty_todo': lots_grouped[mapping][lot]})
                    for lot in lots_grouped.get(mapping, {}).keys()],
            }
            move_id_to_vals.setdefault(mapping.move_id.id, list()).append(val_dict)
        for move in self.move_lines.filtered(lambda move: move.state not in ('done', 'cancel')):
            values = move_id_to_vals.pop(move.id, [])
            pack_operation_values += values
        return pack_operation_values

    @api.multi
    def do_prepare_partial(self):
        PackOperation = self.env['stock.pack.operation']
        # get list of existing operations and delete them
        existing_packages = PackOperation.search([('picking_id', 'in', self.ids)])
        if existing_packages:
            existing_packages.unlink()
        for picking in self:
            forced_qties = []  # Quantity remaining after calculating reserved quants
            picking_quants = self.env['stock.quant']
            # Calculate packages, reserved quants, qtys of this picking's moves
            for move in picking.move_lines:
                if move.state not in ('assigned', 'confirmed', 'waiting'):
                    continue
                move_quants = move.reserved_quant_ids
                picking_quants += move_quants
                forced_qty = 0.0
                if move.state == 'assigned':
                    qty = move.product_uom._compute_quantity(move.product_uom_qty, move.product_id.uom_id, round=False)
                    forced_qty = qty - sum([x.qty for x in move_quants])
                # if we used force_assign() on the move, or if the move is incoming, forced_qty > 0
                if float_compare(forced_qty, 0, precision_rounding=move.product_id.uom_id.rounding) > 0:
                    forced_qties.append((move, forced_qty))
            for vals in picking._prepare_pack_ops(picking_quants, forced_qties):
                vals['fresh_record'] = False
                PackOperation.create(vals)
        # recompute the remaining quantities all at once
        self.do_recompute_remaining_quantities()
        self.write({'recompute_pack_op': False})

    def recompute_remaining_qty(self, done_qtys=False):

        def _create_link_for_index(operation_id, index, product_id, qty_to_assign, quant_id=False):
            move_dict = prod2move_ids[product_id][index]
            qty_on_link = min(move_dict['remaining_qty'], qty_to_assign)
            self.env['stock.move.operation.link'].create({'move_id': move_dict['move'].id, 'operation_id': operation_id, 'qty': qty_on_link, 'reserved_quant_id': quant_id})
            if move_dict['remaining_qty'] == qty_on_link:
                prod2move_ids[product_id].pop(index)
            else:
                move_dict['remaining_qty'] -= qty_on_link
            return qty_on_link

        def _create_link_for_quant(operation_id, quant, qty):
            """create a link for given operation and reserved move of given quant, for the max quantity possible, and returns this quantity"""
            if not quant.reservation_id.id:
                return _create_link_for_product(operation_id, quant.product_id.id, qty)
            qty_on_link = 0
            for i in range(0, len(prod2move_ids[quant.product_id.id])):
                if prod2move_ids[quant.product_id.id][i]['move'].id != quant.reservation_id.id:
                    continue
                qty_on_link = _create_link_for_index(operation_id, i, quant.product_id.id, qty, quant_id=quant.id)
                break
            return qty_on_link

        def _create_link_for_product(operation_id, product_id, qty):
            '''method that creates the link between a given operation and move(s) of given product, for the given quantity.
            Returns True if it was possible to create links for the requested quantity (False if there was not enough quantity on stock moves)'''
            qty_to_assign = qty
            Product = self.env["product.product"]
            product = Product.browse(product_id)
            rounding = product.uom_id.rounding
            qtyassign_cmp = float_compare(qty_to_assign, 0.0, precision_rounding=rounding)
            if prod2move_ids.get(product_id):
                while prod2move_ids[product_id] and qtyassign_cmp > 0:
                    indx = 0
                    for i,item in enumerate(prod2move_ids[product_id]):
                        if operation_id in item['operation_ids']:
                            indx = i
                            break
                    qty_on_link = _create_link_for_index(operation_id, indx, product_id, qty_to_assign, quant_id=False)
                    qty_to_assign -= qty_on_link
                    qtyassign_cmp = float_compare(qty_to_assign, 0.0, precision_rounding=rounding)
            return qtyassign_cmp == 0

        # TDE CLEANME: oh dear ...
        Uom = self.env['product.uom']
        QuantPackage = self.env['stock.quant.package']
        OperationLink = self.env['stock.move.operation.link']

        quants_in_package_done = set()
        prod2move_ids = {}
        still_to_do = []
        # make a dictionary giving for each product, the moves and related quantity that can be used in operation links
        moves = sorted([x for x in self.move_lines if x.state not in ('done', 'cancel')], key=lambda x: (((x.state == 'assigned') and -2 or 0) + (x.partially_available and -1 or 0)))
        for move in moves:
            if not prod2move_ids.get(move.product_id.id):
                prod2move_ids[move.product_id.id] = [{'move': move, 
                                                      'operation_ids': map(lambda lop: lop.operation_id and lop.operation_id.id, move.linked_move_operation_ids),
                                                      'remaining_qty': move.product_qty}]
            else:
                prod2move_ids[move.product_id.id].append({'move': move, 
                                                          'operation_ids': map(lambda lop: lop.operation_id and lop.operation_id.id, move.linked_move_operation_ids),
                                                          'remaining_qty': move.product_qty})

        need_rereserve = False
        # sort the operations in order to give higher priority to those with a package, then a lot/serial number
        operations = self.pack_operation_ids
        operations = sorted(operations, key=lambda x: ((x.package_id and not x.product_id) and -4 or 0) + (x.package_id and -2 or 0) + (x.pack_lot_ids and -1 or 0))
        # delete existing operations to start again from scratch
        links = OperationLink.search([('operation_id', 'in', [x.id for x in operations])])
        if links:
            links.unlink()
        # 1) first, try to create links when quants can be identified without any doubt
        for ops in operations:
            lot_qty = {}
            for packlot in ops.pack_lot_ids:
                lot_qty[packlot.lot_id.id] = ops.product_uom_id._compute_quantity(packlot.qty, ops.product_id.uom_id)
            # for each operation, create the links with the stock move by seeking on the matching reserved quants,
            # and deffer the operation if there is some ambiguity on the move to select
            if ops.package_id and not ops.product_id and (not done_qtys or ops.qty_done):
                # entire package
                for quant in ops.package_id.get_content():
                    remaining_qty_on_quant = quant.qty
                    if quant.reservation_id:
                        # avoid quants being counted twice
                        quants_in_package_done.add(quant.id)
                        qty_on_link = _create_link_for_quant(ops.id, quant, quant.qty)
                        remaining_qty_on_quant -= qty_on_link
                    if remaining_qty_on_quant:
                        still_to_do.append((ops, quant.product_id.id, remaining_qty_on_quant))
                        need_rereserve = True
            elif ops.product_id.id:
                # Check moves with same product
                product_qty = ops.qty_done if done_qtys else ops.product_qty
                qty_to_assign = ops.product_uom_id._compute_quantity(product_qty, ops.product_id.uom_id)
                precision_rounding = ops.product_id.uom_id.rounding
                for move_dict in prod2move_ids.get(ops.product_id.id, []):
                    move = move_dict['move']
                    for quant in move.reserved_quant_ids:
                        if float_compare(qty_to_assign, 0, precision_rounding=precision_rounding) != 1:
                            break
                        if quant.id in quants_in_package_done:
                            continue

                        # check if the quant is matching the operation details
                        if ops.package_id:
                            flag = quant.package_id == ops.package_id
                        else:
                            flag = not quant.package_id.id
                        flag = flag and (ops.owner_id.id == quant.owner_id.id)
                        if flag:
                            if not lot_qty:
                                max_qty_on_link = min(quant.qty, qty_to_assign)
                                qty_on_link = _create_link_for_quant(ops.id, quant, max_qty_on_link)
                                qty_to_assign -= qty_on_link
                            else:
                                if lot_qty.get(quant.lot_id.id):  # if there is still some qty left
                                    max_qty_on_link = min(quant.qty, qty_to_assign, lot_qty[quant.lot_id.id])
                                    qty_on_link = _create_link_for_quant(ops.id, quant, max_qty_on_link)
                                    qty_to_assign -= qty_on_link
                                    lot_qty[quant.lot_id.id] -= qty_on_link

                qty_assign_cmp = float_compare(qty_to_assign, 0, precision_rounding=precision_rounding)
                if qty_assign_cmp > 0:
                    # qty reserved is less than qty put in operations. We need to create a link but it's deferred after we processed
                    # all the quants (because they leave no choice on their related move and needs to be processed with higher priority)
                    still_to_do += [(ops, ops.product_id.id, qty_to_assign)]
                    need_rereserve = True

        # 2) then, process the remaining part
        all_op_processed = True
        for ops, product_id, remaining_qty in still_to_do:
            all_op_processed = _create_link_for_product(ops.id, product_id, remaining_qty) and all_op_processed
        return (need_rereserve, all_op_processed)
