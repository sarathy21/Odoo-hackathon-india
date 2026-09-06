# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError

class TestManualOverlimitApproval(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_main = cls.env.ref('base.main_company')
        cls.company_secondary = cls.env['res.company'].create({'name': 'Secondary Company'})

        # Groups
        cls.group_saleperson = cls.env.ref('sales_team.group_sale_salesman')
        cls.group_manager = cls.env.ref('sales_team.group_sale_manager')
        cls.group_df_manager = cls.env.ref('dealflow360.group_dealflow_manager')

        # Users
        cls.user_salesrep = cls.env['res.users'].create({
            'name': 'Test Rep User',
            'login': 'rep_overlimit_df360',
            'email': 'rep_overlimit@example.com',
            'group_ids': [(6, 0, [cls.group_saleperson.id])],
            'company_ids': [(6, 0, [cls.company_main.id])],
            'company_id': cls.company_main.id
        })

        cls.user_salesmgr = cls.env['res.users'].create({
            'name': 'Test Manager User',
            'login': 'mgr_overlimit_df360',
            'email': 'mgr_overlimit@example.com',
            'group_ids': [(6, 0, [cls.group_manager.id, cls.group_df_manager.id])],
            'company_ids': [(6, 0, [cls.company_main.id])],
            'company_id': cls.company_main.id
        })

        cls.user_other_company = cls.env['res.users'].create({
            'name': 'Other Company Manager',
            'login': 'other_mgr_df360',
            'email': 'other_mgr@example.com',
            'group_ids': [(6, 0, [cls.group_manager.id, cls.group_df_manager.id])],
            'company_ids': [(6, 0, [cls.company_secondary.id])],
            'company_id': cls.company_secondary.id
        })

        cls.user_portal = cls.env['res.users'].create({
            'name': 'Customer Portal User',
            'login': 'portal_overlimit_df360',
            'email': 'portal_overlimit@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
            'company_ids': [(6, 0, [cls.company_main.id])],
            'company_id': cls.company_main.id
        })

        # Customer Tier & Partner
        cls.tier_gold = cls.env['dealflow.customer.tier'].create({
            'name': 'Gold Tier Overlimit'
        })

        cls.partner_abc = cls.env['res.partner'].create({
            'name': 'ABC Technologies',
            'dealflow_tier_id': cls.tier_gold.id,
            'company_id': cls.company_main.id
        })

        # Product & Category
        cls.categ_hardware = cls.env['product.category'].create({'name': 'Hardware'})
        cls.product_laptop = cls.env['product.product'].create({
            'name': 'Enterprise Laptop',
            'categ_id': cls.categ_hardware.id,
            'lst_price': 100000.0,
            'standard_price': 60000.0
        })

        # Discount Rule: Gold Tier + Hardware = 15% allowed
        cls.discount_rule = cls.env['dealflow.discount.rule'].create({
            'name': 'Gold Hardware Rule',
            'tier_id': cls.tier_gold.id,
            'category_id': cls.categ_hardware.id,
            'company_id': cls.company_main.id,
            'max_discount': 15.0
        })

        # Approval Rule: Risk 20-100 Requires DealFlow Manager approval
        cls.approval_rule_mgr = cls.env['dealflow.approval.rule'].create({
            'name': 'Manager Overlimit Approval Rule',
            'min_risk_score': 20.0,
            'max_risk_score': 100.0,
            'company_id': cls.company_main.id,
            'group_id': cls.group_df_manager.id,
            'sequence': 10
        })

    def _create_quotation(self, discount=0.0):
        order = self.env['sale.order'].with_user(self.user_salesrep).create({
            'partner_id': self.partner_abc.id,
            'company_id': self.company_main.id,
            'order_line': [(0, 0, {
                'product_id': self.product_laptop.id,
                'product_uom_qty': 1.0,
                'price_unit': 100000.0,
                'discount': discount
            })]
        })
        return order

    def test_A_overlimit_discount_creates_pending_approval(self):
        # 50% discount requested vs 15% allowed -> 35% excess
        order = self._create_quotation(discount=50.0)
        self.assertTrue(order.approval_required)
        self.assertEqual(order.approval_status, 'pending')

        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)])
        self.assertEqual(len(approval), 1)
        self.assertEqual(approval.status, 'pending')
        self.assertEqual(len(approval.step_ids), 1)
        self.assertEqual(approval.step_ids.status, 'pending')

    def test_B_within_limit_discount_does_not_create_approval(self):
        # 10% requested vs 15% allowed -> 0% excess
        order = self._create_quotation(discount=10.0)
        self.assertFalse(order.approval_required)
        self.assertEqual(order.approval_status, 'none')

        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)])
        self.assertEqual(len(approval), 0)

    def test_C_correct_approval_group_assigned(self):
        order = self._create_quotation(discount=50.0)
        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)
        step = approval.step_ids[0]
        self.assertEqual(step.group_id, self.group_df_manager)

    def test_D_sales_rep_cannot_approve(self):
        order = self._create_quotation(discount=50.0)
        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)
        step = approval.step_ids[0]

        with self.assertRaises(UserError):
            step.with_user(self.user_salesrep).action_approve(reason="Rep self-approval attempt")

    def test_E_authorized_sales_manager_can_approve(self):
        order = self._create_quotation(discount=50.0)
        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)
        step = approval.step_ids[0]

        step.with_user(self.user_salesmgr).action_approve(reason="Manager approval granted")
        self.assertEqual(step.status, 'approved')
        self.assertEqual(approval.status, 'approved')
        self.assertEqual(order.approval_status, 'approved')

    def test_F_unauthorized_user_cannot_approve(self):
        order = self._create_quotation(discount=50.0)
        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)
        step = approval.step_ids[0]

        with self.assertRaises(UserError):
            step.with_user(self.user_salesrep).action_approve(reason="Unauthorized attempt")

    def test_G_wrong_company_cannot_approve(self):
        order = self._create_quotation(discount=50.0)
        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)
        step = approval.step_ids[0]

        with self.assertRaises(UserError):
            step.with_user(self.user_other_company).action_approve(reason="Cross company attempt")

    def test_H_customer_portal_user_cannot_approve(self):
        order = self._create_quotation(discount=50.0)
        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)
        step = approval.step_ids[0]

        with self.assertRaises(UserError):
            step.with_user(self.user_portal).action_approve(reason="Portal customer attempt")

    def test_I_rejected_approval_cannot_be_approved_afterward(self):
        order = self._create_quotation(discount=50.0)
        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)
        step = approval.step_ids[0]

        step.with_user(self.user_salesmgr).action_reject(reason="Too high discount")
        self.assertEqual(step.status, 'rejected')
        self.assertEqual(approval.status, 'rejected')

        with self.assertRaises(UserError):
            step.with_user(self.user_salesmgr).action_approve(reason="Attempt approve after reject")

    def test_J_already_approved_cannot_be_approved_again(self):
        order = self._create_quotation(discount=50.0)
        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)
        step = approval.step_ids[0]

        step.with_user(self.user_salesmgr).action_approve(reason="First approval")
        with self.assertRaises(UserError):
            step.with_user(self.user_salesmgr).action_approve(reason="Second approval")

    def test_K_stale_approval_cannot_be_approved(self):
        order = self._create_quotation(discount=50.0)
        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)
        step = approval.step_ids[0]

        # Modify quotation line to increment revision
        order.order_line[0].write({'discount': 60.0})
        self.assertEqual(approval.status, 'stale')

        with self.assertRaises(UserError):
            step.with_user(self.user_salesmgr).action_approve(reason="Stale step approval attempt")

    def test_L_previous_approval_sequence_enforced(self):
        # Create a 2-step approval chain
        rule_step2 = self.env['dealflow.approval.rule'].create({
            'name': 'Executive Approval Rule',
            'min_risk_score': 0.0,
            'max_risk_score': 100.0,
            'company_id': self.company_main.id,
            'group_id': self.group_manager.id,
            'sequence': 20
        })

        order = self._create_quotation(discount=50.0)
        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)
        steps = approval.step_ids.sorted(key=lambda s: s.sequence)
        self.assertEqual(len(steps), 2)

        # Step 2 cannot be approved before Step 1
        step2 = steps[1]
        with self.assertRaises(UserError):
            step2.with_user(self.user_salesmgr).action_approve(reason="Step 2 out of order")

    def test_M_repeated_risk_evaluation_does_not_create_duplicate_approvals(self):
        order = self._create_quotation(discount=50.0)
        order._compute_dealflow_risk_score()
        order._evaluate_approval_trigger()
        order._evaluate_approval_trigger()

        approvals = self.env['dealflow.approval'].search([('order_id', '=', order.id), ('status', '=', 'pending')])
        self.assertEqual(len(approvals), 1)

    def test_N_O_changing_quotation_after_approval_invalidates_old_and_creates_new(self):
        order = self._create_quotation(discount=50.0)
        approval1 = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)
        approval1.step_ids[0].with_user(self.user_salesmgr).action_approve(reason="Approved rev 1")

        self.assertEqual(order.approval_status, 'approved')

        # Change discount 50% -> 60%
        order.order_line[0].write({'discount': 60.0})

        self.assertEqual(approval1.status, 'stale')
        # Check new active pending approval created for rev 2
        approval2 = self.env['dealflow.approval'].search([('order_id', '=', order.id), ('status', '=', 'pending')], limit=1)
        self.assertTrue(approval2)
        self.assertNotEqual(approval1.id, approval2.id)
        self.assertEqual(order.approval_status, 'pending')

    def test_P_Q_R_S_customer_negotiation_full_flow(self):
        # Create quotation within limit
        order = self._create_quotation(discount=10.0)
        self.assertEqual(order.approval_status, 'none')

        # Customer submits negotiation requesting 50% discount
        negotiation = self.env['dealflow.negotiation'].create({
            'order_id': order.id,
            'reason': 'Customer volume request',
            'line_ids': [(0, 0, {
                'order_line_id': order.order_line[0].id,
                'requested_quantity': 1.0,
                'requested_unit_price': 100000.0,
                'requested_discount': 50.0
            })]
        })
        negotiation.action_submit()
        self.assertEqual(negotiation.state, 'under_review')
        self.assertEqual(order.approval_status, 'none')

        # Internal manager approves the step
        approval = negotiation.approval_id
        approval.with_user(self.user_salesmgr).action_approve_current_step()
        
        self.assertEqual(negotiation.state, 'accepted')
        self.assertEqual(order.order_line[0].discount, 50.0)
        self.assertEqual(order.approval_status, 'approved')

    def test_T_customer_negotiation_rejection_flow(self):
        order = self._create_quotation(discount=10.0)
        negotiation = self.env['dealflow.negotiation'].create({
            'order_id': order.id,
            'reason': 'Customer request',
            'line_ids': [(0, 0, {
                'order_line_id': order.order_line[0].id,
                'requested_quantity': 1.0,
                'requested_unit_price': 100000.0,
                'requested_discount': 50.0
            })]
        })
        negotiation.action_submit()
        self.assertEqual(negotiation.state, 'under_review')

        approval = negotiation.approval_id
        approval.with_user(self.user_salesmgr).action_reject_current_step(reason="Overlimit discount rejected by manager")

        self.assertEqual(approval.status, 'rejected')
        self.assertEqual(order.approval_status, 'rejected')
        self.assertEqual(negotiation.state, 'rejected')
        # Quotation remains unchanged because negotiation was rejected
        self.assertEqual(order.order_line[0].discount, 10.0)

    def test_U_stale_negotiation_cannot_modify_quotation(self):
        order = self._create_quotation(discount=10.0)
        negotiation = self.env['dealflow.negotiation'].create({
            'order_id': order.id,
            'reason': 'Customer request',
            'line_ids': [(0, 0, {
                'order_line_id': order.order_line[0].id,
                'requested_quantity': 1.0,
                'requested_unit_price': 100000.0,
                'requested_discount': 50.0
            })]
        })

        # Sales rep modifies quotation line directly
        order.order_line[0].write({'price_unit': 95000.0})

        # Submitting negotiation after quotation revision change marks it stale
        negotiation.action_submit()
        self.assertEqual(negotiation.state, 'stale')

    def test_V_stale_approval_cannot_authorize_newer_revision(self):
        order = self._create_quotation(discount=50.0)
        approval = self.env['dealflow.approval'].search([('order_id', '=', order.id)], limit=1)

        # Order revision changes
        order.order_line[0].write({'discount': 55.0})
        self.assertEqual(approval.status, 'stale')

        with self.assertRaises(UserError):
            approval.step_ids[0].with_user(self.user_salesmgr).action_approve(reason="Attempting stale revision approval")
