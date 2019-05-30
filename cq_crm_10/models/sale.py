# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    #//aggiunge campo contatto cliente sul preventivo che deriva dall'opportunità
    contact_partner_id = fields.Many2one('res.partner', string='Contatto Cliente', readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]})
    
    #//ordine di vendita: alla conferma chiede se si vuole marcare vinta l'opportunità collegata, se c'è
    @api.multi    
    def action_confirm_win_opportunity(self):
        self.ensure_one()
        if self.opportunity_id and self.opportunity_id.stage_id and self.opportunity_id.stage_id.probability < 100:
            formview_id = self.env['ir.model.data'].get_object_reference('cq_crm_10', 'view_order_form_popup_confirm')[1]       
            return {
                "type": "ir.actions.act_window",
                "name": "Marcare vinta l'opportunità collegata?",
                "view_type": "form",
                "view_mode": "form",
                "view_id": formview_id,
                "views": [(formview_id, 'form')],
                "res_model": "sale.order",
                "res_id": self.id,
                "target": "new"
            }
        return self.action_confirm()

    @api.multi
    def set_opportunity_won(self):
        for order in self:
            order.opportunity_id.action_set_won()
        return self.action_confirm()
    
    @api.multi
    def action_confirm(self):
        for order in self:
            partner = order.partner_id
            partner_ids = self.env['res.partner'].search([('id','child_of',partner.id),('is_prospect','=',True)]) or self.env['res.partner'].browse()
            while partner.parent_id:
                partner_ids |= partner.parent_id
                partner = partner.parent_id
            partner_ids.write({'is_prospect':False})
        return super(SaleOrder,self).action_confirm()
