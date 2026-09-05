# -*- coding: utf-8 -*-
from odoo import models, fields, api

class DealFlowNegotiationRejectWizard(models.TransientModel):
    _name = 'dealflow.negotiation.reject.wizard'
    _description = 'Reject Customer Negotiation'

    negotiation_id = fields.Many2one('dealflow.negotiation', string='Negotiation Request', required=True)
    reason = fields.Text(string='Rejection Reason', required=True, help="Reason for rejecting the customer's negotiation request.")

    def action_confirm_reject(self):
        self.ensure_one()
        self.negotiation_id.action_reject(reason=self.reason)
        return {'type': 'ir.actions.act_window_close'}
