# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError

class DealFlowNegotiation(models.Model):
    _name = 'dealflow.negotiation'
    _description = 'DealFlow360 Customer Negotiation Request'
    _order = 'id desc'

    name = fields.Char(
        string='Reference', 
        required=True, 
        copy=False, 
        readonly=True, 
        default=lambda self: self.env['ir.sequence'].sudo().next_by_code('dealflow.negotiation') or 'New'
    )
    order_id = fields.Many2one('sale.order', string='Quotation', required=True, ondelete='cascade', readonly=True, index=True)
    partner_id = fields.Many2one('res.partner', related='order_id.partner_id', store=True, readonly=True, index=True)
    company_id = fields.Many2one('res.company', related='order_id.company_id', store=True, readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('stale', 'Stale')
    ], string='State', default='draft', required=True, readonly=True, tracking=True)

    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, readonly=True)
    requested_date = fields.Datetime(string='Requested Date', default=fields.Datetime.now, readonly=True)
    reason = fields.Text(string='Customer Reason', help="Customer explanation for the negotiation request.")
    customer_note = fields.Text(string='Customer Note')
    sales_note = fields.Text(string='Sales Note')

    processed_by = fields.Many2one('res.users', string='Processed By', readonly=True)
    processed_date = fields.Datetime(string='Processed Date', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason', readonly=True)

    base_commercial_revision = fields.Integer(string='Base Revision', readonly=True, help="Commercial revision of quotation when request was created.")
    applied_commercial_revision = fields.Integer(string='Applied Revision', readonly=True, help="Commercial revision of quotation after request was applied.")
    active = fields.Boolean(default=True)

    line_ids = fields.One2many('dealflow.negotiation.line', 'negotiation_id', string='Negotiation Lines')
    
    proposed_risk_score = fields.Float(string='Proposed Risk Score', readonly=True)
    proposed_risk_level = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High')
    ], string='Proposed Risk Level', readonly=True)
    approval_required = fields.Boolean(string='Approval Required', readonly=True)
    approval_id = fields.Many2one('dealflow.approval', string='Approval Request', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].sudo().next_by_code('dealflow.negotiation') or 'New'
            if 'order_id' in vals and 'base_commercial_revision' not in vals:
                order = self.env['sale.order'].browse(vals['order_id'])
                if order:
                    vals['base_commercial_revision'] = order.dealflow_commercial_revision
        return super().create(vals_list)

    def _compute_proposed_risk(self):
        for neg in self:
            order = neg.order_id
            if not order:
                continue
            
            neg_line_map = {nl.order_line_id.id: nl for nl in neg.line_ids}
            
            total_undiscounted = 0.0
            total_weighted_excess = 0.0
            risky_count = 0
            largest_excess = 0.0
            line_count = 0
            
            # Use same risk math logic as sale.order
            for line in order.order_line:
                if line.display_type:
                    continue
                line_count += 1
                
                nl = neg_line_map.get(line.id)
                if nl:
                    qty = nl.requested_quantity
                    price = nl.requested_unit_price
                    discount = nl.requested_discount
                    
                    # Compute allowed discount exactly as in sale_order_line._compute_dealflow_discount_evaluation
                    tier_id = order.partner_id.dealflow_tier_id.id
                    category_id = line.product_id.categ_id.id
                    company_id = order.company_id.id
                    
                    allowed = 0.0
                    if tier_id and category_id and company_id:
                        domain = [
                            ('tier_id', '=', tier_id),
                            ('category_id', '=', category_id),
                            ('company_id', '=', company_id)
                        ]
                        rule = self.env['dealflow.discount.rule'].search(domain, limit=1)
                        if rule:
                            allowed = rule.max_discount
                            
                    excess = max(0.0, discount - allowed)
                else:
                    qty = line.product_uom_qty
                    price = line.price_unit
                    discount = line.discount
                    excess = line.discount_excess
                    
                undiscounted = price * qty
                total_undiscounted += undiscounted
                
                if excess > 0:
                    risky_count += 1
                    total_weighted_excess += excess * undiscounted
                    if excess > largest_excess:
                        largest_excess = excess
                        
            w = (total_weighted_excess / total_undiscounted) if total_undiscounted > 0 else 0.0
            b = w * 2.0
            p = largest_excess * 1.0
            proportion = (risky_count / line_count) if line_count > 0 else 0.0
            m = 1.0 + (proportion * 0.25) + (min(risky_count, 10) * 0.025)
            
            raw_score = (b + p) * m
            final_score = min(100.0, max(0.0, raw_score))
            
            neg.proposed_risk_score = final_score
            
            if final_score <= 20.0:
                neg.proposed_risk_level = 'low'
            elif final_score <= 60.0:
                neg.proposed_risk_level = 'medium'
            else:
                neg.proposed_risk_level = 'high'
                
            # Check if this risk score requires approval
            tier_id = order.partner_id.dealflow_tier_id.id
            domain = [
                ('min_risk_score', '<=', final_score),
                ('max_risk_score', '>=', final_score),
                ('company_id', '=', order.company_id.id),
                '|', ('tier_ids', '=', False), ('tier_ids', 'in', [tier_id] if tier_id else [])
            ]
            rule_count = self.env['dealflow.approval.rule'].search_count(domain)
            neg.approval_required = rule_count > 0

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Only draft negotiations can be submitted.")

            if not rec.order_id:
                raise UserError("Negotiation must be linked to a valid quotation.")

            if rec.order_id.state not in ['draft', 'sent']:
                raise UserError(f"Quotation '{rec.order_id.name}' is in state '{rec.order_id.state}' and cannot be negotiated.")

            # Stale revision check
            if rec.base_commercial_revision != rec.order_id.dealflow_commercial_revision:
                rec.sudo().write({'state': 'stale'})
                return

            if not rec.line_ids:
                raise UserError("A negotiation request must contain at least one line.")

            for line in rec.line_ids:
                line._validate_line_values()

            # Duplicate active request check
            active_count = self.search_count([
                ('id', '!=', rec.id),
                ('order_id', '=', rec.order_id.id),
                ('state', 'in', ['submitted', 'under_review'])
            ])
            if active_count > 0:
                raise UserError("An active negotiation request is already pending for this quotation.")

            rec.sudo().write({
                'state': 'submitted',
                'requested_date': fields.Datetime.now()
            })
            
            # Compute proposed risk and route for approval if necessary
            rec.sudo()._compute_proposed_risk()
            if rec.approval_required:
                tier_id = rec.order_id.partner_id.dealflow_tier_id.id
                domain = [
                    ('min_risk_score', '<=', rec.proposed_risk_score),
                    ('max_risk_score', '>=', rec.proposed_risk_score),
                    ('company_id', '=', rec.order_id.company_id.id),
                    '|', ('tier_ids', '=', False), ('tier_ids', 'in', [tier_id] if tier_id else [])
                ]
                rules = self.env['dealflow.approval.rule'].search(domain, order='sequence, id')
                
                if rules:
                    approval = self.env['dealflow.approval'].sudo().create({
                        'order_id': rec.order_id.id,
                        'negotiation_id': rec.id,
                        'status': 'pending'
                    })
                    
                    for rule in rules:
                        self.env['dealflow.approval.step'].sudo().create({
                            'approval_id': approval.id,
                            'rule_id': rule.id
                        })
                        
                    rec.sudo().write({
                        'approval_id': approval.id,
                        'state': 'under_review'
                    })
                    
                    # Log approval request
                    self.env['dealflow.approval.log'].sudo().create({
                        'order_id': rec.order_id.id,
                        'user_id': self.env.user.id,
                        'action': 'requested',
                        'old_status': 'none',
                        'new_status': 'pending',
                        'reason': "Approval requested for customer negotiation."
                    })

    def action_accept(self):
        for rec in self:
            if rec.state not in ['submitted', 'under_review']:
                raise UserError("Only submitted or under-review negotiations can be accepted.")

            if not rec.order_id:
                raise UserError("Negotiation must be linked to a valid quotation.")

            if not self.env.context.get('auto_accept') and rec.approval_required and (not rec.approval_id or rec.approval_id.status != 'approved'):
                raise UserError("This negotiation requires managerial approval and cannot be accepted manually until fully approved.")

            # Stale revision check
            if rec.base_commercial_revision != rec.order_id.dealflow_commercial_revision:
                rec.sudo().write({'state': 'stale'})
                raise UserError("Cannot accept negotiation: the quotation has undergone a commercial revision since this request was created.")

            ctx = {}
            # Only bypass invalidation if we are applying a negotiation that was just formally approved
            if rec.approval_id and rec.approval_id.status == 'approved':
                ctx['dealflow_applying_negotiation'] = True

            # Apply requested line changes natively
            for line in rec.line_ids:
                line._validate_line_values()
                line.order_line_id.with_context(**ctx).write({
                    'product_uom_qty': line.requested_quantity,
                    'price_unit': line.requested_unit_price,
                    'discount': line.requested_discount
                })
                
            # Update the order's approved revision to match the new commercial revision
            # so that future manual modifications are properly tracked
            if rec.approval_id and rec.approval_id.status == 'approved':
                updated_order = rec.order_id.sudo()
                updated_order.invalidate_recordset(['dealflow_commercial_revision'])
                new_revision = updated_order.dealflow_commercial_revision
                updated_order.with_context(**ctx).write({'dealflow_approved_revision': new_revision})

            rec.sudo().write({
                'state': 'accepted',
                'processed_by': self.env.user.id,
                'processed_date': fields.Datetime.now(),
                'applied_commercial_revision': rec.order_id.dealflow_commercial_revision
            })

    def action_reject(self, reason=''):
        for rec in self:
            if rec.state not in ['submitted', 'under_review']:
                raise UserError("Only submitted or under-review negotiations can be rejected.")

            rec.sudo().write({
                'state': 'rejected',
                'rejection_reason': reason or 'Rejected by sales team',
                'processed_by': self.env.user.id,
                'processed_date': fields.Datetime.now()
            })


class DealFlowNegotiationLine(models.Model):
    _name = 'dealflow.negotiation.line'
    _description = 'DealFlow360 Customer Negotiation Line'

    negotiation_id = fields.Many2one('dealflow.negotiation', string='Negotiation Request', required=True, ondelete='cascade')
    order_line_id = fields.Many2one('sale.order.line', string='Quotation Line', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', related='order_line_id.product_id', store=True, readonly=True)
    
    current_quantity = fields.Float(string='Current Quantity', related='order_line_id.product_uom_qty', readonly=True)
    requested_quantity = fields.Float(string='Requested Quantity', required=True)

    current_unit_price = fields.Float(string='Current Unit Price', related='order_line_id.price_unit', readonly=True)
    requested_unit_price = fields.Float(string='Requested Unit Price', required=True)

    current_discount = fields.Float(string='Current Discount (%)', related='order_line_id.discount', readonly=True)
    requested_discount = fields.Float(string='Requested Discount (%)', required=True)

    change_type = fields.Selection([
        ('quantity', 'Quantity'),
        ('price', 'Price'),
        ('discount', 'Discount'),
        ('multiple', 'Multiple')
    ], string='Change Type', compute='_compute_change_type', store=True)

    customer_reason = fields.Char(string='Customer Reason')

    @api.depends('requested_quantity', 'requested_unit_price', 'requested_discount', 'current_quantity', 'current_unit_price', 'current_discount')
    def _compute_change_type(self):
        for line in self:
            qty_changed = line.requested_quantity != line.current_quantity
            price_changed = line.requested_unit_price != line.current_unit_price
            disc_changed = line.requested_discount != line.current_discount

            changes = [qty_changed, price_changed, disc_changed]
            changed_count = sum(1 for c in changes if c)

            if changed_count > 1:
                line.change_type = 'multiple'
            elif qty_changed:
                line.change_type = 'quantity'
            elif price_changed:
                line.change_type = 'price'
            elif disc_changed:
                line.change_type = 'discount'
            else:
                line.change_type = 'multiple'

    def _validate_line_values(self):
        for line in self:
            if line.requested_quantity < 0.0:
                raise ValidationError("Requested quantity cannot be negative.")
            if line.requested_unit_price < 0.0:
                raise ValidationError("Requested unit price cannot be negative.")
            if line.requested_discount < 0.0 or line.requested_discount > 100.0:
                raise ValidationError("Requested discount must be between 0 and 100%.")
            if line.order_line_id.order_id != line.negotiation_id.order_id:
                raise ValidationError("Order line does not belong to the negotiated quotation.")

    @api.constrains('requested_quantity', 'requested_unit_price', 'requested_discount', 'order_line_id', 'negotiation_id')
    def _check_validations(self):
        self._validate_line_values()
