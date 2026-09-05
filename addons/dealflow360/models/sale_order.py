# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            self.env['dealflow.anomaly'].detect_anomalies(order)
        return orders

    # Risk UI Explanatory Fields
    dealflow_weighted_excess = fields.Float(string='Weighted Excess (%)', compute='_compute_dealflow_risk_score', store=True)
    dealflow_risky_line_count = fields.Integer(string='Risky Line Count', compute='_compute_dealflow_risk_score', store=True)
    dealflow_largest_excess = fields.Float(string='Largest Excess (%)', compute='_compute_dealflow_risk_score', store=True)

    risk_score = fields.Float(string='Risk Score', compute='_compute_dealflow_risk_score', store=True, help="Holistic blended risk score (0-100).")
    risk_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string='Risk Level', compute='_compute_dealflow_risk_score', store=True)

    approval_required = fields.Boolean(string='Approval Required', compute='_compute_approval_required', store=False)
    approval_status = fields.Selection([
        ('none', 'No Approval Needed'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Approval Status', default='none', tracking=True)

    last_risk_evaluation = fields.Datetime(string='Last Risk Evaluation', compute='_compute_dealflow_risk_score', store=True)

    # Snapshot / Invalidation Fields
    dealflow_commercial_revision = fields.Integer(string='Commercial Revision', default=1, copy=False)
    dealflow_approved_risk_score = fields.Float(string='Approved Risk Score', copy=False)
    dealflow_approved_revision = fields.Integer(string='Approved Revision', copy=False)

    dealflow_recommendation_data = fields.Json(
        string='Recommendation Data',
        compute='_compute_recommendation_data'
    )

    @api.depends('order_line.discount_excess', 'order_line.price_unit', 'order_line.product_uom_qty', 'partner_id', 'company_id')
    def _compute_dealflow_risk_score(self):
        for order in self:
            total_undiscounted = 0.0
            total_weighted_excess = 0.0
            risky_count = 0
            largest_excess = 0.0

            for line in order.order_line:
                if line.display_type:
                    continue
                undiscounted = line.price_unit * line.product_uom_qty
                total_undiscounted += undiscounted
                if line.discount_excess > 0:
                    risky_count += 1
                    total_weighted_excess += line.discount_excess * undiscounted
                    if line.discount_excess > largest_excess:
                        largest_excess = line.discount_excess

            w = (total_weighted_excess / total_undiscounted) if total_undiscounted > 0 else 0.0
            b = w * 2.0
            p = largest_excess * 1.0

            line_count = len([l for l in order.order_line if not l.display_type])
            proportion = (risky_count / line_count) if line_count > 0 else 0.0

            m = 1.0 + (proportion * 0.25) + (min(risky_count, 10) * 0.025)

            raw_score = (b + p) * m
            final_score = min(100.0, max(0.0, raw_score))

            order.dealflow_weighted_excess = w
            order.dealflow_risky_line_count = risky_count
            order.dealflow_largest_excess = largest_excess
            order.risk_score = final_score

            if final_score <= 20.0:
                order.risk_level = 'low'
            elif final_score <= 60.0:
                order.risk_level = 'medium'
            else:
                order.risk_level = 'high'

            # Separate approval_required compute logic
            order.last_risk_evaluation = fields.Datetime.now()

    @api.depends('risk_score', 'partner_id.dealflow_tier_id', 'company_id')
    def _compute_approval_required(self):
        for order in self:
            tier_id = order.partner_id.dealflow_tier_id.id
            domain = [
                ('min_risk_score', '<=', order.risk_score),
                ('max_risk_score', '>=', order.risk_score),
                ('company_id', '=', order.company_id.id),
                '|', ('tier_ids', '=', False), ('tier_ids', 'in', [tier_id] if tier_id else [])
            ]
            rule_count = self.env['dealflow.approval.rule'].search_count(domain)
            order.approval_required = rule_count > 0

    def _evaluate_approval_trigger(self):
        for order in self:
            if order.approval_required and order.state in ['draft', 'sent']:
                # Don't auto-create a new approval after a rejection;
                # the quotation must be materially revised first.
                if order.approval_status == 'rejected':
                    continue
                active = self.env['dealflow.approval'].search_count([
                    ('order_id', '=', order.id),
                    ('status', 'in', ['pending', 'approved'])
                ])
                if active == 0:
                    order.action_request_approval()

    def write(self, vals):
        material_fields = {'partner_id', 'company_id', 'order_line'}
        if any(f in vals for f in material_fields):
            for order in self:
                vals['dealflow_commercial_revision'] = order.dealflow_commercial_revision + 1

        res = super().write(vals)

        for order in self:
            if order.approval_status in ['approved', 'pending'] and order.dealflow_commercial_revision != order.dealflow_approved_revision:
                order._invalidate_approval("Commercial modification invalidated previous approval.")
            order._evaluate_approval_trigger()

            # Phase C and D integration
            self.env['dealflow.anomaly'].detect_anomalies(order)

        return res

    def _invalidate_approval(self, reason):
        for order in self:
            active_approvals = self.env['dealflow.approval'].search([
                ('order_id', '=', order.id),
                ('status', 'in', ['pending', 'approved'])
            ])
            if active_approvals:
                active_approvals.sudo().write({'status': 'stale'})

            old_status = order.approval_status
            order.approval_status = 'none'

            self.env['dealflow.approval.log'].sudo().create({
                'order_id': order.id,
                'user_id': self.env.user.id,
                'action': 'recalculated',
                'old_status': old_status,
                'new_status': 'none',
                'reason': reason
            })

    def action_request_approval(self):
        for order in self:
            if not order.approval_required:
                continue

            # Prevent duplicates
            active = self.env['dealflow.approval'].search_count([
                ('order_id', '=', order.id),
                ('status', 'in', ['pending', 'approved'])
            ])
            if active > 0:
                continue

            # Find rules
            tier_id = order.partner_id.dealflow_tier_id.id
            # Find rules with exact sequencing
            domain = [
                ('min_risk_score', '<=', order.risk_score),
                ('max_risk_score', '>=', order.risk_score),
                ('company_id', '=', order.company_id.id),
                '|', ('tier_ids', '=', False), ('tier_ids', 'in', [tier_id] if tier_id else [])
            ]
            rules = self.env['dealflow.approval.rule'].search(domain, order='sequence, id')

            if rules:
                approval = self.env['dealflow.approval'].sudo().create({
                    'order_id': order.id,
                    'status': 'pending'
                })

                for rule in rules:
                    self.env['dealflow.approval.step'].sudo().create({
                        'approval_id': approval.id,
                        'rule_id': rule.id
                    })

                order.write({
                    'approval_status': 'pending',
                    'dealflow_approved_risk_score': order.risk_score,
                    'dealflow_approved_revision': order.dealflow_commercial_revision
                })

                self.env['dealflow.approval.log'].sudo().create({
                    'order_id': order.id,
                    'user_id': self.env.user.id,
                    'action': 'requested',
                    'old_status': 'none',
                    'new_status': 'pending',
                    'reason': "Approval requested."
                })

    @api.depends('order_line.product_id', 'pricelist_id', 'currency_id', 'company_id')
    def _compute_recommendation_data(self):
        for order in self:
            if not order.order_line:
                order.dealflow_recommendation_data = []
                continue

            existing_product_ids = [line.product_id.id for line in order.order_line if not line.display_type and line.product_id]
            if not existing_product_ids:
                order.dealflow_recommendation_data = []
                continue

            domain = [
                ('source_product_id', 'in', existing_product_ids),
                ('active', '=', True),
                ('company_id', '=', order.company_id.id)
            ]
            recs = self.env['dealflow.product.recommendation'].search(domain, order='priority desc, recommendation_type, recommended_product_id')

            seen_recommended = set(existing_product_ids)
            final_recs = []

            for rec in recs:
                if rec.recommended_product_id.id in seen_recommended:
                    continue
                seen_recommended.add(rec.recommended_product_id.id)

                product = rec.recommended_product_id
                cost = product.standard_price

                sale_price = 0.0
                if order.pricelist_id:
                    try:
                        sale_price = order.pricelist_id._get_product_price(product, 1.0, order.partner_id)
                    except AttributeError:
                        sale_price = product.lst_price
                else:
                    sale_price = product.lst_price

                revenue = sale_price
                margin = revenue - cost

                final_recs.append({
                    'id': rec.id,
                    'product_id': product.id,
                    'product_name': product.display_name,
                    'type': rec.recommendation_type,
                    'type_label': 'Upsell' if rec.recommendation_type == 'upsell' else 'Cross-sell',
                    'reason': rec.reason or '',
                    'revenue': round(revenue, 2),
                    'margin': round(margin, 2),
                    'currency_symbol': order.currency_id.symbol or ''
                })

            order.dealflow_recommendation_data = final_recs

    def action_add_dealflow_recommendation(self, product_id):
        self.ensure_one()
        from odoo.exceptions import UserError

        if self.state not in ['draft', 'sent']:
            raise UserError("You can only add recommendations to quotations.")

        product = self.env['product.product'].browse(product_id)
        if not product.exists():
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'message': "Product not found.", 'type': 'danger'}}

        existing = any(line.product_id.id == product.id for line in self.order_line if not line.display_type)
        if existing:
            return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {'message': "Product already on quotation.", 'type': 'warning'}}

        self.env['sale.order.line'].create({
            'order_id': self.id,
            'product_id': product.id,
        })

        return {'type': 'ir.actions.client', 'tag': 'reload'}
