from odoo import models, fields, api

class DealAnomaly(models.Model):
    _name = 'dealflow.anomaly'
    _description = 'Deal Anomaly'
    _order = 'detected_at desc'
    
    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    order_id = fields.Many2one('sale.order', string='Sale Order', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='order_id.company_id', store=True)
    
    anomaly_type = fields.Selection([
        ('extreme_discount', 'Extreme Discount'),
        ('approval_delay', 'Approval Delay'),
        ('repeated_negotiation', 'Repeated Negotiation'),
        ('fulfillment_shortage', 'Fulfillment Shortage'),
        ('risk_spike', 'Risk Spike'),
    ], string='Anomaly Type', required=True)
    
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Severity', required=True)
    
    description = fields.Char(string='Description')
    detected_at = fields.Datetime(default=fields.Datetime.now)
    resolved_at = fields.Datetime()
    state = fields.Selection([('active', 'Active'), ('resolved', 'Resolved')], default='active')
    
    source = fields.Char(string='Source')
    value = fields.Float(string='Trigger Value')
    threshold = fields.Float(string='Threshold')
    explanation = fields.Text(string='Explanation')
    
    @api.depends('order_id.name', 'anomaly_type')
    def _compute_name(self):
        for record in self:
            record.name = f"{record.order_id.name or 'New'} - {dict(self._fields['anomaly_type'].selection).get(record.anomaly_type, 'Anomaly')}"

    @api.model
    def detect_anomalies(self, order):
        """
        Runs anomaly detection rules on the given order.
        """
        self._detect_extreme_discount(order)
        self._detect_repeated_negotiation(order)
        self._detect_fulfillment_shortage(order)
        self._detect_risk_spike(order)
        
        # After detecting, trigger health re-evaluation
        self.env['dealflow.deal.health'].evaluate_order(order)
        
    def _create_or_update(self, order, anomaly_type, severity, description, value, threshold, explanation, source='System'):
        existing = self.sudo().search([
            ('order_id', '=', order.id),
            ('anomaly_type', '=', anomaly_type),
            ('state', '=', 'active')
        ], limit=1)
        
        if existing:
            existing.sudo().write({
                'severity': severity,
                'description': description,
                'value': value,
                'threshold': threshold,
                'explanation': explanation,
                'detected_at': fields.Datetime.now(),
            })
        else:
            self.sudo().create({
                'order_id': order.id,
                'anomaly_type': anomaly_type,
                'severity': severity,
                'description': description,
                'value': value,
                'threshold': threshold,
                'explanation': explanation,
                'source': source
            })

    def _resolve(self, order, anomaly_type):
        active = self.sudo().search([
            ('order_id', '=', order.id),
            ('anomaly_type', '=', anomaly_type),
            ('state', '=', 'active')
        ])
        if active:
            active.sudo().write({
                'state': 'resolved',
                'resolved_at': fields.Datetime.now()
            })

    def action_resolve(self):
        """Action for users to manually resolve anomalies."""
        for record in self:
            if record.state == 'active':
                record.sudo().write({
                    'state': 'resolved',
                    'resolved_at': fields.Datetime.now()
                })

    def _detect_extreme_discount(self, order):
        # Discount > allowed + 20%
        extreme = False
        max_excess = 0
        for line in order.order_line:
            if line.discount_excess >= 20.0:
                extreme = True
                max_excess = max(max_excess, line.discount_excess)
                
        if extreme:
            self._create_or_update(
                order, 'extreme_discount', 'high',
                'Extreme discount requested', max_excess, 20.0,
                'Requested discount exceeds the configured limit by more than 20%.'
            )
        else:
            self._resolve(order, 'extreme_discount')

    def _detect_repeated_negotiation(self, order):
        count = self.env['dealflow.negotiation'].search_count([('order_id', '=', order.id)])
        if count >= 3:
            self._create_or_update(
                order, 'repeated_negotiation', 'medium',
                'High negotiation frequency', count, 2.0,
                f'This deal has gone through {count} negotiation cycles.'
            )
        else:
            self._resolve(order, 'repeated_negotiation')

    def _detect_fulfillment_shortage(self, order):
        plan = self.env['dealflow.fulfillment.plan'].search([
            ('order_id', '=', order.id),
            ('state', 'in', ['validated', 'applied'])
        ], limit=1)
        
        shortage = sum(plan.allocation_ids.mapped('backorder_qty')) if plan else 0
        if shortage > 0:
            self._create_or_update(
                order, 'fulfillment_shortage', 'high',
                'Critical fulfillment shortage', shortage, 0.0,
                f'Deal has a backorder of {shortage} units.'
            )
        else:
            self._resolve(order, 'fulfillment_shortage')

    def _detect_risk_spike(self, order):
        # We need historical risk. If previous revision had 20 points lower...
        # We can check approval logs or health history.
        health_history = self.env['dealflow.deal.health'].search([
            ('order_id', '=', order.id)
        ], order='id desc', limit=2)
        
        if len(health_history) == 2:
            prev_risk = health_history[1].risk_component * 2 # reverse calculation
            curr_risk = order.risk_score
            delta = curr_risk - prev_risk
            
            if delta > 20:
                self._create_or_update(
                    order, 'risk_spike', 'medium',
                    'Sudden risk spike', delta, 20.0,
                    f'Risk score increased by {delta} points since the previous evaluation.'
                )
            elif delta <= 20 and curr_risk < 50:
                # Resolve if risk dropped and it's generally low
                self._resolve(order, 'risk_spike')
