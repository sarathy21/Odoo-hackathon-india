from odoo import models, fields, api

class DealHealth(models.Model):
    _name = 'dealflow.deal.health'
    _description = 'Deal Health Monitoring'
    _order = 'evaluated_at desc'
    
    order_id = fields.Many2one('sale.order', string='Sale Order', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    health_score = fields.Integer(string='Health Score', default=100)
    health_level = fields.Selection([
        ('healthy', 'Healthy'),
        ('watch', 'Watch'),
        ('at_risk', 'At Risk'),
        ('critical', 'Critical')
    ], string='Health Level', compute='_compute_health_level', store=True)
    status = fields.Selection([('active', 'Active'), ('historical', 'Historical')], default='active')
    evaluated_at = fields.Datetime(default=fields.Datetime.now)
    previous_score = fields.Integer(default=100)
    score_delta = fields.Integer(compute='_compute_score_delta', store=True)
    
    risk_component = fields.Integer(default=0)
    approval_component = fields.Integer(default=0)
    negotiation_component = fields.Integer(default=0)
    fulfillment_component = fields.Integer(default=0)
    billing_component = fields.Integer(default=0)
    anomaly_count = fields.Integer(default=0)
    
    explanation = fields.Text(string='Explanation')
    
    @api.depends('health_score')
    def _compute_health_level(self):
        for record in self:
            if record.health_score >= 80:
                record.health_level = 'healthy'
            elif record.health_score >= 60:
                record.health_level = 'watch'
            elif record.health_score >= 40:
                record.health_level = 'at_risk'
            else:
                record.health_level = 'critical'
                
    @api.depends('health_score', 'previous_score')
    def _compute_score_delta(self):
        for record in self:
            record.score_delta = record.health_score - record.previous_score

    @api.model
    def evaluate_order(self, order):
        """
        Deterministically evaluates the health of the deal and saves a record.
        """
        score = 100
        reasons = []
        
        # 1. Risk Component
        risk = order.risk_score
        risk_comp = 0
        if risk > 20:
            risk_comp = int(risk / 2) # e.g. 50 risk -> -25 health
            score -= risk_comp
            reasons.append(f"High risk score ({risk}) reduces health by {risk_comp}.")
            
        # 2. Approval Component
        appr_comp = 0
        if order.approval_status == 'pending':
            appr_comp = 15
            score -= appr_comp
            reasons.append("Pending approval reduces health by 15.")
        elif order.approval_status == 'rejected':
            appr_comp = 30
            score -= appr_comp
            reasons.append("Rejected approval reduces health by 30.")
            
        # 3. Negotiation Component
        neg_comp = 0
        active_neg = self.env['dealflow.negotiation'].search_count([
            ('order_id', '=', order.id),
            ('state', '=', 'submitted')
        ])
        if active_neg > 0:
            neg_comp = 10
            score -= neg_comp
            reasons.append("Active customer negotiation reduces health by 10.")
            
        # 4. Fulfillment Component
        full_comp = 0
        active_plan = self.env['dealflow.fulfillment.plan'].search([
            ('order_id', '=', order.id),
            ('state', 'in', ['validated', 'applied'])
        ], limit=1)
        if active_plan:
            backorder_total = sum(active_plan.allocation_ids.mapped('backorder_qty'))
            if backorder_total > 0:
                full_comp = 20
                score -= full_comp
                reasons.append(f"Fulfillment backorder of {backorder_total} reduces health by 20.")
                
        # 5. Billing Component
        bill_comp = 0
        # If invoice status is 'to invoice' but it's an old order, could be an issue, but let's keep it simple.
        
        # 6. Anomaly Component (Assume anomalies exist)
        anomaly_count = self.env['dealflow.anomaly'].search_count([
            ('order_id', '=', order.id),
            ('state', '=', 'active')
        ])
        if anomaly_count > 0:
            score -= (15 * anomaly_count)
            reasons.append(f"{anomaly_count} active anomalies reduce health by {15 * anomaly_count}.")
            
        score = max(0, min(100, score))
        
        # Find previous active health
        previous = self.sudo().search([('order_id', '=', order.id), ('status', '=', 'active')], limit=1)
        prev_score = previous.health_score if previous else 100
        
        if previous:
            previous.sudo().status = 'historical'
            
        return self.sudo().create({
            'order_id': order.id,
            'health_score': score,
            'previous_score': prev_score,
            'risk_component': risk_comp,
            'approval_component': appr_comp,
            'negotiation_component': neg_comp,
            'fulfillment_component': full_comp,
            'billing_component': bill_comp,
            'anomaly_count': anomaly_count,
            'explanation': "\\n".join(reasons) if reasons else "Deal is perfectly healthy."
        })
