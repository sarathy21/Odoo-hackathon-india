# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_recurring = fields.Boolean(string="Is Recurring", default=False)
    billing_classification = fields.Selection([
        ('one_time', 'One-Time'),
        ('recurring', 'Recurring')
    ], string="Billing Classification", compute="_compute_billing_classification", store=True)

    @api.depends('is_recurring')
    def _compute_billing_classification(self):
        for line in self:
            line.billing_classification = 'recurring' if line.is_recurring else 'one_time'

    def _create_procurements(self, product_qty, procurement_uom, values):
        self.ensure_one()
        # Phase A: Intercept procurement creation to split by warehouse allocation
        applied_plan = self.env['dealflow.fulfillment.plan'].search([
            ('order_id', '=', self.order_id.id),
            ('state', '=', 'applied')
        ], limit=1)

        if applied_plan:
            allocations = applied_plan.allocation_ids.filtered(lambda a: a.line_id == self and a.allocated_qty > 0)
            if allocations:
                procurements = []
                for alloc in allocations:
                    alloc_values = dict(values)
                    alloc_values['warehouse_id'] = alloc.warehouse_id

                    # Convert allocated qty to procurement_uom if needed (assuming UoM matches for now, or using Odoo's compute)
                    # For simplicity, we just use the adjusted qty directly since product_qty is already in procurement_uom.
                    # We compute the proportion:
                    proportion = alloc.allocated_qty / self.product_uom_qty if self.product_uom_qty else 0
                    alloc_proc_qty = product_qty * proportion

                    procurements.append(self.env['stock.rule'].Procurement(
                        self.product_id, alloc_proc_qty, procurement_uom, self._get_location_final(),
                        self.product_id.display_name, self.order_id.name, self.order_id.company_id, alloc_values
                    ))

                total_allocated = sum(allocations.mapped('allocated_qty'))
                backorder_qty = max(0.0, self.product_uom_qty - total_allocated)
                if backorder_qty > 0:
                    proportion = backorder_qty / self.product_uom_qty if self.product_uom_qty else 0
                    backorder_proc_qty = product_qty * proportion
                    procurements.append(self.env['stock.rule'].Procurement(
                        self.product_id, backorder_proc_qty, procurement_uom, self._get_location_final(),
                        self.product_id.display_name, self.order_id.name, self.order_id.company_id, values
                    ))

                return procurements

        return super()._create_procurements(product_qty, procurement_uom, values)

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

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        for line in lines:
            if line.order_id:
                if line.order_id.approval_status in ['approved', 'pending'] and line.order_id.dealflow_commercial_revision != line.order_id.dealflow_approved_revision:
                    line.order_id._invalidate_approval("Commercial modification invalidated previous approval.")
                line.order_id._evaluate_approval_trigger()
                self.env['dealflow.anomaly'].detect_anomalies(line.order_id)
        return lines

    def write(self, vals):
        material_fields = {'discount', 'product_id', 'product_uom_qty', 'price_unit'}
        if any(f in vals for f in material_fields):
            for line in self:
                if line.order_id:
                    line.order_id.dealflow_commercial_revision += 1
        res = super().write(vals)
        for line in self:
            if line.order_id:
                if line.order_id.approval_status in ['approved', 'pending'] and line.order_id.dealflow_commercial_revision != line.order_id.dealflow_approved_revision:
                    line.order_id._invalidate_approval("Commercial modification invalidated previous approval.")
                line.order_id._evaluate_approval_trigger()
                self.env['dealflow.anomaly'].detect_anomalies(line.order_id)
        return res
