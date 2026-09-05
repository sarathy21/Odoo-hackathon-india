# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    dealflow_tier_id = fields.Many2one(
        'dealflow.customer.tier', 
        string='DealFlow Tier', 
        ondelete='set null',
        help="Determines the customer's discount governance tier."
    )
