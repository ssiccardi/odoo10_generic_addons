# -*- coding: utf-8 -*-
{
    'name': "Sistemazione area crm",

    'summary': "Modifiche al CRM",

    'author': "Creativi Quadrati",

    'category': 'Sistemazioni generali',
    'version': '1.0',

    'depends': ['sale','crm','sale_crm','cq_sales_10'],

    'data': [
        'views/crm_views.xml',
        'views/sale_view.xml',
        'views/res_partner_view.xml',
        'views/calendar_views.xml',
        'security/ir.model.access.csv',
        'report/crm_opportunity_report_views.xml',
        'data/crm_data.xml',
    ],
    'installable': True,
    'auto-install': False
}
