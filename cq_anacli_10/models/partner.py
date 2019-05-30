# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools, SUPERUSER_ID, _
import logging
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
import code

_logger=logging.getLogger(__name__)


class SectorCompany(models.Model):
    _name = 'sector.company'
    _description = 'Different banches of a company'
#// Implementazione della gerarchia aziendale
    name = fields.Char('Company Branches')


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    sector = fields.Many2one('sector.company', 'Sector')
#// eredito ResPartner
    
    #//Nuovi tipi di contatti
    type = fields.Selection(
           [('contact', 'Contact'), 
            ('admin_contact', 'Administrative Contact'),
            ('purchase_contact', 'RFQ Contact'),
            ('sale_contact', 'Selling Contact'),
            ('invoice', 'Invoicing Contact'), 
            ('delivery', 'Shipping address'),
            ('other', 'Other Address')], string='Address Type',
        default='contact',
        help="Used to select automatically the right address according to the context in sales and purchases documents.")    
    
    #Evito di duplicare anche il codice interno -> copy=False
    ref = fields.Char(string='Internal Reference', index=True, copy=False)
    
    vat_required = fields.Boolean('VAT required', help="Don't check if VAT is not required")

    @api.onchange('company_type')
    def change_vat_required(self):
        if self.company_type == 'company':
            self.vat_required = True
        elif self.company_type == 'person':
            self.vat_required = False
    
    @api.multi
    def address_get(self, adr_pref=None):
        """ Find contacts/addresses of the right type(s) by doing a depth-first-search
        through descendants within company boundaries (EVEN through entities flagged ``is_company``)
        then continuing the search at the ancestors that are within the same company boundaries.
        Defaults to partners of type ``'default'`` when the exact type is not found, or to the
        provided partner itself if no type ``'default'`` is found either. """
        adr_pref = set(adr_pref or [])
        if 'contact' not in adr_pref:
            adr_pref.add('contact')
        result = {}
        visited = set()
        for partner in self:
            current_partner = partner
            while current_partner:
                to_scan = [current_partner]
                # Scan descendants, DFS
                while to_scan:
                    record = to_scan.pop(0)
                    visited.add(record)
                    if record.type in adr_pref and not result.get(record.type):
                        result[record.type] = record.id
                    if len(result) == len(adr_pref):
                        return result
                    to_scan = [c for c in record.child_ids
                                 if c not in visited] + to_scan
                                 #if not c.is_company] + to_scan

                # Continue scanning at ancestor if current_partner is not a commercial entity
                if current_partner.is_company or not current_partner.parent_id:
                    break
                current_partner = current_partner.parent_id

        # default to type 'contact' or the partner itself
        default = result.get('contact', self.id or False)
        for adr_type in adr_pref:
            result[adr_type] = result.get(adr_type) or default
        return result


    @api.onchange('parent_id')
    def onchange_parent_id(self):
        # return values in result, as this method is used by _fields_sync()
        if not self.parent_id:
            return
        result = {}
        partner = getattr(self, '_origin', self)
        if partner.parent_id and partner.parent_id != self.parent_id:
            result['warning'] = {
                'title': _('Warning'),
                'message': _('Changing the company of a contact should only be done if it '
                             'was never correctly set. If an existing contact starts working for a new '
                             'company then a new contact should be created under that new '
                             'company. You can use the "Discard" button to abandon this change.')}
        if partner.type == 'contact' or self.type == 'contact':
            # for contacts: copy the parent address, if set (aka, at least one
            # value is set in the address: otherwise, keep the one from the
            # contact)
            address_fields = self._address_fields()
            if not str(self.id).isdigit():
                if any(self.parent_id[key] for key in address_fields):
                    def convert(value):
                        return value.id if isinstance(value, models.BaseModel) else value
                    result['value'] = {key: convert(self.parent_id[key]) for key in address_fields}
        return result

    ###################################################################################################
    #Gerarchia tra i partner
    @api.multi
    def get_hierarchy_code(self, padre):
        for record in padre:
            if record.is_company == True:
                if record.parent_id:
                    record.parent_id.hierarchy_code = record.parent_id.ref
                    self.get_hierarchy_code(record.parent_id) 
                    if isinstance(record.parent_id.hierarchy_code, basestring) and isinstance(record.ref, basestring):
                        record.hierarchy_code = record.parent_id.hierarchy_code + "/" + record.ref
                    elif isinstance(record.parent_id.hierarchy_code, basestring) and not isinstance(record.ref, basestring):
                        record.hierarchy_code = record.parent_id.hierarchy_code
                    elif not isinstance(record.parent_id.hierarchy_code, basestring) and isinstance(record.ref, basestring):
                        record.hierarchy_code = record.ref
                    else:
                        record.hierarchy_code = ''
                else:
                    record.hierarchy_level = record.ref
                    record.hierarchy_code = record.hierarchy_level
                query1 = "UPDATE res_partner SET hierarchy_level = '%s'" %record.hierarchy_code
                query2 = query1 + " WHERE id = %s" %record.id
                self.env.cr.execute(query2) 
    
    @api.one
    def hierarchy_esterna(self):
        self.get_hierarchy_code(self)
        return True
    
    hierarchy_code = fields.Char('Hierarchy', compute = 'hierarchy_esterna')
    hierarchy_level = fields.Char('Hierarchy', readonly = True)    
    #########################################################################
    
    #Aggiornamento dei dati di una ragione sociale
    @api.multi
    def copy(self, default=None): 
        self.ensure_one()
        default = dict(default or {})
        #Nel caso di aggiornamento dei dati della ragione sociale, trasferisco tutti i figli della vecchia denominazione in quella nuova
        if self._context.get('new_company'):
            default = dict(default or {}, name = ('%s (new)') % self.name, child_ids = [(6, 0, [self.id])])
            vals = self.copy_data(default)[0]
            new_company = self.create(vals)
            return new_company
        else:
            return super(ResPartner, self).copy(default)
    
    @api.multi
    def New_Company(self):
        context = self._context.copy()
        context.update({'new_company':True})
        self=self.with_context(context)
        new = self.copy()
        childs = self.child_ids
        if childs:
            for child in childs:
                child.write({'parent_id':self.parent_id.id})
            
        #The form is returned in edit mode
        return {
            'name': 'New Company',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.partner',
            'view_id': False,
            'type': 'ir.actions.act_window',
            'res_id': new.id,
            'views': [(False, 'form')],
            'flags':  {'initial_mode': 'edit'},
            }
    
    #########################################################################
    #//Controllo che il codice interno sia unico
    @api.constrains('ref')
    def _uniq_code(self):
        for partner in self:
            if self.search([('id','!=',partner.id),('ref', '=', partner.ref)]):
                raise ValidationError(_('There is another client with the same code. It must be unique.'))
    
    #########################################################################
    #//Controllo sulla P.IVA obbligatoria per aziende e unica (tranne nella stessa gerarchia) se flag in configurazione lo prevede
                    
    @api.constrains('vat')
    def _check_vat_unique_(self):
        if not self.env['ir.values'].get_default('sale.config.settings', 'not_check_unique_vat'):
            for partner in self:
                if partner.vat:
                    padre = partner
                    while padre.parent_id:
                        padre = padre.parent_id
                    family = self.search([('id','child_of',padre.id)])
                    if self.search([('id','not in',family.ids),('vat','=',partner.vat)]):
                        raise ValidationError(_("The TIN you have inserted is already assigned to a company not affiliated."))

    @api.model
    def create(self, vals):
        #// Toglie eventuali caratteri vuoti all'inizio e fine dell'email alla creazione partner
        if 'email' in vals:
            email = vals.get('email') or ''
            email = email.strip()
            if email:
                vals['email'] = email
            else:
                vals.pop('email')

        #// Implemento sequenza automatica codice per i customer
        if vals.get('customer') == True:
            seq_cust = self.env['partner.sequence'].search([('name', '=', 'customer')])
            if not seq_cust:
                raise ValidationError(_("It doesn't exist a sequence for this category of partner. Define one."))
            else:
                c_counter = str(seq_cust.next_number)
                seq_cust.next_number = seq_cust.next_number + 1
                c_code = seq_cust.prefix + c_counter.zfill(seq_cust.len_digit)
                vals['ref'] = c_code    

        #// Implemento sequenza automatica codice per i supplier
        if vals.get('supplier') == True and vals.get('customer') == False:
            seq_supp = self.env['partner.sequence'].search([('name', '=', 'supplier')])
            if not seq_supp:
                raise ValidationError(_("It doesn't exist a sequence for this category of partner. Define one."))
            else:
                s_counter = str(seq_supp.next_number)
                seq_supp.next_number = seq_supp.next_number + 1
                s_code = seq_supp.prefix + s_counter.zfill(seq_supp.len_digit)
                vals['ref'] = s_code

        # Implemento sequenza automatica codice per gli users
        if vals.get('customer') != True and vals.get('supplier') != True:
            seq_oth = self.env['partner.sequence'].search([('name', '=', 'others')])
            if not seq_oth:
                raise ValidationError(_("It doesn't exist a sequence for this category of partner. Define one."))
            else:
                o_counter = str(seq_oth.next_number)
                seq_oth.next_number = seq_oth.next_number + 1
                o_code = seq_oth.prefix + o_counter.zfill(seq_oth.len_digit)
                vals['ref'] = o_code
        return super(ResPartner, self).create(vals)

    @api.multi
    def write(self, vals):
        #// Toglie eventuali caratteri vuoti all'inizio e fine dell'email alla modifica partner
        if 'email' in vals:
            email = vals.get('email') or ''
            email = email.strip()
            vals['email'] = email or None
        return super(ResPartner, self).write(vals)

    #########################################################################
    #// Definizione email fatture, vendita, acquisti
    @api.multi
    def get_email_fatture(self):
        for padre in self:

            email_fatture = self.search(
                [('type','=','admin_contact'),('parent_id', '=', padre.id)]
            ).mapped('email')
            email_fatture = [mail for mail in email_fatture if isinstance(mail, str) or isinstance(mail, unicode)]
            email_fatture = ','.join(email_fatture)
            padre.email_fatture = email_fatture or padre.email


    @api.multi
    def get_email_ordini(self):
        for padre in self:

            email_vendite = self.search(
                [('type','=','sale_contact'),('parent_id', '=', padre.id)]
            ).mapped('email')
            email_vendite = [mail for mail in email_vendite if isinstance(mail, str) or isinstance(mail, unicode)]
            email_vendite = ','.join(email_vendite)
            padre.email_vendite = email_vendite or padre.email

    @api.multi
    def get_email_acquisti(self):
        for padre in self:

            email_acquisti = self.search(
                [('type','=','purchase_contact'),('parent_id', '=', padre.id)]
            ).mapped('email')
            email_acquisti = [mail for mail in email_acquisti if isinstance(mail, str) or isinstance(mail, unicode)]
            email_acquisti = ','.join(email_acquisti)
            padre.email_acquisti = email_acquisti or padre.email


    email_acquisti = fields.Char(string="Purchase email", compute="get_email_acquisti", help="Email for purchase orders")
    email_vendite = fields.Char(string="Sales email", compute="get_email_ordini", help="Email for sale orders")
    email_fatture = fields.Char(string="Billing email", compute="get_email_fatture", help="Email for invoices")
    #default opt_out attivo
    opt_out = fields.Boolean(
        'Opt-Out', help="If opt-out is checked, this contact has refused to receive emails for mass mailing and marketing campaign. "
                        "Filter 'Available for Mass Mailing' allows users to filter the partners when performing mass mailing.", default=True)    
    
       
# Sequenza riferimento dei partner
class PartnerSequence(models.Model):
    _name = 'partner.sequence'
    
    next_number = fields.Integer('Next Number')
    name = fields.Selection([('customer', 'Customer'),
                             ('supplier', 'Supplier'),
                             ('others', 'Others')], 'Category of partner')
    prefix = fields.Char('Prefix')
    len_digit = fields.Integer('# of digit', default = 7)
    
class Users(models.Model):
    _inherit = 'res.users'
    
    #Disattivazione del flag 'customer' per gli users
    @api.model
    def create(self, vals):
        vals.update({'customer': False})
        user = super(Users, self).create(vals)
        user.partner_id.active = user.active
        if user.partner_id.company_id:
            user.partner_id.write({'company_id': user.company_id.id})
        return user
        
    
