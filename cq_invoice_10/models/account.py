# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
# Bisogna importare _ e usarlo nei raise per avere i messaggi tradotti
import logging
from odoo.exceptions import UserError, ValidationError, RedirectWarning
from datetime import date, datetime, timedelta
import odoo.addons.decimal_precision as dp

_logger=logging.getLogger(__name__)

class fatture_fornitori(models.Model):
    _name = 'fatture.fornitori'
    _description = 'Summary of previous invoices of the supplier'
#//Elenco delle fatture fornitori gia registrate per evitare doppi inserimenti

    part_id = fields.Integer('Supplier')
    user_id = fields.Integer('User')
    num_interno = fields.Char('Internal Reference', size=32)
    num_esterno = fields.Char('Supplier Reference', size=32)
    data_fatt = fields.Date('Invoice Date')
    data_scad = fields.Date('Due Date')
    data_reg = fields.Date('Registration Date')
    saldo = fields.Float('Residual Amount')
    subtotale = fields.Float('Amount Untaxed')
    totale = fields.Float('Total Amount')


class AccountJournal(models.Model):
    _inherit = "account.journal"
#//Eredita acoount.journal

#//Il flag no_tax_check esclude le righe della fattura dal controllo sull'aliquota iva
    no_tax_check = fields.Boolean('No Tax Check', default=False)
    

class AccountInvoice(models.Model):
    _inherit='account.invoice'
#//Eredita account.invoice

#//Controlla che le righe con un valore abbiano almeno una aliquota iva
#//Escludo la fattura dal controllo se il sezionale ha no_tax_check attivo
#//Gestisce la data contabile
    @api.model
    @api.constrains('invoice_line_ids')
    def CheckLimit(self):
        for record in self:
            if record.journal_id.no_tax_check:
                continue
            for line in record.invoice_line_ids:
                if not line.invoice_line_tax_ids:
                    if line.price_subtotal:
                        raise ValidationError (_('Lines with an amount must have a tax code'))

    comment = fields.Text('Additional Information', readonly=False) # Always editable
    n_proforma = fields.Char('Proforma Number')
    payed_date=fields.Date('Payment Date', readonly=True, compute="_getPayedDate")

#//Gestisce la data di pagamento
    @api.model
    def _getPayedDate(self):
        for day in self:
            date=""
            if day.state=='paid':
                pagamenti=self.env['account.payment'].search([('invoice_ids', 'in', day.id)])
                if pagamenti:
                    for pag in pagamenti:
                        date=pag.payment_date
            elif day.state=='draft' or 'open':
                date=""
            day.payed_date=date

#//Compila la banca 
    @api.model
    def create(self, vals):
        ''' When the new invoice doesn't have partner_bank_id into vals,
            it looks through the invoice's partner and the user's company
            in order to get a default bank value
        '''
        Partner = self.env['res.partner']
        Users = self.env['res.users']
        Company = self.env['res.company']
        # Se è di tipo vendita o non c'è il tipo nei vals
        if vals.get('type','out_invoice') in ('out_invoice','out_refund'):
            add_data = False
            if not vals.get('partner_bank_id'):
                add_data = True

            if add_data:
                #cerca sulla scheda del partner
                if vals.get('partner_id', None):
                    partner = Partner.browse(vals.get('partner_id'))
                    if partner.customer and partner.default_bank_account_payment:
                        bank = partner.default_bank_account_payment
                        vals['partner_bank_id'] = bank.id
                        add_data=False
            if add_data:
                # cerca tra le banche della company che hanno il flag default_bank attivo
                company = Users._get_company()
                if company:
                    company = Company.browse(company.id)
                    for bank in company.bank_ids:
                        if bank.default_bank:
                            vals['partner_bank_id'] = bank.id
                            break
        invoice = super(AccountInvoice, self).create(vals)
        return invoice


#//Aggiunge la numerazione delle fatture proforma
    @api.multi
    def action_invoice_proforma2(self):
        self.ensure_one()
        res = super(AccountInvoice, self).action_invoice_proforma2()
        number = self.env['ir.sequence'].get('cq_invoice_10.proforma')
        self.write({'n_proforma': number})
        return res


#//Gestisce la cancellazione del numero di fattura
    @api.multi
    def cancel_bill_number(self):
    # il numero interno ora si chiama move_name
        if self.move_name:   
            this_id = self.write({'move_name': False,})
        return this_id

    @api.multi
    def popup_numero_fattura(self): 
        model_obj = self.env['ir.model.data']
        if self.state not in ['draft', 'cancel']:
            raise ValidationError(_('You can erase the internal number only for draft or canceled invoices.'))
        elif self.move_name:
            view_id = 'account_invoice_inherit_anacli5'
            dummy, view_id = model_obj.get_object_reference('cq_invoice_10', view_id)
            return {
                'type': 'ir.actions.act_window',
                'name': 'Cancel invoice number?',
                'res_model': 'account.invoice',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': self.id,
                'view_id': view_id,
                'views': [(view_id, 'form')],
                'target': 'new',
            } 
        else:
            result = {}
            result['warning'] = {'title': 'Warning', 'message': "This invoice hasn't an invoice number."}
            raise ValidationError(_("This invoice hasn't an invoice number."))

    is_refunds = fields.Char("Refund", compute="_get_refund")

    @api.multi
    def _get_refund(self):
        for bill in self:
            bills=""
            if bill.type=="out_refund" or bill.type=="in_refund":
                bills=_("Refund")
            bill.is_refunds=bills

    #provv_tl_calc = fields.Boolean('Provv. Team Leader calcolata')

    @api.multi
    def show_invoices(self):
        part_id = self.partner_id.id
        # uid e' l'utente che sta lavorando
        uid = self.env.uid

        appoggio_obj = self.env['fatture.fornitori'] # tabella d'appoggio

        # cancella le righe delle fatture relative al partner
        str = 'DELETE FROM fatture_fornitori WHERE part_id = %s and user_id = %s'  % (part_id, uid) 
        self._cr.execute(str)

        # storico fatture fornitori  
        # ids delle fatture fornitore con il mio partner      
        fattlines = self.search([('partner_id', '=', part_id), ('type', '=', 'in_invoice')])

        for fattline in fattlines:
            if fattline.id != self.id:
                numb = fattline.number
                # numero fattura fornitore non e' origin!
                supp_inv_numb = fattline.reference
                date_inv = fattline.date_invoice
                # la data contabile non e' la data di pagamento!
                date_rec = fattline.date
                date_due = fattline.date_due
                residual = fattline.residual
                am_untax = fattline.amount_untaxed
                am_tot = fattline.amount_total
                
                cq_show_data = {
                    'part_id': part_id,
                   'user_id': uid,
                    'num_interno': numb,
                    'num_esterno': supp_inv_numb,
                    'data_fatt': date_inv,
                    'data_reg': date_rec,
                    'data_scad': date_due,
                    'saldo': residual,
                    'subtotale': am_untax,
                    'totale': am_tot,
                }

                rec_id = appoggio_obj.create(cq_show_data)

        context = {'part_id': part_id}
        view = self.env.ref('cq_invoice_10.account_invoice_inherit_anacli7')
        return {
            'type': 'ir.actions.act_window',
            'name': _("Previous Invoices"),
            'view_type': 'tree',
            'view_mode': 'tree',
            'res_model': 'fatture.fornitori',
            'view_id': view.id,
            'domain': [('part_id','=',part_id), ('user_id','=',uid)],
            'context': context,
            'target': 'new',
        }

#//Gestisce la coerenza fra numero e data fattura per fatture clienti 
#//Gestisce la coerenza fra data contabile e data fattura per fatture fornitori 
    @api.multi
    def action_invoice_open(self):
        for fatt in self:
            if not fatt.move_name:
                # controllo solo la prima validazione
                if fatt.date_invoice:
                    data_fatt = fatt.date_invoice
                else:
                    data_fatt1 = date.today()
                    data_fatt=datetime.strftime(data_fatt1,'%Y-%m-%d')
                if fatt.date:
                    data_reg = fatt.date
                else:
                    data_reg = data_fatt
                    fatt.date = data_fatt
                if fatt.type in ('out_invoice', 'out_refund'):
                    sql="SELECT date_invoice FROM account_invoice WHERE journal_id=%s AND date_invoice is not null AND move_name is not null And type ='"  % fatt.journal_id.id
                    sql = sql + fatt.type +"' ORDER BY move_name DESC"
                    self.env.cr.execute(sql)
                    ans=self.env.cr.fetchone()
            
                    if ans and ans[0]>data_fatt:
                        if ans[0][:4] == data_fatt[:4]:
                            raise ValidationError(
                                _("It is not possible to validate an invoice with an earlier date than that of the last validated invoice")
                            )
                else:
                    # controllo data contabile per fatture e note fornitori
                    if data_reg < data_fatt:
                        raise ValidationError(
                            _("Accounting Date (%s) can't be earlier than Invoice Date (%s).")
                            % (data_reg, data_fatt)
                        )

        return super(AccountInvoice, self).action_invoice_open()

#//Prende il sezionale di default della posizione fiscale
    @api.onchange('fiscal_position_id')
    def _onchange_fiscal_position_id(self):
        if self.type in ('out_invoice', 'out_refund') and self.fiscal_position_id and self.fiscal_position_id.inv_journal:
            self.journal_id = self.fiscal_position_id.inv_journal


#//Onchange sul partner che porta in fattura la banca inserita sul cliente
    @api.onchange('partner_id', 'company_id')
    def _onchange_partner_id(self):
        ''' Use the default bank account if specified in the customer view. '''
        res = super(AccountInvoice, self)._onchange_partner_id()
        if self.partner_id:
            bank = self.partner_id.default_bank_account_payment
            if self.type in ('out_invoice','out_refund') and bank:
                if 'value' in res:
                    res['value']['partner_bank_id'] = bank.id
                else:
                    res['value'] = {}
                    res['value']['partner_bank_id'] = bank.id
        return res



class AccountInvoiceLine(models.Model):
    _inherit='account.invoice.line'
#//Eredita account.invoice.line
#//Definisce data di inizio e fine competenza
 
    start_accounting = fields.Date('Accounting Start Date')
    end_accounting = fields.Date('Accounting End Date')
            
class AccountFiscalPosition(models.Model):
    _inherit = 'account.fiscal.position'
#//Aggiunge un sezionale sulla posizione fiscale, da usare come default per le fatture di vendita

    inv_journal = fields.Many2one('account.journal', 'Account Journal')
