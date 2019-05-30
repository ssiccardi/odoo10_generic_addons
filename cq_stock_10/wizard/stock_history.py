# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools
from odoo.fields import Datetime as fieldsDatetime


class StockHistory(models.Model):
    _inherit = 'stock.history'

    # modifico l'ordinamento su product_price_history per lo stesso motivo descritto in cq_products_10 file product.py
    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        res = super(StockHistory, self).read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        if 'inventory_value' in fields:
            date = self._context.get('history_date', fieldsDatetime.now())
            stock_history = self.env['stock.history']
            group_lines = {}
            for line in res:
                domain = line.get('__domain', domain)
                group_lines.setdefault(str(domain), self.search(domain))
                stock_history |= group_lines[str(domain)]

            histories_dict = {}
            not_real_cost_method_products = stock_history.mapped('product_id').filtered(lambda product: product.cost_method != 'real')
            if not_real_cost_method_products:
                self._cr.execute("""SELECT DISTINCT ON (product_id, company_id) product_id, company_id, cost
                    FROM product_price_history
                    WHERE product_id in %s AND datetime <= %s
                    ORDER BY product_id, company_id, datetime DESC, id DESC""", (tuple(not_real_cost_method_products.ids), date))
                for history in self._cr.dictfetchall():
                    histories_dict[(history['product_id'], history['company_id'])] = history['cost']

            for line in res:
                inv_value = 0.0
                for stock_history in group_lines.get(str(line.get('__domain', domain))):
                    product = stock_history.product_id
                    if product.cost_method == 'real':
                        price = stock_history.price_unit_on_quant
                    else:
                        price = histories_dict.get((product.id, stock_history.company_id.id), 0.0)
                    inv_value += price * stock_history.quantity
                line['inventory_value'] = inv_value

        return res
