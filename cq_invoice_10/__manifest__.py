# -*- coding: utf-8 -*-
{
    'name': "Sistemazione area fatturazione",

    'summary': "Modifiche sulle fatture",

    'author': "Creativi Quadrati",

    'category': 'Sistemazioni generali',
    'version': '1.0',

    'depends': ['account', 'base','account_invoice_entry_date', 'cq_anacli_10'],

    'data': [
        'views/partner_view.xml',
        'data/account_data.xml',
        'views/account_view.xml',
        'views/res_bank_view.xml',
        'security/ir.model.access.csv',
    ],
    "installable":True,
    "auto-install":False
}
