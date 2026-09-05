# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class DiscountRule(models.Model):
    _name = 'dealflow.discount.rule'
    _description = 'DealFlow360 Discount Rule'

    name = fields.Char(string='Rule Name', required=True)
    tier_id = fields.Many2one('dealflow.customer.tier', string='Customer Tier', required=True, ondelete='restrict')
    category_id = fields.Many2one('product.category', string='Product Category', required=True, ondelete='restrict')
    max_discount = fields.Float(string='Max Discount (%)', required=True, default=0.0)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    _unique_rule = models.Constraint(
        'UNIQUE(tier_id, category_id, company_id)',
        'A discount rule already exists for this Tier, Category, and Company combination.'
    )

    @api.constrains('max_discount')
    def _check_max_discount(self):
        for record in self:
            if record.max_discount < 0.0 or record.max_discount > 100.0:
                raise ValidationError("The maximum discount must be between 0 and 100%.")
