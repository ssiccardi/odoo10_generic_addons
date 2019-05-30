# -*- coding: utf-8 -*-
{
    'name': "Anagrafiche Prodotti",

    'summary': "Modifiche dell'anagrafica prodotti",

    'author': "Creativi Quadrati",
    'category': 'Sistemazioni Generali',
    'version': '1.0',
    'depends': ['base', 'product', 'stock', 'purchase', 'cq_technical_features'],

    'data': [
        'security/ir.model.access.csv',
        'views/product_view.xml',
        'views/product_pricelist_views.xml',
        'wizard/cq_ricalcola_campi_view.xml',
    ],
    "installable":True,
    "auto-install":False
}
