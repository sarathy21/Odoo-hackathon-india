# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    discount_allowed = fields.Float(
        string='Discount Allowed', 
        compute='_compute_dealflow_discount_evaluation', 
        store=True,
        help="Maximum discount permitted by the applicable DealFlow360 discount rule."
    )
    
    discount_excess = fields.Float(
        string='Discount Excess', 
        compute='_compute_dealflow_discount_evaluation', 
        store=True,
        help="Amount by which the requested discount exceeds the allowed discount."
    )
    
    discount_risk = fields.Float(
        string='Discount Risk', 
        compute='_compute_dealflow_discount_evaluation', 
        store=True,
        help="TEMPORARY LINE-LEVEL DISCOUNT RISK INDICATOR. In Phase 2, this is equal to discount_excess. It is NOT the final DealFlow360 quotation risk score."
    )
    
    risk_flag = fields.Boolean(
        string='Risk Flag', 
        compute='_compute_dealflow_discount_evaluation', 
        store=True,
        help="True when the requested discount exceeds the allowed discount, or when a non-zero discount has no applicable rule."
    )

    @api.depends(
        'discount', 
        'product_id', 
        'product_id.categ_id', 
        'order_id.partner_id', 
        'order_id.partner_id.dealflow_tier_id', 
        'order_id.company_id'
    )
    def _compute_dealflow_discount_evaluation(self):
        # Build a distinct set of lookup keys to minimize queries
        # Key: (tier_id, category_id, company_id)
        lookup_keys = set()
        for line in self:
            if not line.order_id or not line.product_id:
                continue
                
            tier_id = line.order_id.partner_id.dealflow_tier_id.id
            category_id = line.product_id.categ_id.id
            company_id = line.order_id.company_id.id
            
            # Rules are exact match, no category parent inheritance in Phase 2
            # Rules are company specific.
            if tier_id and category_id and company_id:
                lookup_keys.add((tier_id, category_id, company_id))
        
        # Batch query rules
        rule_map = {}
        if lookup_keys:
            domain = ['|'] * (len(lookup_keys) - 1)
            for tier_id, category_id, company_id in lookup_keys:
                domain.extend([
                    '&', '&',
                    ('tier_id', '=', tier_id),
                    ('category_id', '=', category_id),
                    ('company_id', '=', company_id)
                ])
                
            # Must be active (handled natively by Odoo for active=True unless specified)
            # but we can explicitly add it just in case if domain gets complex, though standard Odoo handles it.
            rules = self.env['dealflow.discount.rule'].search(domain)
            for rule in rules:
                rule_map[(rule.tier_id.id, rule.category_id.id, rule.company_id.id)] = rule.max_discount
        
        # Evaluate each line
        for line in self:
            req_discount = line.discount or 0.0
            
            tier_id = line.order_id.partner_id.dealflow_tier_id.id if line.order_id and line.order_id.partner_id else False
            category_id = line.product_id.categ_id.id if line.product_id else False
            company_id = line.order_id.company_id.id if line.order_id else False
            
            allowed = 0.0
            if tier_id and category_id and company_id:
                key = (tier_id, category_id, company_id)
                allowed = rule_map.get(key, 0.0)
                
            excess = max(0.0, req_discount - allowed)
            
            if allowed > 0.0:
                flag = excess > 0.0
            else:
                flag = req_discount > 0.0
                
            line.discount_allowed = allowed
            line.discount_excess = excess
            line.risk_flag = flag
            line.discount_risk = excess

    def write(self, vals):
        material_fields = {'discount', 'product_id', 'product_uom_qty', 'price_unit'}
        if any(f in vals for f in material_fields):
            for line in self:
                if line.order_id:
                    line.order_id.dealflow_commercial_revision += 1
        return super().write(vals)
