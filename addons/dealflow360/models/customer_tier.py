# -*- coding: utf-8 -*-
from odoo import models, fields

class CustomerTier(models.Model):
    _name = 'dealflow.customer.tier'
    _description = 'DealFlow360 Customer Tier'

    name = fields.Char(string='Tier Name', required=True, translate=True)
    active = fields.Boolean(default=True)
