# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class StockSettings(models.TransientModel):
    _inherit = 'stock.config.settings'

    #//aggiunge un punto di configurazione per decidere se la riserva prioritaria avviene togliendo la riserva agli altri movimenti in ordine di data schedulata crescente o decrescente
    unreserve_priority_move = fields.Selection([
        (0, "Data schedulata crescente"),
        (1, 'Data schedulata decrescente')
        ], "Ordine di Priorità",
        help='Punto di configurazione in cui è possibile decidere se la riserva prioritaria avviene togliendo la riserva agli altri movimenti in ordine di data schedulata crescente o decrescente')

