# -*- coding: utf-8 -*-
{
    'name': "Forza numero fattura",

    'summary': "Modulo da usare solo per clienti che devono caricare vecchie fatture contemporaneamente alle nuove.",

    'author': "Creativi Quadrati",

    'category': 'Sistemazioni generali',
    'version': '1.0',

    'depends': ['cq_invoice_10'],

    # always loaded
    'data': [
        'views/account_view.xml',
    ],
    "installable":True,
    "auto-install":False
}
