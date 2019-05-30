# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

#// Aggiunta classe CQRicalcolaCampi in cui definire all'occorrenza dei metodi per 
#// sovrascrittura/ricalcolo dei campi (es: aggiunta di campi compute o related su record pre-esistenti).
#// Aggiunto punto menu Configurazione/Wizard Ricalcolo Campi
class CQRicalcolaCampi(models.TransientModel):

    _name = 'cq.ricalcola.campi'
    _description = 'Wizard per ricalcolo dei campi'

    action_id = fields.Many2one('ir.actions.actions', string='Trigger Action',
        help="Action that triggered this wizard instance: "
        "each action should be 1-to-1 bound to a wizard method, so knowing the action "
        "means knowing the method launched through this instance."
    )

    @api.model
    def create(self, vals):
        ''' Aggiunge al record del wizard il link all'azione che ha chiamato questa istanza.
        NB: l'azione è un record di ir.actions.actions, non ir.actions.act_window!
        '''
        params = self.env.context.get('params', None)
        action_id = isinstance(params, dict) and params.get('action', None) or None
        if not isinstance(action_id, bool):
            try:
                action_id = int(action_id)
                vals['action_id'] = action_id
            except:
                pass
        record = super(CQRicalcolaCampi, self).create(vals)
        return record
