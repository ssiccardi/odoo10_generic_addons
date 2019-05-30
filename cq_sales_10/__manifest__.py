# -*- coding: utf-8 -*-
{
    'name': "Sistemazione area vendite",

    'summary': "Modifiche sulle vendite",

    'author': "Creativi Quadrati",

    'category': 'Sistemazioni generali',
    'version': '1.0',

    'depends': ['base', 'account', 'sale', 'purchase', 'cq_products_10', 'sale_order_dates', 'sale_stock'],

    'data': [
        'views/sales_view.xml',
        'views/account_view.xml',
        'views/stock_picking_view.xml',
        'views/sale_config_settings_views.xml',
        'wizard/stock_picking_return.xml',
        'data/sale_data.xml',
        'data/mail_template_data.xml',
        'security/ir.model.access.csv',
        'security/agente_security.xml',
    ],
    'installable': True,
    'auto-install': False
}
