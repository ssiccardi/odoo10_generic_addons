# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
# Bisogna importare _ e usarlo nei raise per avere i messaggi tradotti
import logging
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
import odoo.addons.decimal_precision as dp

        
class AccountInvoice(models.Model):
    _inherit='account.invoice'
    
      
    
    internal_number = fields.Char(string='Manual Invoice Number', help="Unique number of the invoice, computed automatically when the invoice is created.")
    
    @api.multi
    @api.constrains('internal_number')
    def action_number(self):
        for bill in self:
            if bill.internal_number:
                # e' inutile scrivere number, la fattura non e' validata
                #self.write({'number': bill.internal_number})
                # cosi' viene scritto due volte! e' inutile!
                #new_num = 'UPDATE account_invoice SET number=internal_number WHERE id=%s' %bill.id 
                #self._cr.execute(new_num)
                # facciamo il controllo prima di scrivere! E solo fra le fatture dello stesso tipo (potrebbe cmq creare dei doppi con fatture/note di cr)
                check_num = self.search(['&', ('type','=',bill.type), '|', ('number', '=', bill.internal_number), ('move_name', '=', bill.internal_number)])
                if len(check_num)!=0:
                    if check_num.id != bill.id:
                        raise ValidationError(_('Invoice Number must be unique!'))
                new_move_name = 'UPDATE account_invoice SET move_name=internal_number WHERE id=%s' %bill.id 
                self._cr.execute(new_move_name)
               
                #str = 'DELETE FROM fatture_fornitori WHERE part_id = %s and user_id = %s'  % (part_id, uid)
                #self._cr.execute(str)
            return bill.internal_number
                
