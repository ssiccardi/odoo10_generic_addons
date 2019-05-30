# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, models
import json
import ast

class View(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def postprocess(self, model, node, view_id, in_tree_view, model_fields):
        """Inherited to modify the options for 'Create and Edit' according to the flag in the table ir_model_fields"""
        
        fields = super(View, self).postprocess(model, node, view_id, in_tree_view, model_fields)
        Model = self.env[model]

        if node.tag in ('field', 'node', 'arrow'):
            name = node.get('name')
            if name:
                field = Model._fields.get(name)
                if field and field.comodel_name in self.env and field.type in ('many2one', 'many2many'):
                    self._cr.execute("SELECT show_create_and_edit FROM ir_model_fields WHERE model='%s' AND name='%s' LIMIT 1"%(model,name))
                    show_create_and_edit = self._cr.fetchone()
                    if show_create_and_edit:
                        show_create_and_edit = show_create_and_edit[0]
                        options = node.get('options')
                        if options:
                            options = ast.literal_eval(options.strip())
                        else:
                            options = {}
                        if show_create_and_edit:
                            options.update({'no_create_edit': False})
                        else:
                            options.update({'no_create_edit': True})
                        node.set('options', json.dumps(options))

        return fields
