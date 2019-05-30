# -*- coding="UTF-8" -*-

{
    'name': 'Modifiche area acquisto',
    'author': 'CQ Creativi Quadrati',
    'category': 'Sistemazioni Generali',
    'summary': 'Modifiche sugli ordini di acquisto',
    'version': '1.0',
    'depends': ['purchase', 'account', 'base'],
    'data': [
        'views/purchase_config_settings_views.xml',
        'views/purchase_views.xml',
        'views/product_views.xml',
        'views/account_invoice_views.xml',
        'wizard/stock_picking_return.xml'
            ],
    'auto-install': False,
    'installable': True
}
