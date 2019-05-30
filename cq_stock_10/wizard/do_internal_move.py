# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
import copy
from odoo.tools import float_compare, float_round
import time
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

## HOWTO fix the Unicode special characters issue
## https://stackoverflow.com/questions/21129020/how-to-fix-unicodedecodeerror-ascii-codec-cant-decode-byte
import sys
reload(sys)
sys.setdefaultencoding('utf8')


'''classi per la visualizzazione dei lotti'''
class AvQtyLots(models.TransientModel):
    _name = "av.qty.lots"
    
    lot_id = fields.Many2one(
        'stock.production.lot', 'Lotto', readonly=True)
    product_id = fields.Many2one(
        'product.product', 'Prodotto', readonly=True)
    product_uom_id = fields.Many2one(
        'product.uom', 'Unità di Misura', related='product_id.uom_id', readonly=True)
    production_date = fields.Datetime('Data Produzione', readonly=True)
    product_qty = fields.Float('Quantità Disponibile', readonly=True)
    location_id = fields.Many2one('stock.location', 'Locazione Sorgente', required=True, domain=['usage','=','internal'])

    @api.multi
    def visualizza(self,location_id):
        query = '''SELECT lot_id, product_id, SUM(qty) as product_qty, MAX(location_id) as location_id, MAX(create_date) as production_date
                   FROM stock_quant
                   WHERE location_id = %s AND reservation_id is null
                   GROUP BY lot_id, product_id
                   HAVING SUM(qty) > 0'''%location_id
        self._cr.execute(query)
        ids = []
        for rec in self._cr.dictfetchall():
            ids.append(self.create(rec).id)

        treeview_id = self.env['ir.model.data'].get_object_reference('cq_stock_10', 'view_qty_lots_tree')[1]
        return {
            "type": "ir.actions.act_window",
            "name": "Lotti disponibili in %s"%self.env['stock.location'].browse(location_id).name,
            "view_type": "form",
            "view_mode": "tree,form",
            "view_id": treeview_id,
            "views": [(treeview_id, 'tree')],            
            "res_model": "av.qty.lots",
            "domain": [('id','in',ids)],
        }
    
class SelectLocationInternalMove(models.TransientModel):
    _name = "select.location.internal.move"

    @api.model
    def _get_default_location_id(self):
        picking_id = self.env['ir.model.data'].get_object_reference('stock', 'picking_type_internal')[1]
        return self.env['stock.picking.type'].browse(picking_id).default_location_src_id.id
            
    location_id = fields.Many2one('stock.location', 'Locazione Sorgente', default=_get_default_location_id, required=True)
    
    @api.multi
    def visualizza(self):
        return self.env['av.qty.lots'].visualizza(self.location_id.id)



 
'''classi per la creazione del picking e delle moves'''
class WizardCreatePicking(models.TransientModel):
    _name = "wizard.create.picking"

    location_id = fields.Many2one(
        'stock.location', "Locazione di Partenza", readonly=True)
    location_dest_id = fields.Many2one(
        'stock.location', "Locazione di Arrivo", required=True, domain=[('usage','=','internal')])
    move_lines = fields.One2many('wizard.create.move', 'picking_id', string="Movimenti")
    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Tipo di Picking', required=True, domain=[('code','=','internal')])
    note = fields.Text('Note') 
        
    @api.multi
    def crea_picking(self,ids):
        picking_type_id = self.env['ir.model.data'].get_object_reference('stock', 'picking_type_internal')[1]
        location = self.env['av.qty.lots'].browse(ids[0]).location_id
        location_dest = self.env['stock.picking.type'].browse(picking_type_id).default_location_dest_id
        picking = self.create({'location_id': location.id,
                               'location_dest_id': location_dest.id,
                               'picking_type_id': picking_type_id})
        WizardCreateMove = self.env['wizard.create.move']
        for move in self.env['av.qty.lots'].browse(ids):
            #ricalcolo la quantità disponibile del lotto perchè nel frattempo qualcuno potrebbe movimentarne una quantità
            self._cr.execute('''SELECT SUM(qty) as product_qty
                                FROM stock_quant
                                WHERE '''+(move.lot_id and 'lot_id = %s AND '%move.lot_id.id or '')+'''product_id = %s AND location_id = %s AND reservation_id is null
                                GROUP BY lot_id,product_id'''%(move.product_id.id,location.id))
            av_qty = self._cr.fetchone()
            av_qty = av_qty and av_qty[0] or 0                                
            WizardCreateMove.create({'picking_id': picking.id,
                                     'product_id': move.product_id.id,
                                     'product_qty': av_qty,
                                     'product_uom': move.product_uom_id.id,
                                     'lot_id': move.lot_id.id,
                                     'product_qty_totr': move.lot_id and av_qty or 0,
                                     })
        return {
            "type": "ir.actions.act_window",
            "name": "Crea Movimento",
            "view_type": "form",
            "view_mode": "form",
            "res_model": "wizard.create.picking",
            "res_id": picking.id,
            "target": 'new',
        }
        
    @api.multi
    def do_move(self):
        error = ''
        for move in self.move_lines:
            #ricalcolo la quantità disponibile del lotto perchè nel frattempo qualcuno potrebbe movimentarne una quantità
            self._cr.execute('''SELECT SUM(qty) as product_qty
                                FROM stock_quant
                                WHERE '''+(move.lot_id and 'lot_id = %s AND '%move.lot_id.id or '')+'''product_id = %s AND location_id = %s AND reservation_id is null
                                GROUP BY lot_id,product_id'''%(move.product_id.id,self.location_id.id))
            av_qty = self._cr.fetchone()
            av_qty = av_qty and av_qty[0] or 0
            precision = move.product_uom.rounding
            if float_compare(av_qty, move.product_qty_totr, precision_rounding=precision) < 0 or float_compare(move.product_qty_totr, 0, precision_rounding=precision) <= 0:
                error += '- Prodotto: %s Lotto: %s Qtà Disp: %s %s\n'\
                                         %(move.product_id_name,move.lot_id_name,float_round(av_qty, precision_rounding=precision),move.product_uom_name)
        if error:
            error = "Controllare le quantità inserite per i seguenti lotti (deve essere maggiore di zero e non superiore alla quantità disponibile):\n" + error
            raise UserError(error)
        
        product_to_move = {}
        for move in self.move_lines:
            if product_to_move.get(move.product_id):
               product_to_move[move.product_id]['qty'] += move.product_qty_totr
               product_to_move[move.product_id]['lots'].append({'qty':move.product_qty_totr,'lot':move.lot_id})
            else:
               product_to_move[move.product_id] = {'uom':move.product_uom.id,'qty':move.product_qty_totr,'lots':[{'qty':move.product_qty_totr,'lot':move.lot_id}]}
        picking = self.env['stock.picking'].create({'move_type': 'one',
                                                    'date': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                                    'date_done': time.strftime(DEFAULT_SERVER_DATETIME_FORMAT),
                                                    'location_id': self.location_id.id,
                                                    'location_dest_id': self.location_dest_id.id,
                                                    'picking_type_id': self.picking_type_id.id,
                                                    'note': self.note})
        for product, det in product_to_move.items():
            self.env['stock.move'].create({'name': product.display_name,
                                           'product_id': product.id,
                                           'product_uom_qty': det['qty'],
                                           'product_uom': det['uom'],
                                           'location_id': self.location_id.id,
                                           'location_dest_id': self.location_dest_id.id,
                                           'picking_id': picking.id})
            operation = self.env['stock.pack.operation'].create({'picking_id': picking.id,
                                                                 'product_qty': det['qty'],
                                                                 'qty_done': det['qty'],
                                                                 'product_id': product.id,
                                                                 'location_id': self.location_id.id,
                                                                 'location_dest_id': self.location_dest_id.id,
                                                                 'product_uom_id': det['uom']})
            for lot in det['lots']:
                if lot['lot']:
                    self.env['stock.pack.operation.lot'].create({'operation_id': operation.id,
                                                                 'lot_id': lot['lot'].id,
                                                                 'lot_name': lot['lot'].display_name,
                                                                 'qty_todo': lot['qty'],
                                                                 'qty': lot['qty']})
                                                                 
        picking.do_transfer()
        
        formview_id = self.env['ir.model.data'].get_object_reference('stock', 'view_picking_form')[1]       
        return {
            "type": "ir.actions.act_window",
            "name": "Picking Creato e Trasferito",
            "view_type": "form",
            "view_mode": "form",
            "view_id": formview_id,
            "views": [(formview_id, 'form')],
            "res_model": "stock.picking",
            "res_id": picking.id,
        }

class WizardCreateMove(models.TransientModel):
    _name = "wizard.create.move"
    
    picking_id = fields.Many2one('wizard.create.picking', 'Transfer Reference')
    product_id = fields.Many2one(
        'product.product', 'Prodotto', readonly=True)
    product_id_name = fields.Char('Prodotto', related='product_id.display_name', readonly=True)
    product_qty = fields.Float('Quantità Disponibile', readonly=True)
    product_uom = fields.Many2one(
        'product.uom', 'Unità di Misura', readonly=True)
    product_uom_name = fields.Char('Unità di Misura', related='product_uom.display_name', readonly=True)        
    lot_id = fields.Many2one(
        'stock.production.lot', 'Lotto', readonly=True)
    lot_id_name = fields.Char('Lotto', related='lot_id.display_name', readonly=True)        
    product_qty_totr = fields.Float('Quantità da Trasferire', required=True, default=0.)           
