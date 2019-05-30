# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, tools

class OpportunityReport(models.Model):

    _inherit = "crm.opportunity.report"


    prospect = fields.Boolean('Prospect', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'crm_opportunity_report')
        self._cr.execute("""
            CREATE VIEW crm_opportunity_report AS (
                SELECT
                    c.id,
                    c.date_deadline,

                    c.date_open as opening_date,
                    c.date_closed as date_closed,
                    c.date_last_stage_update as date_last_stage_update,

                    c.user_id,
                    c.probability,
                    c.stage_id,
                    stage.name as stage_name,
                    c.type,
                    c.company_id,
                    c.priority,
                    c.team_id,
                    (SELECT COUNT(*)
                     FROM mail_message m
                     WHERE m.model = 'crm.lead' and m.res_id = c.id) as nbr_activities,
                    c.active,
                    partner.is_prospect as prospect,
                    c.campaign_id,
                    c.source_id,
                    c.medium_id,
                    c.partner_id,
                    c.city,
                    c.country_id,
                    c.planned_revenue as total_revenue,
                    c.planned_revenue*(c.probability/100) as expected_revenue,
                    c.create_date as create_date,
                    extract('epoch' from (c.date_closed-c.create_date))/(3600*24) as  delay_close,
                    abs(extract('epoch' from (c.date_deadline - c.date_closed))/(3600*24)) as  delay_expected,
                    extract('epoch' from (c.date_open-c.create_date))/(3600*24) as  delay_open,
                    c.lost_reason,
                    c.date_conversion as date_conversion
                FROM
                    "crm_lead" c
                LEFT JOIN "crm_stage" stage ON stage.id = c.stage_id
                LEFT JOIN "res_partner" partner ON partner.id = c.partner_id
                GROUP BY c.id, stage.name, partner.id
            )""")
