# -*- coding: utf-8 -*-
{
    'name': 'DealFlow360',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'DealFlow360 Module Baseline',
    'description': """DealFlow360 - Odoo Hackathon 2026""",
    'author': 'DealFlow360 Team',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['base', 'product'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/customer_tier_views.xml',
        'views/discount_rule_views.xml',
        'views/menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
