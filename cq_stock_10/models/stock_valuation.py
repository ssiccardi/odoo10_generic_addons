# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.exceptions import UserError, AccessError, ValidationError
import odoo.addons.decimal_precision as dp
from datetime import datetime
from dateutil import relativedelta
import pytz


def datetime_to_date(datetime_str, from_tz, to_tz):
    from_tz = pytz.timezone(from_tz)
    to_tz = pytz.timezone(to_tz)
    date_from = datetime.strptime(datetime_str, DEFAULT_SERVER_DATETIME_FORMAT)
    date_from = from_tz.localize(date_from)
    date_to = date_from.astimezone(to_tz).date()
    date_to = datetime.strftime(date_to, "%d/%m/%Y")
    return date_to


class StockValuation(models.Model):

    _name="cq.stock.valuation"
    _description = "Valorizzazione magazzino LIFO, FIFO, CMP e CSR"


    '''
        Le tipologie di valorizzazione tengono conto del campo real_unit_cost di stock.quant, questo campo deve perciò essere valorrizato secondo le fatture fornitori, per gli item aquistati,
        e secondo gli ordini di produzione, per gli item prodotti.

        Se la quantità è negativa (oppure se i movimenti non coprono la quantità presente) viene scritto -1 sia come quantità che come valore.
        
        Ad eccezione del costo specifico reale, la valorizzazione viene effettuata considerando la quantità totale in tutti i magazzini, che viene poi ripartita
        proporzionalmente per i vari punti di stoccaggio in base alle quantità.

        I metodi di valutazione per ora implementati sono:
         - LIFO a scatti con valorizzazione al costo medio ponderato della quantità aggiunta nel periodo
         - FIFO
         - costo medio ponderato di periodo
         - costo specifico reale

        I metodi di valutazione per ora NON implementati sono:
         - LIFO continuo
         - LIFO a scatti con la quantità aggiunta nel periodo valorizzata al LIFO di periodo
         - LIFO di periodo
         - costo medio ponderato a scatti (quest'ultimo dovrebbe però coincidere con il metodo di costo standard di Oddo che si ha impostando sul prodotto il metodo di costo 'average')
    '''


    @api.multi
    def name_get(self):
        return [(valuation.id, 'Valorizzazione del ' + datetime_to_date(valuation.data_chiusura, 'UTC', self._context.get('tz', 'UTC'))) for valuation in self]


    @api.model
    def _get_selezione_metodo(self):
        if self.env.user.has_group('stock.group_production_lot'):
            return [('lifo', 'LIFO'), ('fifo', 'FIFO'), ('cmp', 'Costo Medio Ponderato'), ('csr', 'Costo Specifico Reale')]
        else:
            return [('lifo', 'LIFO'), ('fifo', 'FIFO'), ('cmp', 'Costo Medio Ponderato')]


    data_chiusura = fields.Datetime(string="Data Rimanenza", required=True, default=fields.Datetime.now)
    metodo = fields.Selection(_get_selezione_metodo, string="Metodo", required=True, default=lambda self: self.search([], limit=1).metodo)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.user.company_id)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', string='Valuta', readonly=True)
    state = fields.Selection([('draft', 'Bozza'), ('confirmed', 'Confermato')], string='Stato', readonly=True, default='draft')
    valuation_lines = fields.One2many('cq.stock.valuation.line', 'valuation_id', string="Linee Valorizzazione")
    tot_val = fields.Monetary(currency_field='currency_id', compute='_get_total_val', string="Totale", readonly=True, store=True)
    
    _order = "data_chiusura desc"


    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        raise AccessError('La duplica non è permessa')


    @api.multi
    def unlink(self):
        if self.filtered(lambda x: x.state != 'draft'):
            raise UserError('Non puoi cancellare valorizzazioni di magazzino non in bozza.')
        return super(StockValuation, self).unlink()


    @api.multi
    @api.depends('currency_id', 'valuation_lines', 'valuation_lines.value')
    def _get_total_val(self):
        for val in self:
            val.tot_val = sum(line.value for line in val.valuation_lines if float_compare(line.qty, 0, precision_rounding=line.uom_id.rounding) >= 0)


    @api.multi
    def action_confirm(self):
        self.write({'state': 'confirmed'})


    @api.multi
    def action_set_to_draft(self):
        self.write({'state': 'draft'})


    @api.multi
    def action_view_details(self):
        self.ensure_one()
        action = {
            "type": "ir.actions.act_window",
            "name": "Dettagli",
            "view_mode": "tree,form",
            "res_model": "cq.stock.valuation.line",
            "domain": [('valuation_id','in', self.ids)],
            "context": dict(self.env.context, default_valuation_id = self.ids[0], metodo=self.metodo, search_default_group_by_product_id=1)
        }
        if self.state == 'confirmed':
            action['context'].update({"done": True})
            view_id = self.env.ref('cq_stock_10.view_stock_valuation_lines_cq_tree_done').id
        else:
            view_id = self.env.ref('cq_stock_10.view_stock_valuation_lines_cq_tree').id
        action.update({
            "views": [(view_id, 'tree')],
            "view_id": view_id,})
        if self.env.user.has_group('base.group_multi_company'):
            action['context'].update({"search_default_group_by_location":1})
        return action


    @api.multi
    def replace_valuation_line(self):
        self.ensure_one()
        self.valuation_lines.unlink()
        if self.metodo == 'lifo':
            self.LIFO_A_SCATTI()
        elif self.metodo == 'fifo':
            self.FIFO()
        elif self.metodo == 'cmp':
            self.COSTO_MEDIO_PONDERATO_DI_PERIDO()
        elif self.metodo == 'csr':
            self.COSTO_SPECIFICO_REALE()
        return self.action_view_details()


    @api.multi
    def base_subquery(self):
        return '''  SELECT
                        dest_location.id AS location_id,
                        dest_location.company_id AS company_id,
                        stock_move.product_id AS product_id,
                        product_template.uom_id AS uom_id,
                        quant.qty AS qty,
                        stock_move.date AS date,
                        quant.real_unit_cost as unit_value,
                        stock_production_lot.id AS lot_id
                    FROM
                        stock_quant as quant
                    JOIN
                        stock_quant_move_rel ON stock_quant_move_rel.quant_id = quant.id
                    JOIN
                        stock_move ON stock_move.id = stock_quant_move_rel.move_id
                    LEFT JOIN
                        stock_production_lot ON stock_production_lot.id = quant.lot_id
                    JOIN
                        stock_location dest_location ON stock_move.location_dest_id = dest_location.id
                    JOIN
                        stock_location source_location ON stock_move.location_id = source_location.id
                    JOIN
                        product_product ON product_product.id = stock_move.product_id
                    JOIN
                        product_template ON product_template.id = product_product.product_tmpl_id
                    WHERE quant.qty>0 AND stock_move.state = 'done' AND dest_location.usage in ('internal', 'transit')
                    AND (
                        not (source_location.company_id is null and dest_location.company_id is null) or
                        source_location.company_id != dest_location.company_id or
                        source_location.usage not in ('internal', 'transit')
                    )
                    UNION ALL
                    (SELECT
                        source_location.id AS location_id,
                        source_location.company_id AS company_id,
                        stock_move.product_id AS product_id,
                        product_template.uom_id AS uom_id,
                        - quant.qty AS qty,
                        stock_move.date AS date,
                        quant.real_unit_cost as unit_value,
                        stock_production_lot.id AS lot_id
                    FROM
                        stock_quant as quant
                    JOIN
                        stock_quant_move_rel ON stock_quant_move_rel.quant_id = quant.id
                    JOIN
                        stock_move ON stock_move.id = stock_quant_move_rel.move_id
                    LEFT JOIN
                        stock_production_lot ON stock_production_lot.id = quant.lot_id
                    JOIN
                        stock_location source_location ON stock_move.location_id = source_location.id
                    JOIN
                        stock_location dest_location ON stock_move.location_dest_id = dest_location.id
                    JOIN
                        product_product ON product_product.id = stock_move.product_id
                    JOIN
                        product_template ON product_template.id = product_product.product_tmpl_id
                    WHERE quant.qty>0 AND stock_move.state = 'done' AND source_location.usage in ('internal', 'transit')
                    AND (
                        not (dest_location.company_id is null and source_location.company_id is null) or
                        dest_location.company_id != source_location.company_id or
                        dest_location.usage not in ('internal', 'transit')
                    ))
               '''


    @api.multi
    def total_splitted_query(self, company_id, data):
        return '''  WITH inv_details AS (
                        %s
                    ), tot_val AS (
                        SELECT  product_id,
                                uom_id,
                                SUM(qty) AS qty
	                    FROM inv_details
                        WHERE company_id = %s AND date < '%s'::timestamp
                        GROUP BY product_id, uom_id
                    ), split_val AS (
                        SELECT  product_id,
                                location_id,
                                SUM(qty) AS qty
	                    FROM inv_details
                        WHERE company_id = %s AND date < '%s'::timestamp
                        GROUP BY product_id, location_id
                    )
                    SELECT tot_val.product_id AS product_id,
                           tot_val.uom_id AS uom_id,
                           tot_val.qty AS qty_tot,
                           split_val.location_id AS location_id,
                           split_val.qty AS qty
                    FROM split_val
                    JOIN tot_val ON split_val.product_id = tot_val.product_id
               '''%( self.base_subquery(), company_id, data, company_id, data ) 


    @api.model
    def LIFO_A_SCATTI(self):
        stock_move_env = self.env['stock.move']
        valuation_line_env = self.env["cq.stock.valuation.line"]
        product_uom_env = self.env['product.uom']
        precedenti = self.search([('company_id','=',self.company_id.id),('data_chiusura', '<', self.data_chiusura),('state','=','confirmed')], order='data_chiusura asc')
        prev_val = False
        if precedenti:
            prev_val = precedenti[-1]
        move_domain = [('location_dest_id.company_id','=',self.company_id.id),
                       ('location_dest_id.usage', 'in', ['internal','transit']),
                       ('location_id.usage', 'not in', ['internal','transit','view']),
                       ('date', '<', self.data_chiusura),
                       ('state','=','done')]
        if prev_val:
            move_domain += [('date', '>=', prev_val.data_chiusura)]
        self._cr.execute( self.total_splitted_query(self.company_id.id, self.data_chiusura) )
        for line in self._cr.dictfetchall():
            uom = product_uom_env.browse(line['uom_id'])
            if not float_is_zero(line['qty'], precision_rounding=uom.rounding):
                if float_compare(line['qty_tot'], 0, precision_rounding = uom.rounding) <= 0 or float_compare(line['qty'], 0, precision_rounding = uom.rounding) < 0:
                    line['value'] = -1
                    line['qty'] = -1
                else:
                    qty_I = 0
                    value_I = 0
                    if prev_val:
                        for prev_line in valuation_line_env.search([('product_id','=',line['product_id']), ('valuation_id','=',prev_val.id), ('qty','>',0), ('value','>=',0)]):
                            qty_I += prev_line.uom_id._compute_quantity(prev_line.qty, uom, round=False)
                            value_I += prev_line.value
                    qty_tot = line.pop('qty_tot')
                    if float_compare(qty_tot, qty_I, precision_rounding = uom.rounding) == 0:
                        line['value'] = value_I / qty_I * line['qty']
                    elif float_compare(qty_tot, qty_I, precision_rounding = uom.rounding) > 0:
                        t_move_domain = move_domain + [('product_id', '=', line['product_id'])]
                        qty = 0
                        value = 0
                        for move in stock_move_env.search(t_move_domain):
                            qty += move.product_qty
                            value += move.real_unit_cost * move.product_qty
                        if not qty:
                            line['value'] = -1
                            line['qty'] = -1
                        else:
                            cmp_u = value / qty
                            new_value_tot = (qty_tot - qty_I) * cmp_u + value_I
                            line['value'] = new_value_tot / qty_tot * line['qty']
                    else:
                        value_tot = 0
                        qty_rimanente = qty_tot
                        errore = False
                        for prec in precedenti:
                            qty = 0
                            value = 0
                            for pline in prec.valuation_lines.filtered(lambda x: x.product_id.id == line['product_id'] and x.qty > 0 and x.value >= 0):
                                qty += pline.uom_id._compute_quantity(pline.qty, uom, round=False)
                                value += pline.value
                            if float_compare(qty, 0, precision_rounding = uom.rounding) < 0:
                                errore = True
                                break
                            if float_is_zero(qty, 0, precision_rounding = uom.rounding):
                                continue
                            value_tot += min(qty,qty_rimanente) * value / qty
                            qty_rimanente -= qty
                            if float_compare(qty_rimanente, 0, precision_rounding = uom.rounding) <= 0:
                                break
                        if errore:
                            line['value'] = -1
                            line['qty'] = -1
                        else:
                            line['value'] = value_tot / qty_tot * line['qty']
                self.write({'valuation_lines': [(0, 0, line)]})
        return True


    @api.model
    def FIFO(self):
        stock_move_env = self.env['stock.move']
        product_uom_env = self.env['product.uom']
        move_domain = [('location_dest_id.company_id','=',self.company_id.id),
                       ('location_dest_id.usage', 'in', ['internal','transit']),
                       ('location_id.usage', 'not in', ['internal','transit','view']),
                       ('date', '<', self.data_chiusura),
                       ('state','=','done')]
        self._cr.execute( self.total_splitted_query(self.company_id.id, self.data_chiusura) )
        for line in self._cr.dictfetchall():
            uom = product_uom_env.browse(line['uom_id'])
            if not float_is_zero(line['qty'], precision_rounding=uom.rounding):
                if float_compare(line['qty_tot'], 0, precision_rounding = uom.rounding) <= 0 or float_compare(line['qty'], 0, precision_rounding = uom.rounding) < 0:
                    line['value'] = -1
                    line['qty'] = -1
                else:
                    qty_residual = qty_tot = line.pop('qty_tot')
                    value = 0
                    t_move_domain = move_domain + [('product_id', '=', line['product_id'])]
                    for move in stock_move_env.search(t_move_domain, order="date desc"):
                        qty = min(qty_residual, move.product_qty)
                        value += move.real_unit_cost * qty
                        qty_residual -= qty
                        if float_compare(qty_residual, 0, precision_rounding = uom.rounding) <= 0:
                            break
                    if float_compare(qty_residual, 0, precision_rounding = uom.rounding) > 0:
                        line['qty'] = -1
                        line['value'] = -1
                    else:
                        line['value'] = value / qty_tot * line['qty']
                self.write({'valuation_lines': [(0, 0, line)]})
        return True


    @api.model
    def COSTO_MEDIO_PONDERATO_DI_PERIDO(self):
        stock_move_env = self.env['stock.move']
        valuation_line_env = self.env["cq.stock.valuation.line"]
        product_uom_env = self.env['product.uom']
        prev_val = self.search([('company_id','=',self.company_id.id),
                                ('data_chiusura', '<', self.data_chiusura), 
                                ('state','=','confirmed')], order='data_chiusura desc', limit=1)
        move_domain = [('location_dest_id.company_id','=',self.company_id.id),
                       ('location_dest_id.usage', 'in', ['internal','transit']),
                       ('location_id.usage', 'not in', ['internal','transit','view']),
                       ('date', '<', self.data_chiusura),
                       ('state','=','done')]
        if prev_val:
            move_domain += [('date', '>=', prev_val.data_chiusura)]
        self._cr.execute(
        ''' SELECT  location_id,
                    product_id,
                    uom_id,
                    SUM(qty) AS qty
            FROM ( %s ) AS tbl
            WHERE company_id = %s AND date < '%s'::timestamp
            GROUP BY product_id, location_id, uom_id
        ''' %( self.base_subquery(), self.company_id.id, self.data_chiusura ) )
        for line in self._cr.dictfetchall():
            quantity = line['qty']
            uom = product_uom_env.browse(line['uom_id'])
            if not float_is_zero(quantity, precision_rounding=uom.rounding):
                product_id = line['product_id']
                vals = {
                    'product_id': product_id,
                    'uom_id': uom.id,
                    'location_id': line['location_id'],
                    'value': -1,
                    'qty': -1,
                }
                if float_compare(quantity, 0, precision_rounding = uom.rounding) > 0:
                    vals['qty'] = quantity
                    value = 0
                    qty = 0
                    for move in stock_move_env.search(move_domain + [('product_id','=',product_id)]):
                        qty += move.product_qty
                        value += move.real_unit_cost * move.product_qty
                    if prev_val:
                        for prev_line in valuation_line_env.search([('product_id','=',product_id), ('valuation_id', '=', prev_val.id), ('qty','>',0), ('value','>=',0)]):
                            qty += prev_line.uom_id._compute_quantity(prev_line.qty, uom, round=False)
                            value += prev_line.value
                    if qty:
                        vals['value'] = value / qty * quantity
                self.write({'valuation_lines': [(0, 0, vals)]})
        return True


    @api.model
    def COSTO_SPECIFICO_REALE(self):
        valuation_line_env = self.env["cq.stock.valuation.line"]
        valuation_line_lots_env = self.env["cq.stock.valuation.line.lots"]
        product_uom_env = self.env['product.uom']
        self._cr.execute(
        ''' SELECT  location_id,
                    product_id,
                    lot_id,
                    uom_id,
                    SUM(qty) AS qty,
                    SUM(qty * unit_value) AS value
            FROM ( %s ) AS tbl
            WHERE company_id = %s AND date < '%s'::timestamp
            GROUP BY lot_id, product_id, location_id, uom_id
            ORDER BY location_id asc, product_id asc
        ''' %( self.base_subquery(), self.company_id.id, self.data_chiusura ) )
        location_id = False
        product_id = False
        valuation_line = False
        for line in self._cr.dictfetchall():
            uom = product_uom_env.browse(line['uom_id'])
            if not float_is_zero(line['qty'], precision_rounding=uom.rounding):
                if product_id != line['product_id'] or location_id != line['location_id']:
                    product_id = line['product_id']
                    location_id = line['location_id']
                    if valuation_line:
                        valuation_line.save()
                    valuation_line = valuation_line_env.create({'valuation_id': self.ids[0], 
                                                                'qty': 0, 
                                                                'product_id': product_id,
                                                                'location_id': location_id,
                                                                'value': 0, 
                                                                'uom_id': line['uom_id']})
                valuation_line_lots_env.create({'valuation_line_id': valuation_line.id,
                                                'lot_id': line['lot_id'] or False,
                                                'qty': line['qty'],
                                                'value': line['value'],
                                                'uom_id': line['uom_id']})
        if valuation_line:
            valuation_line.save()
        return True


class StockValuationLine(models.Model):

    _name="cq.stock.valuation.line"

    valuation_id = fields.Many2one('cq.stock.valuation', string="Valutazione", required=True, ondelete="cascade", 
                                    default=lambda self: self._context.get('default_valuation_id', False))
    qty = fields.Float(string="Quantità", required=True, digits=dp.get_precision('Product Unit of Measure'))
    location_id = fields.Many2one('stock.location', string="Punto di Stoccaggio", required=True, domain=[('usage','=','internal')])
    currency_id = fields.Many2one('res.currency', related='valuation_id.currency_id', string='Valuta')
    product_id = fields.Many2one('product.product', string="Prodotto", required=True, domain=[("type",'in',['product','consu'])])
    value = fields.Monetary(currency_field='currency_id', string='Valore', required=True)
    uom_id = fields.Many2one('product.uom', string="Unità di Misura", required=True)
    category_id = fields.Many2one('product.uom.categ', related='product_id.uom_id.category_id', string="Categoria Unità di Misura")
    valuation_lines_lots = fields.One2many('cq.stock.valuation.line.lots', 'valuation_line_id', string="Linee Valorizzazione Lotti")

    _order = "location_id asc"

    @api.one
    @api.constrains('location_id', 'product_id', 'valuation_id')
    def _check_unique_product_id(self):
        if self.valuation_id and self.product_id and self.location_id and \
           self.valuation_id.valuation_lines.filtered(lambda x: x.id != self.id and x.product_id == self.product_id and x.location_id == self.location_id):
            raise ValidationError(u"Hai già inserito il prodotto in un'altra riga!")

    @api.onchange('product_id')
    def _product_onchange(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id


    @api.multi
    def split_lot(self):
        self.ensure_one()
        view_id = self.env.ref('cq_stock_10.view_stock_valuation_lines_cq_form').id
        return {
            'name': 'Lotti o S/N',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'cq.stock.valuation.line',
            'views': [(view_id, 'form')],
            'view_id': view_id,
            'target': 'new',
            'res_id': self.ids[0],
            'context': dict(self.env.context)}


    @api.multi
    def save(self):
        self.ensure_one()
        self.value = sum(line.value for line in self.valuation_lines_lots)
        self.qty = sum(line.uom_id._compute_quantity(line.qty, self.uom_id) for line in self.valuation_lines_lots)
        return {'type': 'ir.actions.act_window_close'}


class StockValuationLineLots(models.Model):

    _name="cq.stock.valuation.line.lots"

    valuation_line_id = fields.Many2one('cq.stock.valuation.line', string="Linea Valorizzazione", ondelete="cascade")
    currency_id = fields.Many2one('res.currency', related='valuation_line_id.currency_id', string='Valuta')
    qty = fields.Float(string="Quantità", required=True, digits=dp.get_precision('Product Unit of Measure'))
    value = fields.Monetary(currency_field='currency_id', string='Valore', required=True)
    uom_id = fields.Many2one('product.uom', string="Unità di Misura", required=True)
    lot_id = fields.Many2one('stock.production.lot', string="Lotto o S/N")

    @api.one
    @api.constrains('lot_id', 'valuation_line_id')
    def _check_unique_lot_id(self):
        if self.valuation_line_id and self.lot_id and self.valuation_line_id.valuation_lines_lots.filtered(lambda x: x.id != self.id and x.lot_id == self.lot_id):
            raise ValidationError(u"Hai già inserito il lotto in un'altra riga!")

    @api.onchange('lot_id')
    def _lot_onchange(self):
        if self.lot_id:
            self.uom_id = self.lot_id.product_uom_id


