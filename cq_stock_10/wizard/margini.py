# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo
import datetime
from odoo import api, fields, models, _
from odoo.tools.float_utils import float_round, float_compare
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

## HOWTO fix the Unicode special characters issue
## https://stackoverflow.com/questions/21129020/how-to-fix-unicodedecodeerror-ascii-codec-cant-decode-byte
import sys
reload(sys)
sys.setdefaultencoding('utf8')

class StockQuant(models.Model):

    _inherit = "stock.quant"

    @api.multi
    def _calc_margine(self):
        for quant in self:
            margine = quant.price_out - quant.price_in
            qty = quant.qty
            quant.margine = margine
            quant.margine_u = qty and margine/qty or 0.

    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        #modifico la read_group in models.py perchè i margini sono campi funzione non store e perchè il margine unitario non è la somma dei margini unitari dei record raggruppati
        #il parametro group_operator nella definizione del campo permette l'iserimento solo della somma o della media tra i record raggruppati
        res = super(StockQuant, self).read_group(domain=domain, fields=fields, groupby=groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        if 'margine_u' in fields:
            for line in res:
                line['margine'] = line.get('price_out',0) - line.get('price_in',0)
                qty = line.get('qty',0)
                line['margine_u'] = qty and line['margine']/qty or 0
        return res
                        
    price_out = fields.Float('Prezzo di Vendita', digits=dp.get_precision('Product Price'))
    price_in = fields.Float("Prezzo d'Acquisto", digits=dp.get_precision('Product Price'))
    data_uscita = fields.Date('Data vendita')
    cliente = fields.Many2one('res.partner','Cliente')
    fornitore = fields.Many2one('res.partner','Fornitore')
    margine = fields.Float(compute='_calc_margine',string="Margine",digits=dp.get_precision('Product Price'))
    margine_u = fields.Float(compute='_calc_margine', string="Margine Unitario",digits=dp.get_precision('Product Price'))

    def query_anagrafica(self):
        #query che considera i prezzi in anagrafica prodotti
        #la valuta sulla scheda prodotto è quella aziendale
        #l'unità di misura sui quanti coincide con quella sulla scheda prodotto (non servono equivalenze)
        return '''
            WITH values_table AS (
                SELECT q.id as id, q.qty * pt.list_price as price_out, q.qty * ph.cost as price_in, max(m.date) as data_uscita
                FROM stock_quant q 
                JOIN stock_quant_move_rel rel ON q.id=rel.quant_id
                JOIN stock_move m ON m.id=rel.move_id
                JOIN stock_location sl ON sl.id=m.location_dest_id
                JOIN product_product p ON q.product_id=p.id                
                JOIN product_template pt ON pt.id=p.product_tmpl_id
                JOIN product_price_history ph ON ph.id = (SELECT id 
                                                          FROM product_price_history tph
                                                          WHERE tph.company_id=q.company_id and tph.product_id=q.product_id and tph.datetime<=COALESCE(q.in_date, NOW())
                                                          ORDER BY tph.datetime desc
                                                          LIMIT 1)
                WHERE sl.usage = 'customer'
                GROUP BY q.id, p.id, pt.id, ph.id
            )
            UPDATE stock_quant q
            SET price_out = val.price_out, price_in = val.price_in, data_uscita = val.data_uscita::date
            FROM values_table val
            WHERE q.id = val.id
        '''

    def query_clienti(self):
        #query clienti considerando i prezzi delle fatture validate
        #multivaluta
        #con equivalenza tra unità di misura del quanto e unità di misura segnata in fattura
        return '''
            WITH currency_rate (currency_id, company_id, rate, date_start, date_end) AS (%s)        
            UPDATE stock_quant q
            SET 
                price_out = val.price * q.qty / val.qty_il,
                cliente = val.cliente
            FROM 
            (   SELECT q.id as id,
                       sum(il.price_subtotal / COALESCE(cr.rate, 1)) as price, 
                       sum(il.quantity / puom.factor * puom2.factor) as qty_il, 
                       min(ai.partner_id) as cliente
                FROM stock_quant q 
                JOIN stock_quant_move_rel rel ON q.id=rel.quant_id            
                JOIN stock_move m ON m.id=rel.move_id
                JOIN procurement_order p ON p.id=m.procurement_id
                JOIN sale_order_line_invoice_rel rel2 ON rel2.order_line_id=p.sale_line_id
                JOIN account_invoice_line il ON il.id=rel2.invoice_line_id
                JOIN account_invoice ai ON ai.id=il.invoice_id
                LEFT JOIN currency_rate cr ON
                    (cr.currency_id = ai.currency_id AND
                     cr.company_id = q.company_id AND
                     cr.date_start <= COALESCE(ai.date, NOW()) AND
                     (cr.date_end IS NULL OR cr.date_end > COALESCE(ai.date, NOW())))
                JOIN product_uom puom ON il.uom_id = puom.id
                JOIN product_product pp ON q.product_id=pp.id
                JOIN product_template pt ON pt.id=pp.product_tmpl_id
                JOIN product_uom puom2 ON pt.uom_id = puom2.id                         
                WHERE ai.type='out_invoice' and ai.state in ('open','paid')
                GROUP BY q.id) AS val
            WHERE q.id = val.id
        '''%(self.env['res.currency']._select_companies_rates())

    def query_fornitori(self):
        #query fornitori considerando i prezzi delle fatture validate
        #multivaluta
        #con equivalenza tra unità di misura del quanto e unità di misura segnata in fattura
        return '''
            WITH currency_rate (currency_id, company_id, rate, date_start, date_end) AS (%s)
            UPDATE stock_quant q
            SET
                price_in = val.price * q.qty / val.qty_il,
                fornitore = val.fornitore
            FROM 
            (   SELECT q.id as id, 
                       sum(il.price_subtotal / COALESCE(cr.rate, 1)) as price, 
                       sum(il.quantity / puom.factor * puom2.factor) as qty_il,
                       min(ai.partner_id) as fornitore
                FROM stock_quant q 
                JOIN stock_quant_move_rel rel ON q.id=rel.quant_id            
                JOIN stock_move m ON m.id=rel.move_id
                JOIN purchase_order_line pol ON pol.id=m.purchase_line_id
                JOIN account_invoice_line il ON il.purchase_line_id=pol.id
                JOIN account_invoice ai ON ai.id=il.invoice_id
                LEFT JOIN currency_rate cr ON
                    (cr.currency_id = ai.currency_id AND
                     cr.company_id = q.company_id AND
                     cr.date_start <= COALESCE(ai.date, NOW()) AND
                     (cr.date_end IS NULL OR cr.date_end > COALESCE(ai.date, NOW())))
                JOIN product_uom puom ON il.uom_id = puom.id
                JOIN product_product pp ON q.product_id=pp.id
                JOIN product_template pt ON pt.id=pp.product_tmpl_id
                JOIN product_uom puom2 ON pt.uom_id = puom2.id                                                    
                WHERE ai.type='in_invoice' and ai.state in ('open','paid')
                GROUP BY q.id) AS val
            WHERE q.id = val.id
        '''%(self.env['res.currency']._select_companies_rates())

    @api.model
    def update_records_margini(self):
        with api.Environment.manage():
            with odoo.registry(self.env.cr.dbname).cursor() as new_cr:
                # Create a new environment with new cursor database
                new_env = api.Environment(new_cr, self.env.uid, self.env.context)
                # with_env replace original env for this method
                self = self.with_env(new_env)
                self._cr.execute(self.query_anagrafica())
                self.env.cr.commit()
                self._cr.execute(self.query_clienti())
                self.env.cr.commit()
                self._cr.execute(self.query_fornitori())
                self.env.cr.commit()
