# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2017 CQ Creativi Quadrati (http://www.creativiquadrati.it)
#
#    License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
#
##############################################################################

from odoo import models, fields, api

class AccountInvoice(models.Model):
    
    _inherit = 'account.invoice'

    totale_documento = fields.Monetary(string='Totale Documento',
        store=True, readonly=True, compute='_compute_totale_documento')
    
    @api.one
    @api.depends('invoice_line_ids.price_subtotal', 'tax_line_ids.amount', 'currency_id', 'company_id', 'date_invoice', 'type')
    def _compute_totale_documento(self):
        amount_new = 0.0
        amount_tax = 0.0
        for line in self.invoice_line_ids:
            if not (line.product_id and line.product_id.sp_type == 'sconto'):
                amount_new += line.price_subtotal
                taxes = line.invoice_line_tax_ids.compute_all(
                (line.price_unit * (1 - (line.discount or 0.0) / 100.0)),
                self.currency_id, line.quantity, line.product_id, self.partner_id)['taxes']                
                amount_tax += sum(tax['amount'] for tax in taxes)
        totale_documento = amount_new + amount_tax      
        if self.currency_id and self.company_id and self.currency_id != self.company_id.currency_id:
            currency_id = self.currency_id.with_context(date=self.date_invoice)
            totale_documento = currency_id.compute(totale_documento, self.company_id.currency_id)
        self.totale_documento = totale_documento
