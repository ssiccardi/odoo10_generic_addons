# -*- coding:UTF-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import odoo.addons.decimal_precision as dp


class ProductTemplate(models.Model):
    _inherit = 'product.template'

#//Eredita product.template
#//Aggiunge la gestione dei codici prodotto obbligatori ed eventualmente automatici per categoria
    @api.onchange('categ_id')
    @api.depends('categ_id')
    def _code_is_required(self):
        self.code_is_required = not self._get_seq_from_categ(self.categ_id and self.categ_id.id or False)

    @api.model
    def _get_seq_from_categ(self, categ_id):
        temp_cat = categ_id
        sequenza = False
        while temp_cat and not sequenza:
            sequenza = self.env['cat.products'].search([('name','=',temp_cat)])
            parent_cat = self.env['product.category'].search([('id','=',temp_cat)]).parent_id
            if parent_cat:
                temp_cat = parent_cat.id
            else:
                temp_cat = False
        return sequenza

    @api.model
    def _get_code_from_category(self, categ_id):
        sequenza = self._get_seq_from_categ(categ_id)
        code = False
        if sequenza:
            code = sequenza.prefix or ''
            tmpcode = str(sequenza.next_number)
            if len(tmpcode) < sequenza.zeri:
                tmpcode = '0' * (sequenza.zeri - len(tmpcode)) + tmpcode
            code += tmpcode
            sequenza.next_number += 1
        return code

    @api.one
    @api.constrains('default_code')
    def _check_code_unique_and_required(self):
        if not self.default_code:
            new_code = self._get_code_from_category(self.categ_id.id)
            if new_code is False:
                raise ValidationError(_('The product code is mandatory, but the category and its parents have no sequences.'))
            elif self.search([('id','!=', self.id),('default_code', '=', new_code)]):
                raise ValidationError(_('Another product has the same code %s that would be generated. Check the sequence of the product category.')% new_code)
            else:
                self.default_code = new_code
        elif self.search([('id','!=', self.id),('default_code', '=', self.default_code)]):
            raise ValidationError(_('Another product has the same code %s. It must be unique.') %self.default_code)

    @api.multi
    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        self.ensure_one()
        default['default_code'] = self._get_code_from_category(self.categ_id.id) or ( self.default_code + _(' (Copy)') )
        return super(ProductTemplate, self).copy(default=default)

    @api.one
    def _set_unique_variant_code(self):
        if len(self.product_variant_ids) == 1 and not self._context.get('not_update_variant_code'):
            self.with_context(dict(not_update_template_code=True)).product_variant_ids.default_code = self.default_code

    @api.one
    def _set_unique_variant_descriptions(self):
        if (
            len(self.product_variant_ids) == 1 and
            not self._context.get('not_update_variant_descriptions')
        ):
            ctx = self.env.context.copy()
            ctx['not_update_template_descriptions'] = True
            self.with_context(ctx).product_variant_ids.description = self.description
            self.with_context(ctx).product_variant_ids.description_sale = self.description_sale
            self.with_context(ctx).product_variant_ids.description_purchase = self.description_purchase
            self.with_context(ctx).product_variant_ids.description_picking = self.description_picking


#//Definisce i tipi speciali spedizione, descrizione, cessione grautuita, sconto cassa
    code_is_required = fields.Boolean('Codice obbligatorio?', compute='_code_is_required')
    default_code = fields.Char(compute=False, inverse='_set_unique_variant_code')
    p_suff_default_code = fields.Integer(default=1, copy=False)
    type = fields.Selection([
        ('consu', _('Consumable')),
        ('service', _('Service')),
        ('product', _('Stockable Product'))], string='Product Type', default='product', required=True,
        help='A stockable product is a product for which you manage stock. The "Inventory" app has to be installed.\n'
             'A consumable product, on the other hand, is a product for which stock is not managed.\n'
             'A service is a non-material product you provide.\n'
             'A digital content is a non-material product you sell online. The files attached to the products are the one that are sold on '
             'the e-commerce such as e-books, music, pictures,... The "Digital Product" module has to be installed.')
    sp_type = fields.Selection([
        ('ship',_('Shipment')),
        ('desc',_('Description')),
        ('sconto','Cessione Gratuita'),
        ('sconto_cassa','Sconto Cassa')], string='Special Type')
    weight_gross = fields.Float(string='Peso Lordo', digits=dp.get_precision('Stock Weight'),
        help="Il peso lordo: la somma del peso netto e dell'imballaggio, in Kg")
    description = fields.Text(
        'Description', translate=True, inverse='_set_unique_variant_descriptions',
        help="A precise description of the Product, used only for internal information purposes."
    )
    description_purchase = fields.Text(
        'Purchase Description', translate=True, inverse='_set_unique_variant_descriptions',
        help="A description of the Product that you want to communicate to your vendors. "
             "This description will be copied to every Purchase Order, Receipt and Vendor Bill/Refund."
    )
    description_sale = fields.Text(
        'Sale Description', translate=True, inverse='_set_unique_variant_descriptions',
        help="A description of the Product that you want to communicate to your customers. "
             "This description will be copied to every Sale Order, Delivery Order and Customer Invoice/Refund"
    )
    description_picking = fields.Text(
        'Description on Picking', translate=True, inverse='_set_unique_variant_descriptions'
    )

#//Imposta per default fatturazione su consegna per prodotti fisici e su ordine per servizi
    @api.onchange('type')
    def onchange_invoice_policy(self):
        if self.type == 'service':
            self.invoice_policy = 'order'
        else:
            self.invoice_policy = 'delivery'

    @api.onchange('type')
    def _onchange_type(self):
        ''' Override the original onchange, because it triggered the
            track_service field on value "timesheet" when product's type turned
            into "service".
        '''
        if self.type:
            self.track_service = 'manual'


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.one
    def _set_template_code(self):
        template = self.product_tmpl_id
        if not self._context.get('not_update_template_code') and template:
            if len(template.product_variant_ids) == 1:
                self.with_context(
                    dict(not_update_variant_code=True)
                ).product_tmpl_id.default_code = self.default_code

    @api.one
    def _set_template_descriptions(self):
        template = self.product_tmpl_id
        if not self._context.get('not_update_template_descriptions') and template:
            if len(template.product_variant_ids) == 1:
                ctx = self.env.context.copy()
                ctx['not_update_variant_descriptions'] = True
                self.with_context(ctx).product_tmpl_id.description = self.description
                self.with_context(ctx).product_tmpl_id.description_sale = self.description_sale
                self.with_context(ctx).product_tmpl_id.description_purchase = self.description_purchase
                self.with_context(ctx).product_tmpl_id.description_picking = self.description_picking


    default_code = fields.Char(compute=False, inverse='_set_template_code')
    lst_price = fields.Float(compute='_compute_product_lst_price',inverse='_set_template_list_price')
    price = fields.Float(inverse='_set_product_price')
    free_price = fields.Float('Prezzo libero', digits=dp.get_precision('Product Price'))
    force_price = fields.Boolean('Forza Prezzo', help="Forza prezzo.\nSpuntare e inserire il prezzo se non si vuole usare il calcolo automatico.")
    description = fields.Text(
        'Description', translate=True, inverse='_set_template_descriptions',
        help="A precise description of the Product, used only for internal information purposes."
    )
    description_purchase = fields.Text(
        'Purchase Description', translate=True, inverse='_set_template_descriptions',
        help="A description of the Product that you want to communicate to your vendors. "
             "This description will be copied to every Purchase Order, Receipt and Vendor Bill/Refund."
    )
    description_sale = fields.Text(
        'Sale Description', translate=True, inverse='_set_template_descriptions',
        help="A description of the Product that you want to communicate to your customers. "
             "This description will be copied to every Sale Order, Delivery Order and Customer Invoice/Refund"
    )
    description_picking = fields.Text(
        'Description on Picking', translate=True, inverse='_set_template_descriptions'
    )

    @api.model
    def create(self, vals):

        product = super(ProductProduct, self).create(vals)
        template = product.product_tmpl_id
        if template:
            if len(template.product_variant_ids) == 1:
                product.default_code = template.default_code
            elif len(template.product_variant_ids) > 1:
                product.default_code = (template.default_code or '') + '-' + str(template.p_suff_default_code)
                template.p_suff_default_code += 1
#// Descrizioni template-variante indipendenti:
#// funzione "Create" delle varianti riempie le descrizioni della variante
#//se sono vuote, prendendole dal template
            if not product.description and template.description:
                product.description = template.description
            if not product.description_sale and template.description_sale:
                product.description_sale = template.description_sale
            if not product.description_purchase and template.description_purchase:
                product.description_purchase = template.description_purchase
            if not product.description_picking and template.description_picking:
                product.description_picking = template.description_picking

        return product

    @api.multi
    def unlink(self):
        #se il template ha solo una variante non è possibile forzare il prezzo tramite il campo free_price perchè 
        #viene direttamente reso non readonly il campo lst_price che deve essere uguale al campo list_price del template
        templates = self.mapped('product_tmpl_id')
        res = super(ProductProduct, self).unlink()
        for template in templates:
            if template.exists() and template.product_variant_count == 1:
                template.product_variant_ids.write({'force_price':False})
        return res

    @api.one
    @api.constrains('default_code')
    def _check_variant_code_unique_and_required(self):
        if not self.default_code:
            raise ValidationError(_('The product code is mandatory.'))
        elif self.search([('id','!=', self.id),('default_code', '=', self.default_code)]):
            raise ValidationError(_('Another product has the same code %s. It must be unique.') %self.default_code)

    @api.multi
    @api.depends('list_price', 'price_extra', 'force_price', 'free_price')
    def _compute_product_lst_price(self):
        to_uom = None
        if 'uom' in self._context:
            to_uom = self.env['product.uom'].browse([self._context['uom']])
        for product in self:
            if product.force_price:
                product.lst_price = product.free_price
            else:
                if to_uom:
                    list_price = product.uom_id._compute_price(product.list_price, to_uom)
                else:
                    list_price = product.list_price
                product.lst_price = list_price + product.price_extra

    @api.multi
    def _set_template_list_price(self):
        for product in self:
            if product.product_tmpl_id and len(product.product_tmpl_id.product_variant_ids) == 1:
                if product.force_price:
                    value = product.free_price
                else:
                    value = product.lst_price - product.price_extra
                if self._context.get('uom'):
                    value = self.env['product.uom'].browse(self._context['uom'])._compute_price(product.lst_price, product.uom_id)
                product.write({'list_price': value})        

    @api.multi
    def _set_product_price(self):
        for product in self:
            if product.product_tmpl_id and len(product.product_tmpl_id.product_variant_ids) == 1:
                if self._context.get('uom'):
                    value = self.env['product.uom'].browse(self._context['uom'])._compute_price(product.price, product.uom_id)
                else:
                    value = product.price
                if not product.force_price:
                    value -= product.price_extra
                product.write({'list_price': value})

    #devo sovrascrivere la funzione price_compute perchè non tiene conto del prezzo forzato
    @api.multi
    def price_compute(self, price_type, uom=False, currency=False, company=False):
        if not uom and self._context.get('uom'):
            uom = self.env['product.uom'].browse(self._context['uom'])
        if not currency and self._context.get('currency'):
            currency = self.env['res.currency'].browse(self._context['currency'])

        products = self
        if price_type == 'standard_price':
            # standard_price field can only be seen by users in base.group_user
            # Thus, in order to compute the sale price from the cost for users not in this group
            # We fetch the standard price as the superuser
            products = self.with_context(force_company=company and company.id or self._context.get('force_company', self.env.user.company_id.id)).sudo()

        prices = dict.fromkeys(self.ids, 0.0)
        for product in products:
            prices[product.id] = product[price_type] or 0.0
            if price_type == 'list_price':
                if product.force_price:
                    prices[product.id] = product.free_price
                else:
                    prices[product.id] += product.price_extra

            if uom:
                prices[product.id] = product.uom_id._compute_price(prices[product.id], uom)

            # Convert from current user company currency to asked one
            # This is right cause a field cannot be in more than one currency
            if currency:
                prices[product.id] = product.currency_id.compute(prices[product.id], currency)

        return prices

class CatProd(models.Model):
    _name = 'cat.products'
    
    name = fields.Many2one('product.category', 'Category Name')
    prefix = fields.Char('Prefix')
    next_number = fields.Integer('Next Number')
    zeri = fields.Integer('# of digits')

# Modifico l'ordinamento della classe ProductPriceHistory
# Bugfix: nel caso di prodotti importati con un programma di import, si creano due record di questa classe che hanno lo stesso datetime e la funzione get_history_price considera quello sbagliato
# aggiungo l'id nell'ordinamento per risolvere il problema
class ProductPriceHistory(models.Model):

    _inherit = 'product.price.history'
    _order = 'datetime desc, id desc'


