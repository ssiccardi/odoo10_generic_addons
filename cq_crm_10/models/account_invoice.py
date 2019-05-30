# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class AccountInvoice(models.Model):
    _inherit = "account.invoice"

    @api.multi
    def action_invoice_open(self):
        for invoice in self:
            if invoice.type in ('out_invoice','out_refund'):
                partner = invoice.partner_id
                partner_ids = self.env['res.partner'].search([('id','child_of',partner.id)]) or self.env['res.partner'].browse()
                while partner.parent_id:
                    partner_ids |= partner.parent_id
                    partner = partner.parent_id
                partner_ids.write({'is_prospect':False})
        return super(AccountInvoice,self).action_invoice_open()
