# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class Partner(models.Model):
    _inherit = 'res.partner'
    
    #//gestione flag prospect
    is_prospect = fields.Boolean('Prospect',default=False)

    #se si toglie o si inserisce il flag prospect i figli hanno lo stesso flag del padre
    @api.multi
    @api.constrains('is_prospect')
    def set_flag_prospect(self):
        for partner in self:
            self.search([('id','child_of',partner.id),('is_prospect','=',not partner.is_prospect)]).write({'is_prospect':partner.is_prospect})
    
    @api.model
    def create(self, vals):
        if vals.get('customer'):
            vals['is_prospect'] = True
        return super(Partner,self).create(vals)

    @api.multi
    def _compute_meeting_count(self):
        for partner in self:
            partner.meeting_count = 0        
            for child in self.search([('id','child_of',partner.id)]):
                partner.meeting_count += len(child.meeting_ids)
            
    @api.multi
    def schedule_meeting(self):
        partner_ids = self.ids
        partner_ids.append(self.env.user.partner_id.id)
        meeting_ids = []
        for partner in self:
            for child in self.search([('id','child_of',partner.id)]):
                for meeting in child.meeting_ids:
                    meeting_ids.append(meeting.id)        
        action = self.env.ref('cq_crm_10.action_calendar_event_from_document').read()[0]
        action['context'] = {
            'default_partner_ids': partner_ids,
        }
        action['domain'] = [('id','in',meeting_ids)]      
        return action
