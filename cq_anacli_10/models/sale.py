#-*- coding:utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.multi
    def check_limit(self):
        for order in self:
            partner = order.partner_id
            if partner.credit_limit > 0:
                if partner.credit + order.amount_total > partner.credit_limit:
                    raise UserError(u'Impossibile confermare questo ordine perchè viene superato il fido per %s.\nPer procedere modificare il Fido Accordato sulla scheda cliente.'
                                        %(partner.name))
        
    @api.multi
    def action_confirm(self):
        for order in self:
            order.check_limit()
        return super(SaleOrder,self).action_confirm()
