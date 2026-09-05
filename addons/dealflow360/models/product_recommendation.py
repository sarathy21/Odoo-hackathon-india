from odoo import models, fields, api
from odoo.exceptions import ValidationError

class DealFlowProductRecommendation(models.Model):
    _name = 'dealflow.product.recommendation'
    _description = 'DealFlow360 Product Recommendation'
    _order = 'priority desc, id asc'

    name = fields.Char(string='Reference', required=True, copy=False, default='New')
    source_product_id = fields.Many2one('product.product', string='Source Product', required=True, index=True, ondelete='cascade')
    recommended_product_id = fields.Many2one('product.product', string='Recommended Product', required=True, index=True, ondelete='cascade')
    recommendation_type = fields.Selection([
        ('upsell', 'Upsell'),
        ('cross_sell', 'Cross-sell')
    ], string='Recommendation Type', required=True, default='cross_sell')
    priority = fields.Integer(string='Priority', default=10, help="Higher priority recommendations are shown first.")
    reason = fields.Char(string='Reason', help="Short explanation shown to the salesperson.")
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    _sql_constraints = [
        ('check_different_products', 'CHECK(source_product_id != recommended_product_id)', 'A product cannot recommend itself.')
    ]

    @api.constrains('source_product_id', 'recommended_product_id', 'company_id')
    def _check_duplicate_recommendation(self):
        for rec in self:
            domain = [
                ('id', '!=', rec.id),
                ('source_product_id', '=', rec.source_product_id.id),
                ('recommended_product_id', '=', rec.recommended_product_id.id),
                ('company_id', '=', rec.company_id.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError("A recommendation rule already exists for this source and recommended product combination in this company.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                source = self.env['product.product'].browse(vals.get('source_product_id'))
                recommended = self.env['product.product'].browse(vals.get('recommended_product_id'))
                vals['name'] = f"{source.name or 'Product'} -> {recommended.name or 'Product'}"
        return super().create(vals_list)
