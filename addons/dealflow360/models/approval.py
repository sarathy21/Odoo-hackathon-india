# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError

class DealFlowApproval(models.Model):
    _name = 'dealflow.approval'
    _description = 'DealFlow360 Approval Request'
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: self.env['ir.sequence'].next_by_code('dealflow.approval') or 'New')
    order_id = fields.Many2one('sale.order', string='Sale Order', required=True, ondelete='cascade', readonly=True)
    company_id = fields.Many2one('res.company', related='order_id.company_id', store=True, readonly=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('stale', 'Stale / Cancelled')
    ], string='Status', default='draft', required=True, readonly=True, tracking=True)
    
    negotiation_id = fields.Many2one('dealflow.negotiation', string='Negotiation Request', ondelete='cascade', readonly=True)
    negotiation_line_ids = fields.One2many(related='negotiation_id.line_ids', string='Proposed Lines', readonly=True)
    proposed_risk_score = fields.Float(related='negotiation_id.proposed_risk_score', string='Proposed Risk', readonly=True)
    proposed_risk_level = fields.Selection(related='negotiation_id.proposed_risk_level', string='Proposed Risk Level', readonly=True)
    
    step_ids = fields.One2many('dealflow.approval.step', 'approval_id', string='Approval Steps')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('dealflow.approval') or 'New'
        return super().create(vals_list)

    def action_approve_current_step(self, reason=''):
        self.ensure_one()
        if self.status != 'pending':
            raise UserError(f"Cannot approve an approval request with status '{self.status}'.")
        sorted_steps = self.step_ids.sorted(key=lambda s: (s.sequence, s.id))
        pending_step = sorted_steps.filtered(lambda s: s.status == 'pending')
        if not pending_step:
            raise UserError("No pending step found to approve.")
        pending_step[0].action_approve(reason=reason)

    def action_reject_current_step(self, reason=''):
        self.ensure_one()
        if self.status != 'pending':
            raise UserError(f"Cannot reject an approval request with status '{self.status}'.")
        sorted_steps = self.step_ids.sorted(key=lambda s: (s.sequence, s.id))
        pending_step = sorted_steps.filtered(lambda s: s.status == 'pending')
        if not pending_step:
            raise UserError("No pending step found to reject.")
        pending_step[0].action_reject(reason=reason)

class DealFlowApprovalStep(models.Model):
    _name = 'dealflow.approval.step'
    _description = 'DealFlow360 Approval Step'
    _order = 'sequence, id'

    approval_id = fields.Many2one('dealflow.approval', string='Approval Request', required=True, ondelete='cascade')
    rule_id = fields.Many2one('dealflow.approval.rule', string='Triggering Rule', required=True, ondelete='restrict')
    group_id = fields.Many2one('res.groups', string='Required Group', related='rule_id.group_id', store=True, readonly=True)
    sequence = fields.Integer(string='Sequence', related='rule_id.sequence', store=True, readonly=True)
    company_id = fields.Many2one('res.company', related='approval_id.company_id', store=True, readonly=True)
    
    status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('skipped', 'Skipped')
    ], string='Status', default='pending', required=True, readonly=True)
    
    approver_id = fields.Many2one('res.users', string='Approver', readonly=True)
    reason = fields.Text(string='Reason', readonly=True)

    def _is_user_eligible(self, user=None):
        self.ensure_one()
        user = user or self.env.user
        if self.status != 'pending' or self.approval_id.status != 'pending':
            return False
        order = self.approval_id.order_id
        if self.approval_id.negotiation_id:
            if order and order.dealflow_commercial_revision != self.approval_id.negotiation_id.base_commercial_revision:
                return False
        else:
            if order and order.dealflow_commercial_revision != order.dealflow_approved_revision:
                return False
        if self.company_id and self.company_id.id not in user.company_ids.ids:
            return False
        all_steps = self.approval_id.step_ids.sorted(key=lambda s: (s.sequence, s.id))
        for s in all_steps:
            if s.status == 'pending':
                if s.id != self.id:
                    return False
                break
        if self.group_id not in user.all_group_ids:
            return False
        return True

    def action_approve(self, reason=''):
        self.ensure_one()
        if not self._is_user_eligible():
            if self.status != 'pending':
                raise UserError("You can only action pending approval steps.")
            if self.approval_id.status != 'pending':
                raise UserError(f"Approval request is '{self.approval_id.status}' and cannot be actioned.")
            if self.company_id and self.company_id.id not in self.env.companies.ids:
                raise UserError("You cannot action approval steps for another company.")
            all_steps = self.approval_id.step_ids.sorted(key=lambda s: (s.sequence, s.id))
            for step in all_steps:
                if step.status == 'pending' and step.id != self.id:
                    raise UserError(f"You must wait for previous steps (e.g. {step.rule_id.name}) to be approved first.")
            if self.group_id not in self.env.user.all_group_ids:
                raise UserError(f"You must belong to the '{self.group_id.name}' group to approve this step.")
            raise UserError("You are not authorized to action this approval step.")
        
        self.write({
            'status': 'approved',
            'approver_id': self.env.user.id,
            'reason': reason
        })
        
        self.env['dealflow.approval.log'].sudo().create({
            'order_id': self.approval_id.order_id.id,
            'user_id': self.env.user.id,
            'action': 'approved',
            'old_status': 'pending',
            'new_status': 'approved',
            'reason': f"Step {self.rule_id.name} approved."
        })
        
        all_steps = self.approval_id.step_ids
        if all(step.status == 'approved' for step in all_steps):
            self.approval_id.write({'status': 'approved'})
            
            if self.approval_id.negotiation_id:
                self.approval_id.order_id.with_context(dealflow_applying_negotiation=True).write({
                    'approval_status': 'approved',
                    'dealflow_approved_revision': self.approval_id.order_id.dealflow_commercial_revision
                })
            else:
                self.approval_id.order_id.write({'approval_status': 'approved'})
            
            # Automatically accept linked negotiation if one exists
            if self.approval_id.negotiation_id and self.approval_id.negotiation_id.state in ['submitted', 'under_review']:
                self.approval_id.negotiation_id.sudo().with_context(auto_accept=True).action_accept()
                
            self.env['dealflow.approval.log'].sudo().create({
                'order_id': self.approval_id.order_id.id,
                'user_id': self.env.user.id,
                'action': 'approved',
                'old_status': 'pending',
                'new_status': 'approved',
                'reason': "All approval steps completed successfully."
            })

    def action_reject(self, reason=''):
        self.ensure_one()
        if not self._is_user_eligible():
            if self.status != 'pending':
                raise UserError("You can only action pending approval steps.")
            if self.approval_id.status != 'pending':
                raise UserError(f"Approval request is '{self.approval_id.status}' and cannot be actioned.")
            if self.company_id and self.company_id.id not in self.env.companies.ids:
                raise UserError("You cannot action approval steps for another company.")
            all_steps = self.approval_id.step_ids.sorted(key=lambda s: (s.sequence, s.id))
            for step in all_steps:
                if step.status == 'pending' and step.id != self.id:
                    raise UserError(f"You must wait for previous steps (e.g. {step.rule_id.name}) to be approved first.")
            if self.group_id not in self.env.user.all_group_ids:
                raise UserError(f"You must belong to the '{self.group_id.name}' group to reject this step.")
            raise UserError("You are not authorized to action this approval step.")
            
        self.write({
            'status': 'rejected',
            'approver_id': self.env.user.id,
            'reason': reason
        })
        
        self.approval_id.write({'status': 'rejected'})
        self.approval_id.order_id.write({'approval_status': 'rejected'})
        
        # Automatically reject linked negotiation if one exists
        if self.approval_id.negotiation_id and self.approval_id.negotiation_id.state in ['submitted', 'under_review']:
            self.approval_id.negotiation_id.sudo().action_reject(reason=f"Approval Rejected: {reason}")
        
        self.env['dealflow.approval.log'].sudo().create({
            'order_id': self.approval_id.order_id.id,
            'user_id': self.env.user.id,
            'action': 'rejected',
            'old_status': 'pending',
            'new_status': 'rejected',
            'reason': f"Step {self.rule_id.name} rejected: {reason}"
        })


class DealFlowApprovalLog(models.Model):
    _name = 'dealflow.approval.log'
    _description = 'DealFlow360 Approval Audit Log'
    _order = 'timestamp desc, id desc'

    order_id = fields.Many2one('sale.order', string='Sale Order', required=True, ondelete='cascade', readonly=True)
    company_id = fields.Many2one('res.company', related='order_id.company_id', store=True, readonly=True)
    user_id = fields.Many2one('res.users', string='User', required=True, readonly=True, default=lambda self: self.env.user)
    action = fields.Selection([
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('recalculated', 'Recalculated / Invalidated')
    ], string='Action', required=True, readonly=True)
    
    old_status = fields.Char(string='Old Status', readonly=True)
    new_status = fields.Char(string='New Status', readonly=True)
    timestamp = fields.Datetime(string='Timestamp', default=fields.Datetime.now, required=True, readonly=True)
    reason = fields.Text(string='Reason', readonly=True)

    def write(self, vals):
        raise UserError("Approval audit logs are immutable and cannot be modified.")

    def unlink(self):
        raise UserError("Approval audit logs are immutable and cannot be deleted.")
