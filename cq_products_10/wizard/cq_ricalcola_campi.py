# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class CQRicalcolaCampi(models.TransientModel):

    _inherit = 'cq.ricalcola.campi'

#// Wizard per copiare campi descrizione prodotti dai template alle varianti
    @api.multi
    def recompute_variant_descriptions(self):
        ProductProduct = self.env['product.product']
        ProductTemplate = self.env['product.template']
        IrTranslation = self.env['ir.translation']

        field_names = [
            'description_sale', 'description', 
            'description_purchase', 'description_picking'
        ]
        ctx_lang = self.env.context.get('lang') # language of current session

        for field_name in field_names:
            prod_domain = [
                (field_name,'=',False), ('product_tmpl_id','!=',False)
            ]
            products = ProductProduct.search(prod_domain, order='product_tmpl_id')
            for product in products:
                product.write(
                    {field_name: product.product_tmpl_id[field_name]}
                )
                template_transl = IrTranslation.search(
                    [('name','=','product.template,' + field_name),
                     ('res_id','=',product.product_tmpl_id.id),
                     ('lang','=','it_IT'),
                     '|',('src','!=',False),('value','!=',False)
                    ], limit=1
                )
                if template_transl:
                    product_transl = IrTranslation.search(
                        [('name','=','product.product,' + field_name),
                         ('res_id','=',product.id), ('lang','=','it_IT'),]
                    )
                    product_transl.write(
                        {'src': template_transl.src, 'value': template_transl.value}
                    )

        return {'type': 'ir.actions.act_window_close'}
