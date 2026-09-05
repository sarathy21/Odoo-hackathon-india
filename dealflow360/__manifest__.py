{
    'name': 'DealFlow360',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Intelligent, Self-Governing Sales Operations Platform',
    'description': """
        DealFlow360 Dashboard Module
    """,
    'depends': ['base', 'web', 'sale_management', 'board'],
    'data': [
        'views/dashboard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dealflow360/static/src/scss/variables.scss',
            'dealflow360/static/src/scss/dashboard.scss',
            'dealflow360/static/src/js/dashboard.js',
            'dealflow360/static/src/xml/dashboard.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
