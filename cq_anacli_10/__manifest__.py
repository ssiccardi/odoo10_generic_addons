# -*- coding: utf-8 -*-
{
    'name': "Anagrafiche clienti e fornitori",

    'summary': "Modifiche dei dati dei clienti",

    'author': "Creativi Quadrati",
    'category': 'Others',
    'version': '1.0',

    'depends': ['account', 'payment', 'base', 'purchase', 'sale', 'base_vat'],

    'data': [
        'views/partner_view.xml',
        'views/sale_config_settings_views.xml',
        'security/ir.model.access.csv',
    ],
    "installable":True,
    "auto-install":False
}
