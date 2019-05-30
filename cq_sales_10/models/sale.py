# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.api import onchange
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_is_zero, float_compare, DEFAULT_SERVER_DATETIME_FORMAT
from lxml import etree
import json

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.multi
    @api.depends(
        'pricelist_id.currency_id', 'amount_untaxed', 'amount_total',
        'order_line.invoice_lines.invoice_id.state'
    )
    def _compute_residual(self):
        ''' Compute order residual amount not invoiced yet '''
        for order in self:
            residual = order.amount_total
            residual_untaxed = order.amount_untaxed
            inv_states = ['open', 'paid']
            invoices = order.sudo().invoice_ids.filtered(
                lambda i: i.type == 'out_invoice' and i.state in inv_states
            )
            for inv in invoices:
                if order.currency_id == inv.currency_id:
                    residual -= inv.amount_total
                    residual_untaxed -= inv.amount_untaxed
                else:
                    inv_total_converted = inv.currency_id.compute(
                        inv.amount_total, order.currency_id
                    )
                    inv_untaxed_converted = inv.currency_id.compute(
                        inv.amount_untaxed, order.currency_id
                    )
                    residual -= inv_total_converted
                    residual_untaxed -= inv_untaxed_converted

            precision = order.currency_id.rounding
            if float_compare(residual_untaxed, 0., precision_digits=precision) < 0.:
                order.residual_untaxed = 0.
            else:
                order.residual_untaxed = residual_untaxed
            if float_compare(residual, 0., precision_digits=precision) < 0.:
                order.residual_total = 0.
            else:
                order.residual_total = residual


    delivery_date = fields.Date(string='Delivery date')
    data_concordata = fields.Date(string='Agreed Delivery Date')
#// Eliminato campo Ultima Data Concordata dalle viste e dalle funzioni.
#// La dichiarazione del campo e' stata mantenuta nel .py per evitare errori in fasi di aggiornamento
#// delle viste sul database. Il campo dovra' essere ridefinito nel modulo forecast a tempo debito.
    last_agreed_delivery_date = fields.Date(string='Last Agreed Delivery Date')
    residual_untaxed = fields.Monetary(
        string='Untaxed Residual', store=True, readonly=True,
        compute='_compute_residual', track_visibility='always',
        help="Untaxed order amount that is not invoiced yet"
    )
    residual_total = fields.Monetary(
        string='Total Residual', store=True, readonly=True,
        compute='_compute_residual', track_visibility='always',
        help="Total order amount (including taxes) that is not invoiced yet"
    )


#// Modificato bottone Cambia Data Concordata:
#// mostra poup di avviso per sovrascrivere le righe dell'ordine con la data dall'ordine
    @api.multi
    def show_popup_change_date(self):
        self.ensure_one()
        view = self.env.ref('cq_sales_10.popup_form_change_data_concordata')
        return {
            'type': 'ir.actions.act_window',
            #'name': "Confirm 'Agreed Delivery Dates' replacement",
            'res_model': 'change.data.concordata',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': view.id,
            'target': 'new',
        }

    @api.multi
    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if not order.order_line:
                raise UserError('You cannot confirm an empty sale order.')
            #max_data_concordata = max([line.data_concordata for line in order.order_line])
            for line in order.order_line:
                if not line.data_concordata:
                    line.data_concordata = order.confirmation_date
            max_data_concordata = max(order.order_line.mapped('data_concordata'))
            order.data_concordata = max_data_concordata

        return res


    @api.depends('order_line.price_total','order_line.prodotto_sconto')
    def _amount_all(self):
        """
        Compute the total amounts of the SO.
        """
        for order in self:
            amount_untaxed = tamount_tax = amount_tax = totale_documento = 0.0
            for line in order.order_line:
                if not line.prodotto_sconto:
                    amount_untaxed += line.price_subtotal
                # FORWARDPORT UP TO 10.0
                if order.company_id.tax_calculation_rounding_method == 'round_globally':
                    price = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
                    taxes = line.tax_id.compute_all(price, line.order_id.currency_id, line.product_uom_qty, product=line.product_id, partner=order.partner_shipping_id)
                    tamount_tax = sum(t.get('amount', 0.0) for t in taxes.get('taxes', []))
                else:
                    tamount_tax = line.price_tax
                totale_documento += (tamount_tax + line.price_subtotal)
                if not line.prodotto_sconto or line.prodotto_sconto == 'rivalsa':
                    amount_tax += tamount_tax
            order.update({
                'amount_untaxed': order.pricelist_id.currency_id.round(amount_untaxed),
                'amount_tax': order.pricelist_id.currency_id.round(amount_tax),
                'amount_total': order.pricelist_id.currency_id.round(amount_untaxed + amount_tax),
                'totale_documento': order.pricelist_id.currency_id.round(totale_documento),
            })

    @api.depends('amount_total')
    def _calcola_sconto_cassa(self):
        for order in self:
            sconto_cassa = 0.0
            lines = order.order_line.filtered(lambda x: x.product_id and x.product_id.sp_type == 'sconto_cassa')
            ammontare_sconto_cassa = lines and abs(sum([line.price_total for line in lines])) or 0.
            order.ammontare_sconto_cassa = order.pricelist_id.currency_id.round(ammontare_sconto_cassa)

    @api.one
    @api.constrains('perc_sconto_cassa')
    def _gestisci_sconto_cassa(self):
        perc_sc_cassa = self.perc_sconto_cassa
        if perc_sc_cassa > 100 or perc_sc_cassa < 0:
            raise ValidationError('Lo sconto cassa deve essere compreso tra 0 e 100.')
        self.order_line.filtered(lambda x: x.product_id and x.product_id.sp_type == 'sconto_cassa').unlink()
        if perc_sc_cassa:
            if self.order_line.filtered(lambda x: x.prodotto_sconto == 'rivalsa') and perc_sc_cassa:
                raise ValidationError("Non è possibile inserire uno sconto cassa con merce in cessione gratuita con rivalsa IVA.")
            product = self.env['product.product'].search([('sp_type','=','sconto_cassa')])
            product = len(product) == 1 and product[0] or False
            if not product:
                raise ValidationError("Impossibile trovare il prodotto speciale per lo sconto cassa. Per proseguire è neseccario configurare un prodotto di tipo sconto cassa.")
            lines = self.order_line.filtered(lambda x: x.prodotto_sconto != 'norivalsa')
            result = {}
            max_sequence = 0.
            for line in lines:
                max_sequence = max_sequence > line.sequence and max_sequence or line.sequence+1
                tax_ids = [tax.id for tax in line.tax_id]
                tax_ids.sort()
                tax_ids = tuple(tax_ids)
                if tax_ids in result:
                    result[tax_ids] += line.price_subtotal
                else:
                    result[tax_ids] = line.price_subtotal
            for tax_ids, amount in result.items():
                if float_is_zero(amount, precision_rounding=self.pricelist_id.currency_id.rounding):
                    continue
                self.env['sale.order.line'].create({
                           'order_id': self.id,
                           'product_id': product.id,
                           'name': product.name,
                           'sequence': max_sequence,
                           'price_unit': -1 * amount * perc_sc_cassa / 100.,
                           'tax_id': [(6, 0, tax_ids)],
                })

    @api.one
    def _get_n_sale_seq(self):
        self.n_sale_sequences = len(self.env['ir.sequence'].search([('code','like','sale.order')]))

    perc_sconto_cassa = fields.Float(string='% Sconto Cassa', states={'cancel': [('readonly', True)], 'done': [('readonly', True)]})
    ammontare_sconto_cassa = fields.Monetary(string='Totale Sconto Cassa', readonly=True, compute='_calcola_sconto_cassa')
    totale_documento = fields.Monetary(string='Totale Documento', readonly=True, compute='_amount_all')
    sale_sequence = fields.Many2one('ir.sequence', 'Sale sequence', required=True, domain=[('code','like','sale.order')], default=lambda self: self.env['ir.sequence'].search([('code', '=', 'sale.order')]))
    n_sale_sequences = fields.Integer('Number of sale sequences',compute='_get_n_sale_seq',default=lambda self:len(self.env['ir.sequence'].search([('code','like','sale.order')])))
    vers_numb = fields.Integer('Version Number', default=0)
    #data di conferma non readonly
    confirmation_date = fields.Datetime(string='Confirmation Date', readonly=False, index=True, help="Date on which the sale order is confirmed.", oldname="date_confirm")
#// Conto analitico su SO copiato in fase di duplica/nuova versione
    project_id = fields.Many2one(
        'account.analytic.account', 'Analytic Account', readonly=True,
        states={'draft': [('readonly', False)], 'sent': [('readonly', False)]},
        help="The analytic account related to a sales order.", copy=True
    )

    @api.multi
    def action_invoice_create(self, grouped=False, final=False):
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for order in self:
            if order.perc_sconto_cassa and not all([float_compare(line.qty_to_invoice, line.product_uom_qty, precision_digits=precision) == 0 for line in order.order_line]):
                raise UserError("Non tutte le righe sono completamente fatturabili!\nSe è presente sconto cassa è neccessario fatturare l'intero ordine di vendita.")
        return super(SaleOrder,self).action_invoice_create(grouped=grouped, final=final)

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            x = self.env['ir.sequence'].search([('id', '=', vals.get('sale_sequence'))]).code
            vals['name'] = self.env['ir.sequence'].next_by_code(x)
#// Data concordata dell'ordine creata alla creazione delle date concordate sulle righe
        order = super(SaleOrder, self).create(vals)
        if order.order_line:
            max_data_concordata = max(order.order_line.mapped('data_concordata'))
            order.write({'data_concordata': max_data_concordata})
        return order

    @api.multi
    def write(self, vals):
        res = super(SaleOrder, self).write(vals)
#// Data concordata dell'ordine modificata alla modifica delle date concordate sulle righe
        if vals.get('order_line', None):
            # vals_lines is a list of lists: each sublist corresponds to a sale order's line
            # Each sublist has 3 components:
            #   a) an integer in [0,1,2,4]
            #   For reference about integer meanings:
            #   https://www.odoo.com/documentation/10.0/reference/orm.html#model-reference
            #   (look at "CRUD" paragraph) - one2many and many2many
            #       0 - new sale.order.line
            #       1 - existing line with same field edited by this write call
            #       2 - deleted line by this call
            #       4 - existing line which doesn't change
            #   b) sale.order.line ID or 'False' (False only for case 0)
            #   c) edited/created field values dictionary (False only for caes 2 and 4)
            vals_lines = vals.get('order_line')
            for order in self:
                max_data_concordata = order.order_line and max(order.order_line.mapped('data_concordata')) or False
                for vals_line in vals_lines:
                    if vals_line[0] == 0:
                        super(SaleOrder, self).write({'data_concordata': max_data_concordata})
                        break
                    elif vals_line[0] == 1 and 'data_concordata' in vals_line[2]:
                        super(SaleOrder, self).write({'data_concordata': max_data_concordata})
                        break
                    elif vals_line[0] == 2:
                        super(SaleOrder, self).write({'data_concordata': max_data_concordata})
                        break
        return res

    @api.multi
    def copy_cancel(self):
        new_vers_numb = self.vers_numb + 1
        if new_vers_numb == 1:
            name = self.name + '_1'
        else:
            name = self.name[:self.name.rfind('_')] + '_' + str(new_vers_numb)
        default = {'date_order': fields.Datetime.now(), 'vers_numb': new_vers_numb, 'name': name}
        data = self.copy_data(default)
        new = self.create(data[0])
        if self.state != 'cancel':
            self.write({'state': 'cancel'})
        view_id = self.env['ir.model.data'].get_object_reference('sale', 'view_order_form')[1]
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Order'),
            'res_model': 'sale.order',
            'res_id': new.id,
            'view_type': 'form',
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'current',
        }


    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(SaleOrder, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu
        )
        ''' Variable domains on partner_shipping_id and partner_invoice_id according to
            sale_order_partner_domain value
            (which is determined by sale_order_partner_domain on sale.config.settings).
            Same for residual_untaxed field on order list view
        '''
        IrValues = self.env['ir.values']
        form_id = self.env['ir.model.data'].get_object_reference(
            'sale', 'view_order_form'
        )[1]
        order_tree_id = self.env['ir.model.data'].get_object_reference(
            'sale', 'view_order_tree'
        )[1]
        sale_order_partner_domain = IrValues.get_default(
            'sale.config.settings', 'sale_order_partner_domain'
        )
        sale_order_show_residual = IrValues.get_default(
            'sale.config.settings', 'sale_order_show_residual'
        )
        doc = etree.XML(res['arch'])

        if view_type == 'form' and (view_id in [form_id, None]):
                #shipping_domain = partner_shipping_nodes.get('domain', '[]')
                #invoice_domain = partner_invoice_nodes.get('domain', '[]')
            partner_shipping_nodes = doc.xpath(
                "//field[@name='partner_shipping_id']"
            )
            partner_invoice_nodes = doc.xpath(
                "//field[@name='partner_invoice_id']"
            )
            if sale_order_partner_domain == 0:
                for node in partner_shipping_nodes:
                    node.set("domain", "[('customer','=',True)]")
                for node in partner_invoice_nodes:
                    node.set("domain", "[('customer','=',True)]")
            elif sale_order_partner_domain == 1:
                for node in partner_shipping_nodes:
                    node.set(
                        "domain", "[('customer','=',True), ('id','child_of',partner_id)]"
                    )
                for node in partner_invoice_nodes:
                    node.set(
                        "domain", "[('customer','=',True), ('id','child_of',partner_id)]"
                    )
        elif view_type == 'tree' and (view_id in [order_tree_id, None]):
            residual_nodes = doc.xpath("//field[@name='residual_untaxed']")
            if sale_order_show_residual == 0:
                for node in residual_nodes:
                    node.set("invisible", "True")
                    modifiers = json.loads(node.get("modifiers"))
                    modifiers['tree_invisible'] = True
                    node.set("modifiers", json.dumps(modifiers))
            elif sale_order_partner_domain == 1:
                for node in residual_nodes:
                    node.set("invisible", "False")
                    modifiers = json.loads(node.get("modifiers"))
                    modifiers['tree_invisible'] = False
                    node.set("modifiers", json.dumps(modifiers))

        res['arch'] = etree.tostring(doc)
        return res


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    delivery_date = fields.Date(string='Delivery date')
    data_concordata = fields.Date(string='Agreed Delivery Date')
    prodotto_sconto = fields.Selection([('rivalsa','Con Rivalsa IVA'),
                                        ('norivalsa','Senza Rivalsa IVA')], string='Cessione Gratuita', default=False)
#// Eliminato campo Ultima Data Concordata SOLO dalle viste e dalle funzioni.
#// La dichiarazione del campo e' stata mantenuta nel .py per evitare errori in fasi di aggiornamento
#// delle viste sul database. Il campo dovra' essere ridefinito nel modulo forecast a tempo debito.
    last_agreed_delivery_date = fields.Date(string='Last Agreed Delivery Date')


    @api.onchange('delivery_date') # if these fields are changed, call method
    def change_delivery_date(self):
        maxdate = max([order.delivery_date for order in self.order_id.order_line])
        if self.delivery_date == maxdate :
            self.order_id.delivery_date = maxdate
        values = { }
        values['delivery_date'] = maxdate
        self.update(values)

    @api.onchange('product_id')
    def _onchange_product_id_set_data_concordata(self):
        if self.product_id and self.order_id and self.order_id.date_order:
            self.data_concordata = datetime.strptime(self.order_id.date_order, DEFAULT_SERVER_DATETIME_FORMAT)\
                                    + timedelta(days=self.customer_lead or 0.0)

    def _prepare_order_line_procurement(self, group_id):

        for line in self:
            order = line.order_id
            if line.data_concordata:
                date_planned = fields.Datetime.from_string(line.data_concordata)
            #~ elif (
                #~ line.order_id.data_concordata and
                #~ all([not line.data_concordata for line in order.order_line])
            #~ ):
                #~ date_planned = fields.Datetime.from_string(line.order_id.data_concordata)
            #~ elif (
                #~ line.order_id.data_concordata and
                #~ any([line.data_concordata for line in order.order_line])
            #~ ):
                #~ date_planned = fields.Datetime.from_string(line.order_id.confirmation_date)
            elif not line.data_concordata and line.order_id.confirmation_date:
                date_planned = fields.Datetime.from_string(line.order_id.confirmation_date)
            else:
                date_planned = datetime.strptime(self.order_id.date_order, DEFAULT_SERVER_DATETIME_FORMAT)\
                    + timedelta(days=self.customer_lead or 0.0) - timedelta(days=self.order_id.company_id.security_lead)

        self.ensure_one()
        return {
            'name': self.name,
            'origin': self.order_id.name,
            'date_planned': date_planned,
            'product_id': self.product_id.id,
            'product_qty': self.product_uom_qty,
            'product_uom': self.product_uom.id,
            'company_id': self.order_id.company_id.id,
            'group_id': group_id,
            'sale_line_id': self.id,
            'location_id': self.order_id.partner_shipping_id.property_stock_customer.id,
            'route_ids': self.route_id and [(4, self.route_id.id)] or [],
            'warehouse_id': self.order_id.warehouse_id and self.order_id.warehouse_id.id or False,
            'partner_dest_id': self.order_id.partner_shipping_id.id,
        }


    @api.multi
    def unlink(self):
        if self.filtered(lambda x: x.state in ('sale', 'done') and x.product_id and not x.product_id.sp_type):
            raise UserError(_('You can not remove a sale order line.\nDiscard changes and try setting the quantity to 0.'))
        return super(models.Model, self).unlink()

    @api.one
    @api.constrains('prodotto_sconto')
    def _no_sconto_cassa_cessione_gratuita_con_rivalsa(self):
        if self.prodotto_sconto == 'rivalsa' and self.order_id.perc_sconto_cassa:
            raise ValidationError("Non è possibile inserire uno sconto cassa con merce in cessione gratuita con rivalsa IVA.")

    @api.multi
    def invoice_line_create(self, invoice_id, qty):
        """
        Create an invoice line. The quantity to invoice can be positive (invoice) or negative
        (refund).

        :param invoice_id: integer
        :param qty: float quantity to invoice
        """
        #ereditata per aggiungere la riga di cessione gratuita
        product = self.env['product.product'].search([('sp_type','=','sconto')])
        product = len(product) == 1 and product[0] or False
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        for line in self:
            if not float_is_zero(qty, precision_digits=precision):
                vals = line._prepare_invoice_line(qty=qty)
                vals.update({'invoice_id': invoice_id, 'sale_line_ids': [(6, 0, [line.id])]})
                invoice_line = self.env['account.invoice.line'].create(vals)
                if not product and line.prodotto_sconto:
                    raise UserError("Impossibile trovare il prodotto speciale per la cessione gratuita. Per proseguire è neseccario configurare un prodotto di tipo cessione gratuita.")
                if product and line.prodotto_sconto:
                    if line.prodotto_sconto == 'rivalsa':
                        tax_id = product.taxes_id.filtered(lambda x: x.amount == 0)
                    else:
                        tax_id = product.taxes_id.filtered(lambda x: x.amount == line.tax_id[0].amount)
                    if not tax_id or len(tax_id) > 1:
                        raise UserError("Impossibile trovare l'imposta per la merce in cessione gratuita. Correggere le imposte presenti sul prodotto %s"%product.display_name)
                    vals={
                        'invoice_id': invoice_id,
                        'sale_line_ids': [(6, 0, [line.id])],
                        'name': product.name,
                        'sequence': invoice_line.sequence,
                        'origin': invoice_line.origin,
                        'price_unit': invoice_line.price_unit*(-1),
                        'quantity': invoice_line.quantity,
                        'discount': 0.,
                        'uom_id': invoice_line.uom_id.id,
                        'product_id': product.id,
                        'account_id': product.property_account_income_id.id,
                        'invoice_line_tax_ids': [(6, 0, [tax_id.id])],
                        'account_analytic_id': invoice_line.account_analytic_id and invoice_line.account_analytic_id.id or False,
                    }
                    self.env['account.invoice.line'].create(vals)



class ChangeDataConcordata(models.TransientModel):
    _name = 'change.data.concordata'
    _description = 'Wizard for changing Agreed Delivery Dates on sale order lines'

    def _get_data_concordata(self):
        order = self.env['sale.order'].browse(self.env.context['active_id'])
        return order.data_concordata

    data_concordata = fields.Date(string='Agreed Delivery Date', default=_get_data_concordata,
        help="Agreed Delivery Date from sale order")


    #@api.depends('order_line.data_concordata')
    @api.multi
    def get_the_date(self):
        self.ensure_one()
        if 'active_id' in self.env.context:
            order_id = self.env.context.get('active_id', None)
        elif unicode('active_id') in self.env.context:
            order_id = self.env.context.get(unicode('active_id'), None)
        else:
            order_id = None
        if order_id:
            order = self.env['sale.order'].browse(order_id)
            order.order_line.write( {'data_concordata': order.data_concordata} )

        return True
