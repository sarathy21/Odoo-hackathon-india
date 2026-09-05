# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class DealFlowApprovalRule(models.Model):
    _name = 'dealflow.approval.rule'
    _description = 'DealFlow360 Approval Rule'
    _order = 'sequence, id'

    name = fields.Char(string='Rule Name', required=True)
    min_risk_score = fields.Float(string='Min Risk Score', required=True, default=0.0)
    max_risk_score = fields.Float(string='Max Risk Score', required=True, default=100.0)
    tier_ids = fields.Many2many('dealflow.customer.tier', string='Specific Tiers', help='Leave empty to apply to all tiers.')
    group_id = fields.Many2one('res.groups', string='Required Approval Group', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)

    @api.constrains('min_risk_score', 'max_risk_score')
    def _check_risk_scores(self):
        for rule in self:
            if rule.min_risk_score < 0 or rule.max_risk_score > 100:
                raise ValidationError("Risk scores must be between 0 and 100.")
            if rule.min_risk_score > rule.max_risk_score:
                raise ValidationError("Min Risk Score cannot be greater than Max Risk Score.")
                
    @api.constrains('min_risk_score', 'max_risk_score', 'tier_ids', 'group_id', 'company_id', 'sequence')
    def _check_duplicate_rules(self):
        for rule in self:
            domain = [
                ('id', '!=', rule.id),
                ('min_risk_score', '=', rule.min_risk_score),
                ('max_risk_score', '=', rule.max_risk_score),
                ('group_id', '=', rule.group_id.id),
                ('company_id', '=', rule.company_id.id),
                ('sequence', '=', rule.sequence)
            ]
            duplicates = self.search(domain)
            for dup in duplicates:
                if set(rule.tier_ids.ids) == set(dup.tier_ids.ids):
                    raise ValidationError(f"Duplicate approval rule detected: '{dup.name}' has the exact same configuration.")
