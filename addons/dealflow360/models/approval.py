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
    
    step_ids = fields.One2many('dealflow.approval.step', 'approval_id', string='Approval Steps')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('dealflow.approval') or 'New'
        return super().create(vals_list)

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

    def action_approve(self, reason=''):
        self.ensure_one()
        
        if self.status != 'pending':
            raise UserError("You can only action pending approval steps.")
            
        # Enforce sequential approval
        all_steps = self.env['dealflow.approval.step'].search([
            ('approval_id', '=', self.approval_id.id)
        ], order='sequence, id')
        
        for step in all_steps:
            if step.status == 'pending':
                if step.id != self.id:
                    raise UserError(f"You must wait for previous steps (e.g. {step.rule_id.name}) to be approved first.")
                break
                
        if not self.env.user.has_group(self.group_id.get_external_id().get(self.group_id.id) or f'{self.group_id.category_id.name}.{self.group_id.name}'):
            if self.group_id not in self.env.user.groups_id:
                raise UserError(f"You must belong to the '{self.group_id.name}' group to approve this step.")
        
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
        
        if all(step.status == 'approved' for step in all_steps):
            self.approval_id.write({'status': 'approved'})
            self.approval_id.order_id.write({'approval_status': 'approved'})
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
        
        if self.status != 'pending':
            raise UserError("You can only action pending approval steps.")
            
        all_steps = self.env['dealflow.approval.step'].search([
            ('approval_id', '=', self.approval_id.id)
        ], order='sequence, id')
        
        for step in all_steps:
            if step.status == 'pending':
                if step.id != self.id:
                    raise UserError(f"You must wait for previous steps (e.g. {step.rule_id.name}) to be approved first.")
                break
                
        if self.group_id not in self.env.user.groups_id:
            raise UserError(f"You must belong to the '{self.group_id.name}' group to reject this step.")
            
        self.write({
            'status': 'rejected',
            'approver_id': self.env.user.id,
            'reason': reason
        })
        
        self.approval_id.write({'status': 'rejected'})
        self.approval_id.order_id.write({'approval_status': 'rejected'})
        
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
