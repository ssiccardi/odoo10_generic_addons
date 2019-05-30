from odoo import api, fields, models, tools, SUPERUSER_ID
from datetime import datetime, timedelta, date
import pytz
from dateutil.relativedelta import relativedelta
from lxml import etree


class Lead(models.Model):

    _inherit = "crm.lead"
    
    vat = fields.Char(string='Partita IVA')
    lost_reason_note = fields.Text(string='Note', track_visibility='onchange')
    prospect = fields.Boolean(related='partner_id.is_prospect', string='Prospect', readonly=True, store=True)


#// Funzione calcolo numero di preventivi collegati ad opportunita':
#// ora considera gli stati preventivo, inviato, annullato.
    @api.depends('order_ids')
    def _compute_sale_amount_total(self):
        for lead in self:
            total = 0.0
            nbr = 0
            company_currency = lead.company_currency or self.env.user.company_id.currency_id
            for order in lead.order_ids:
                if order.state in ('draft', 'sent', 'cancel'):
                    nbr += 1
                # if order.state not in ('draft', 'sent', 'cancel'):
                else:
                    total += order.currency_id.compute(order.amount_untaxed, company_currency)
            lead.sale_amount_total = total
            lead.sale_number = nbr

    @api.multi
    def action_schedule_meeting(self):
        """ Open meeting's calendar view to schedule meeting on current opportunity.
            :return dict: dictionary value for created Meeting view
        """
        self.ensure_one()
        action = self.env.ref('cq_crm_10.action_calendar_event_from_document').read()[0]
        partner_ids = self.env.user.partner_id.ids
        if self.partner_id:
            partner_ids.append(self.partner_id.id)
        action['context'] = {
            'search_default_opportunity_id': self.id if self.type == 'opportunity' else False,
            'default_opportunity_id': self.id if self.type == 'opportunity' else False,
            'default_partner_id': self.partner_id.id,
            'default_partner_ids': partner_ids,
            'default_team_id': self.team_id.id,
            'default_name': self.name,
        }
        return action

    @api.multi
    def create_new_quotation(self):
        self.ensure_one()
        
        partner_id = (self.partner_id and self.partner_id.company_type=='person' and self.partner_id.parent_id) and self.partner_id.parent_id or self.partner_id
        contact_partner_id = (self.partner_id and self.partner_id.company_type=='person') and self.partner_id or False
        action = self.env.ref('sale_crm.sale_action_quotations_new').read()[0]
        action['context'] = {
            'default_team_id': self.team_id.id,
            'default_partner_id': partner_id and partner_id.id or False,
            'default_contact_partner_id': contact_partner_id and contact_partner_id.id or False,
            'search_default_partner_id': partner_id and partner_id.id or False,
            'search_default_opportunity_id': self.id, 
            'default_opportunity_id': self.id,
            'default_tag_ids': [(6, 0, self.tag_ids.ids)],
        }
        return action

    @api.multi
    def _lead_create_contact(self, name, is_company, parent_id=False):
        """ extract data from lead to create a partner
            :param name : furtur name of the partner
            :param is_company : True if the partner is a company
            :param parent_id : id of the parent partner (False if no parent)
            :returns res.partner record
        """
        email_split = tools.email_split(self.email_from)
        values = {
            'name': name,
            'user_id': self.env.context.get('default_user_id') or self.user_id.id,
            'customer':True,
            'comment': self.description,
            'team_id': self.team_id.id,
            'parent_id': parent_id,
            'phone': self.phone,
            'mobile': self.mobile,
            'email': email_split[0] if email_split else False,
            'fax': self.fax,
            'title': self.title.id,
            'function': self.function,
            'street': self.street,
            'street2': self.street2,
            'zip': self.zip,
            'city': self.city,
            'country_id': self.country_id.id,
            'state_id': self.state_id.id,
            'is_company': is_company,
            'type': 'contact',
            'vat': self.env.context.get('vat','')
        }
        return self.env['res.partner'].create(values)


    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
#//bottone Crea invisibile in tutte le viste dal menu Prossime Attivita'
        res = super(Lead, self).fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        doc = etree.XML(res['arch'])

        view_types = ['tree','form','kanban','calendar','pivot','graph']
        if 'menu_prox_attivita' in self._context:
            xpath_name = "//" + view_type
            for node in doc.xpath(xpath_name):
                node.set("create", "0")
        res['arch'] = etree.tostring(doc)
        return res


    @api.model
    def retrieve_sales_dashboard(self):
        #sovrascrivo la funzione e modifico il risulato in modo che tra gli eventi a calendario da fare di oggi siano inclusi tutti quelli che non sono ancora finiti
        #la funzione base considerava la data di inizio come termine del meeting
        """ Fetch data to setup Sales Dashboard """
        result = {
            'meeting': {
                'today': 0,
                'next_7_days': 0,
            },
            'activity': {
                'today': 0,
                'overdue': 0,
                'next_7_days': 0,
            },
            'closing': {
                'today': 0,
                'overdue': 0,
                'next_7_days': 0,
            },
            'done': {
                'this_month': 0,
                'last_month': 0,
            },
            'won': {
                'this_month': 0,
                'last_month': 0,
            },
            'nb_opportunities': 0,
        }

        opportunities = self.search([('type', '=', 'opportunity'), ('user_id', '=', self._uid)])

        for opp in opportunities:
            # Expected closing
            if opp.date_deadline:
                date_deadline = fields.Date.from_string(opp.date_deadline)
                if date_deadline == date.today():
                    result['closing']['today'] += 1
                if date.today() <= date_deadline <= date.today() + timedelta(days=7):
                    result['closing']['next_7_days'] += 1
                if date_deadline < date.today() and not opp.date_closed:
                    result['closing']['overdue'] += 1
            # Next activities
            if opp.next_activity_id and opp.date_action:
                date_action = fields.Date.from_string(opp.date_action)
                if date_action == date.today():
                    result['activity']['today'] += 1
                if date.today() <= date_action <= date.today() + timedelta(days=7):
                    result['activity']['next_7_days'] += 1
                if date_action < date.today():
                    result['activity']['overdue'] += 1
            # Won in Opportunities
            if opp.date_closed:
                date_closed = fields.Date.from_string(opp.date_closed)
                if date.today().replace(day=1) <= date_closed <= date.today():
                    if opp.planned_revenue:
                        result['won']['this_month'] += opp.planned_revenue
                elif  date.today() + relativedelta(months=-1, day=1) <= date_closed < date.today().replace(day=1):
                    if opp.planned_revenue:
                        result['won']['last_month'] += opp.planned_revenue

        result['nb_opportunities'] = len(opportunities)

        # crm.activity is a very messy model so we need to do that in order to retrieve the actions done.
        self._cr.execute("""
            SELECT
                m.id,
                m.subtype_id,
                m.date,
                l.user_id,
                l.type
            FROM mail_message M
                LEFT JOIN crm_lead L ON (M.res_id = L.id)
                INNER JOIN crm_activity A ON (M.subtype_id = A.subtype_id)
            WHERE
                (M.model = 'crm.lead') AND (L.user_id = %s) AND (L.type = 'opportunity')
        """, (self._uid,))
        activites_done = self._cr.dictfetchall()

        for activity in activites_done:
            if activity['date']:
                date_act = fields.Date.from_string(activity['date'])
                if date.today().replace(day=1) <= date_act <= date.today():
                    result['done']['this_month'] += 1
                elif date.today() + relativedelta(months=-1, day=1) <= date_act < date.today().replace(day=1):
                    result['done']['last_month'] += 1

        # Meetings
        tz = self.env.user.tz and pytz.timezone(self.env.user.tz) or pytz.utc        
        now_utc = datetime.now(tz=pytz.utc)
        now = now_utc.astimezone(tz=tz)
        max_date_today = now.replace(microsecond=0,second=0,minute=0,hour=0) + timedelta(days=1)
        max_date_today_utc = max_date_today.astimezone(tz=pytz.utc)
        max_date_utc = max_date_today_utc + timedelta(days=6)        
        meetings_domain = [
            ('start', '<=', fields.Datetime.to_string(max_date_utc)),
            ('stop', '>=', fields.Datetime.to_string(now_utc)),
            ('partner_ids', 'in', [self.env.user.partner_id.id])
        ]
        meetings = self.env['calendar.event'].search(meetings_domain)
        for meeting in meetings:
            if meeting['start'] and meeting['stop']:
                result['meeting']['next_7_days'] += 1
                start = pytz.utc.localize(datetime.strptime(meeting['start'], tools.DEFAULT_SERVER_DATETIME_FORMAT))
                if start < max_date_today_utc:
                    result['meeting']['today'] += 1

        result['done']['target'] = self.env.user.target_sales_done
        result['won']['target'] = self.env.user.target_sales_won
        result['currency_id'] = self.env.user.company_id.currency_id.id

        return result


class Lead2OpportunityPartner(models.TransientModel):

    _inherit = 'crm.lead2opportunity.partner'
    
    vat = fields.Char(string='Partita IVA')
    action = fields.Selection([
        ('exist', 'Link to an existing customer'),
        ('create', 'Create a new customer'),
    ], 'Related Customer', required=True)    
    
    @api.onchange('action')
    def onchange_action(self):
        if self.action == 'create':
            lead = self.env['crm.lead'].browse(self._context['active_id'])
            self.vat = lead and lead.vat or False
        else:
            self.vat = False
        return super(Lead2OpportunityPartner,self).onchange_action()

    def _create_partner(self, lead_id, action, partner_id):
        self = self.with_context(vat=self.vat)
        return super(Lead2OpportunityPartner,self)._create_partner(lead_id, action, partner_id)
        
    @api.model
    def default_get(self, fields):
        result = super(Lead2OpportunityPartner, self).default_get(fields)
        if result.get('action','') == 'nothing':
            result['action'] = 'create'
        result['name'] = 'convert'
        return result
        
class CrmLeadLost(models.TransientModel):
    _inherit = 'crm.lead.lost'

    lost_reason_note = fields.Text(string='Note')

    @api.multi
    def action_lost_reason_apply(self):
        leads = self.env['crm.lead'].browse(self.env.context.get('active_ids'))
        leads.write({'lost_reason': self.lost_reason_id.id,'lost_reason_note': self.lost_reason_note})
        return leads.action_set_lost()
