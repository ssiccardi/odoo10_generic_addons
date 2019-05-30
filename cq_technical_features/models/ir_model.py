# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models

class IrModelFields(models.Model):
    _inherit = 'ir.model.fields'
    
    show_create_and_edit = fields.Boolean('Mostra crea e modifica', default=False)
    
    @api.multi
    def write(self, vals):
        show_create_and_edit = vals.pop('show_create_and_edit', None)
        
        res = super(IrModelFields, self).write(vals)
        
        if show_create_and_edit is not None:
            self._cr.execute("UPDATE ir_model_fields SET show_create_and_edit = %s WHERE id in (%s)"%(show_create_and_edit, ','.join(map(str, self.ids))))
            
        return res
