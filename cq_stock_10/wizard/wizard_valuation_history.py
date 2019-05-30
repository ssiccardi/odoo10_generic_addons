# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _


class WizardValuationHistory(models.TransientModel):
    _inherit = 'wizard.valuation.history'

    @api.multi
    #sovrascrivo la funzione per inserire nel context se c'è o meno l'esportazione per lotti
    def open_table(self):
        self.ensure_one()
        ctx = dict(self._context)
        ctx.update({'history_date': self.date, 'search_default_group_by_location': True, 'search_default_group_by_product': True})

        action = self.env['ir.model.data'].xmlid_to_object('stock_account.action_stock_history')
        if not action:
            action = {
                'view_type': 'form',
                'view_mode': 'tree,graph,pivot',
                'res_model': 'stock.history',
                'type': 'ir.actions.act_window',
            }
        else:
            action = action[0].read()[0]

        action['domain'] = "[('date', '<=', '" + self.date + "')]"
        action['name'] = _('Stock Value At Date')
        if self.env.user.has_group('stock.group_production_lot'):
            ctx.update({'export_group_by_lot': True})
        action['context'] = ctx
        return action
