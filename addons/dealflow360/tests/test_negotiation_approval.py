# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError

class TestNegotiationApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        cls.manager_user = cls.env['res.users'].create({
            'name': 'Manager User',
            'login': 'manager_neg_app',
            'group_ids': [(6, 0, [cls.env.ref('dealflow360.group_dealflow_manager').id, cls.env.ref('sales_team.group_sale_salesman_all_leads').id, cls.env.ref('base.group_user').id])]
        })
        
        cls.sales_user = cls.env['res.users'].create({
            'name': 'Sales User',
            'login': 'sales_neg_app',
            'group_ids': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman_all_leads').id, cls.env.ref('base.group_user').id])]
        })

        # Setup Data
        cls.tier_gold = cls.env['dealflow.customer.tier'].create({'name': 'Gold (Neg Test)'})
        
        cls.partner = cls.env['res.partner'].create({
            'name': 'Negotiation Test Partner',
            'dealflow_tier_id': cls.tier_gold.id
        })
        
        cls.category = cls.env['product.category'].create({'name': 'Test Category'})
        
        cls.product = cls.env['product.product'].create({
            'name': 'Test Product',
            'categ_id': cls.category.id,
            'list_price': 1000.0,
            'standard_price': 500.0,
            'type': 'consu'
        })

        # Governance Rules
        cls.company = cls.env.company
        
        cls.discount_rule = cls.env['dealflow.discount.rule'].create({
            'name': 'Gold Rule',
            'tier_id': cls.tier_gold.id,
            'category_id': cls.category.id,
            'max_discount': 10.0,
            'company_id': cls.company.id
        })

        cls.approval_rule = cls.env['dealflow.approval.rule'].create({
            'name': 'High Risk Approval',
            'min_risk_score': 20.01,
            'max_risk_score': 100.0,
            'group_id': cls.env.ref('dealflow360.group_dealflow_manager').id,
            'company_id': cls.company.id
        })

    def _create_quotation(self):
        so = self.env['sale.order'].with_user(self.sales_user).create({
            'partner_id': self.partner.id,
        })
        self.env['sale.order.line'].with_user(self.sales_user).create({
            'order_id': so.id,
            'product_id': self.product.id,
            'product_uom_qty': 10,
            'price_unit': 1000.0,
            'discount': 0.0
        })
        return so

    def test_A_normal_discount_no_approval(self):
        """Customer requests normal discount within allowed limit."""
        so = self._create_quotation()
        
        neg = self.env['dealflow.negotiation'].create({
            'order_id': so.id,
            'reason': "Normal discount request"
        })
        self.env['dealflow.negotiation.line'].create({
            'negotiation_id': neg.id,
            'order_line_id': so.order_line[0].id,
            'requested_quantity': 10,
            'requested_unit_price': 1000.0,
            'requested_discount': 10.0 # Exactly allowed
        })
        
        neg.action_submit()
        
        self.assertEqual(neg.state, 'submitted')
        self.assertFalse(neg.approval_required)
        self.assertFalse(neg.approval_id)
        
    def test_B_high_discount_approval_created(self):
        """Customer requests discount above allowed limit."""
        so = self._create_quotation()
        
        neg = self.env['dealflow.negotiation'].create({
            'order_id': so.id,
            'reason': "High discount request"
        })
        self.env['dealflow.negotiation.line'].create({
            'negotiation_id': neg.id,
            'order_line_id': so.order_line[0].id,
            'requested_quantity': 10,
            'requested_unit_price': 1000.0,
            'requested_discount': 35.0 # Above 10%
        })
        
        neg.action_submit()
        
        self.assertEqual(neg.state, 'under_review')
        self.assertTrue(neg.approval_required)
        self.assertTrue(neg.approval_id)
        self.assertEqual(neg.approval_id.status, 'pending')
        
    def test_C_manager_opens_approval(self):
        """Manager opens approval and sees linked negotiation."""
        so = self._create_quotation()
        
        neg = self.env['dealflow.negotiation'].create({
            'order_id': so.id,
            'reason': "High discount request"
        })
        self.env['dealflow.negotiation.line'].create({
            'negotiation_id': neg.id,
            'order_line_id': so.order_line[0].id,
            'requested_quantity': 10,
            'requested_unit_price': 1000.0,
            'requested_discount': 35.0
        })
        
        neg.action_submit()
        approval = neg.approval_id
        
        self.assertEqual(approval.negotiation_id.id, neg.id)
        self.assertEqual(approval.proposed_risk_level, neg.proposed_risk_level)
        self.assertGreater(approval.proposed_risk_score, 20.0)
        
    def test_D_manager_approves(self):
        """Manager approves -> negotiation accepted."""
        so = self._create_quotation()
        initial_revision = so.dealflow_commercial_revision
        
        neg = self.env['dealflow.negotiation'].create({
            'order_id': so.id,
        })
        self.env['dealflow.negotiation.line'].create({
            'negotiation_id': neg.id,
            'order_line_id': so.order_line[0].id,
            'requested_quantity': 10,
            'requested_unit_price': 1000.0,
            'requested_discount': 35.0
        })
        
        neg.action_submit()
        approval = neg.approval_id
        
        # Approve as manager
        approval.with_user(self.manager_user).action_approve_current_step()
        
        self.assertEqual(approval.status, 'approved')
        self.assertEqual(neg.state, 'accepted')
        self.assertEqual(so.order_line[0].discount, 35.0)
        self.assertEqual(so.dealflow_commercial_revision, initial_revision + 1)
        
    def test_E_manager_rejects(self):
        """Manager rejects -> negotiation rejected, SO unchanged."""
        so = self._create_quotation()
        
        neg = self.env['dealflow.negotiation'].create({
            'order_id': so.id,
        })
        self.env['dealflow.negotiation.line'].create({
            'negotiation_id': neg.id,
            'order_line_id': so.order_line[0].id,
            'requested_quantity': 10,
            'requested_unit_price': 1000.0,
            'requested_discount': 35.0
        })
        
        neg.action_submit()
        approval = neg.approval_id
        
        approval.with_user(self.manager_user).action_reject_current_step()
        
        self.assertEqual(approval.status, 'rejected')
        self.assertEqual(neg.state, 'rejected')
        self.assertEqual(so.order_line[0].discount, 0.0) # Unchanged
        
    def test_F_two_submissions_prevent_duplicates(self):
        """Two submissions must not create duplicate active approvals."""
        so = self._create_quotation()
        
        neg1 = self.env['dealflow.negotiation'].create({'order_id': so.id})
        self.env['dealflow.negotiation.line'].create({
            'negotiation_id': neg1.id,
            'order_line_id': so.order_line[0].id,
            'requested_quantity': 10,
            'requested_unit_price': 1000.0,
            'requested_discount': 35.0
        })
        
        neg1.action_submit()
        
        neg2 = self.env['dealflow.negotiation'].create({'order_id': so.id})
        self.env['dealflow.negotiation.line'].create({
            'negotiation_id': neg2.id,
            'order_line_id': so.order_line[0].id,
            'requested_quantity': 10,
            'requested_unit_price': 1000.0,
            'requested_discount': 40.0
        })
        
        with self.assertRaisesRegex(UserError, "An active negotiation request is already pending"):
            neg2.action_submit()
            
    def test_G_quotation_changes_stale(self):
        """Quotation changes after negotiation submission."""
        so = self._create_quotation()
        
        neg = self.env['dealflow.negotiation'].create({'order_id': so.id})
        self.env['dealflow.negotiation.line'].create({
            'negotiation_id': neg.id,
            'order_line_id': so.order_line[0].id,
            'requested_quantity': 10,
            'requested_unit_price': 1000.0,
            'requested_discount': 35.0
        })
        
        neg.action_submit()
        approval = neg.approval_id
        
        # Change quotation natively
        so.with_user(self.sales_user).write({'order_line': [(1, so.order_line[0].id, {'discount': 5.0})]})
        
        # Try to approve stale approval
        with self.assertRaisesRegex(UserError, "You are not authorized to action this approval step|not eligible"):
            # is_user_eligible returns False because revision changed
            approval.with_user(self.manager_user).action_approve_current_step()
            
    def test_J_normal_internal_approval(self):
        """Normal internal quotation approval continues to work exactly as before."""
        so = self._create_quotation()
        # Trigger internal approval by increasing discount natively
        so.write({'order_line': [(1, so.order_line[0].id, {'discount': 35.0})]})
        
        self.assertEqual(so.approval_status, 'pending')
        approval = self.env['dealflow.approval'].search([('order_id', '=', so.id), ('status', '=', 'pending')])
        self.assertTrue(approval)
        self.assertFalse(approval.negotiation_id) # No negotiation link
        
        approval.with_user(self.manager_user).action_approve_current_step()
        self.assertEqual(so.approval_status, 'approved')
