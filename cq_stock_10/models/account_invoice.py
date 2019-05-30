# -*- coding: utf-8 -*-

from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.tools import float_is_zero, float_compare

from odoo.exceptions import UserError, RedirectWarning, ValidationError


class AccountInvoice(models.Model):
    _inherit = "account.invoice"
    
    #al momento della validazione di una fattura fornitore scrivo il costo reale sui quanti legati al movimento di ingresso
    @api.multi
    def invoice_validate(self):
        res = super(AccountInvoice, self).invoice_validate()
        for invoice in self:
            if invoice.type == 'in_invoice':
                for line in invoice.invoice_line_ids:
                    purchase_line = line.purchase_line_id
                    if purchase_line:
                        product = purchase_line.product_id
                        if product and product.type in ['product', 'consu']:
                            invoice_lines = purchase_line.invoice_lines.filtered(lambda x: x.product_id==product and x.invoice_id.type=='in_invoice')
                            if invoice_lines:
                                order = purchase_line.order_id
                                qty = 0
                                price = 0
                                for invoice_line in invoice_lines:
                                    if invoice_line.uom_id and invoice_line.uom_id!=product.uom_id:
                                        qty += invoice_line.uom_id._compute_quantity(invoice_line.quantity, product.uom_id, round=False)
                                    else:
                                        qty += invoice_line.quantity
                                    if invoice_line.invoice_id.currency_id != order.company_id.currency_id:
                                        price += invoice_line.invoice_id.currency_id.compute(invoice_line.price_subtotal, order.company_id.currency_id, round=False)
                                    else:
                                        price += invoice_line.price_subtotal
                                if float_compare(qty, 0, precision_rounding = product.uom_id.rounding) > 0:
                                    price_unit = price / qty
                                    purchase_line.sudo().mapped('move_ids.quant_ids').write({'real_unit_cost': price_unit}) 
        return res
