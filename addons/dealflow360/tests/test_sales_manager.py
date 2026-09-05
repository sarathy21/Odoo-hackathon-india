# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError

class TestSalesManagerBackend(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_main = cls.env.ref('base.main_company')
        cls.company_other = cls.env['res.company'].create({'name': 'Secondary Test Company'})
        
        cls.group_user = cls.env.ref('base.group_user')
        cls.group_sale_user = cls.env.ref('sales_team.group_sale_salesman')
        cls.group_sale_all = cls.env.ref('sales_team.group_sale_salesman_all_leads')
        cls.group_manager = cls.env.ref('dealflow360.group_dealflow_manager')
        
        cls.user_rep = cls.env['res.users'].create({
            'name': 'Test Rep User',
            'login': 'test_rep_user_df360',
            'email': 'rep_df360@example.com',
            'group_ids': [(6, 0, [cls.group_user.id, cls.group_sale_user.id])],
            'company_id': cls.company_main.id,
            'company_ids': [(6, 0, [cls.company_main.id, cls.company_other.id])],
        })
        
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Test Manager User',
            'login': 'test_manager_user_df360',
            'email': 'mgr_df360@example.com',
            'group_ids': [(6, 0, [cls.group_user.id, cls.group_sale_all.id, cls.group_manager.id])],
            'company_id': cls.company_main.id,
            'company_ids': [(6, 0, [cls.company_main.id, cls.company_other.id])],
        })

        cls.tier_gold = cls.env.ref('dealflow360.tier_gold')
        cls.tier_silver = cls.env.ref('dealflow360.tier_silver')
        
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Customer Inc',
            'is_company': True,
            'dealflow_tier_id': cls.tier_gold.id,
        })

        cls.product = cls.env.ref('dealflow360.product_enterprise_laptop')
        cls.category_hw = cls.env.ref('dealflow360.category_hardware')

        # Create an approval rule targeting group_manager
        cls.approval_rule = cls.env['dealflow.approval.rule'].create({
            'name': 'High Value Deal Approval',
            'min_risk_score': 50.0,
            'max_risk_score': 100.0,
            'group_id': cls.group_manager.id,
            'sequence': 10,
            'company_id': cls.company_main.id,
        })

    def _create_sale_order(self, user=None, company=None):
        user = user or self.user_rep
        company = company or self.company_main
        order = self.env['sale.order'].with_user(user).with_company(company).create({
            'partner_id': self.partner.id,
            'user_id': user.id,
            'company_id': company.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100000.0,
            })]
        })
        order.write({
            'dealflow_approved_revision': order.dealflow_commercial_revision,
            'dealflow_approved_risk_score': order.risk_score,
        })
        return order

    def test_01_manager_retrieves_pending_approval(self):
        """A. Manager can retrieve authorized pending approval."""
        order = self._create_sale_order()
        approval = self.env['dealflow.approval'].create({
            'order_id': order.id,
            'status': 'pending',
        })
        step = self.env['dealflow.approval.step'].create({
            'approval_id': approval.id,
            'rule_id': self.approval_rule.id,
            'status': 'pending',
        })

        mgr_dashboard = self.env['dealflow.dashboard'].with_user(self.user_manager).get_sales_manager_data()
        self.assertGreaterEqual(mgr_dashboard['kpis']['pending_approvals'], 1)
        pending_ids = [p['id'] for p in mgr_dashboard['pending_approvals']]
        self.assertIn(approval.id, pending_ids)

    def test_02_authorized_manager_approves_step(self):
        """B. Authorized manager can approve a valid pending step."""
        order = self._create_sale_order()
        approval = self.env['dealflow.approval'].create({
            'order_id': order.id,
            'status': 'pending',
        })
        step = self.env['dealflow.approval.step'].create({
            'approval_id': approval.id,
            'rule_id': self.approval_rule.id,
            'status': 'pending',
        })

        step.with_user(self.user_manager).action_approve(reason="Approved by Test Manager")
        self.assertEqual(step.status, 'approved')
        self.assertEqual(approval.status, 'approved')

    def test_03_unauthorized_rep_cannot_approve(self):
        """C. Sales Rep cannot approve manager approval."""
        order = self._create_sale_order()
        approval = self.env['dealflow.approval'].create({
            'order_id': order.id,
            'status': 'pending',
        })
        step = self.env['dealflow.approval.step'].create({
            'approval_id': approval.id,
            'rule_id': self.approval_rule.id,
            'status': 'pending',
        })

        with self.assertRaises(UserError):
            step.with_user(self.user_rep).action_approve(reason="Attempting unauthorized approval")

    def test_04_manager_cannot_approve_wrong_company(self):
        """D. Wrong-company approval cannot be actioned."""
        order_other = self._create_sale_order(company=self.company_other)
        approval_other = self.env['dealflow.approval'].create({
            'order_id': order_other.id,
            'status': 'pending',
        })
        step_other = self.env['dealflow.approval.step'].create({
            'approval_id': approval_other.id,
            'rule_id': self.approval_rule.id,
            'status': 'pending',
        })

        mgr_env = self.env['dealflow.approval.step'].with_user(self.user_manager).with_context(allowed_company_ids=[self.company_main.id])
        with self.assertRaises(UserError):
            mgr_env.browse(step_other.id).action_approve(reason="Cross company approval test")

    def test_05_sequential_approval_enforced(self):
        """E. Out-of-sequence approval cannot be actioned."""
        rule_step2 = self.env['dealflow.approval.rule'].create({
            'name': 'Executive Approval',
            'min_risk_score': 80.0,
            'max_risk_score': 100.0,
            'group_id': self.group_manager.id,
            'sequence': 20,
            'company_id': self.company_main.id,
        })
        order = self._create_sale_order()
        approval = self.env['dealflow.approval'].create({
            'order_id': order.id,
            'status': 'pending',
        })
        step1 = self.env['dealflow.approval.step'].create({
            'approval_id': approval.id,
            'rule_id': self.approval_rule.id,
            'status': 'pending',
        })
        step2 = self.env['dealflow.approval.step'].create({
            'approval_id': approval.id,
            'rule_id': rule_step2.id,
            'status': 'pending',
        })

        with self.assertRaises(UserError):
            step2.with_user(self.user_manager).action_approve(reason="Out of sequence approval")

    def test_06_non_pending_approval_cannot_be_actioned(self):
        """F. Non-pending approval cannot be actioned."""
        order = self._create_sale_order()
        approval = self.env['dealflow.approval'].create({
            'order_id': order.id,
            'status': 'approved',
        })
        step = self.env['dealflow.approval.step'].create({
            'approval_id': approval.id,
            'rule_id': self.approval_rule.id,
            'status': 'approved',
        })

        with self.assertRaises(UserError):
            step.with_user(self.user_manager).action_approve(reason="Action on approved step")

    def test_07_rejected_approval_cannot_be_approved(self):
        """G. Rejected approval cannot be approved."""
        order = self._create_sale_order()
        approval = self.env['dealflow.approval'].create({
            'order_id': order.id,
            'status': 'pending',
        })
        step = self.env['dealflow.approval.step'].create({
            'approval_id': approval.id,
            'rule_id': self.approval_rule.id,
            'status': 'pending',
        })

        step.with_user(self.user_manager).action_reject(reason="Rejected during test")
        self.assertEqual(approval.status, 'rejected')

        with self.assertRaises(UserError):
            step.with_user(self.user_manager).action_approve(reason="Attempting approval on rejected request")

    def test_08_stale_approval_cannot_be_approved(self):
        """H. Stale approval cannot be approved after commercial revision."""
        order = self._create_sale_order()
        approval = self.env['dealflow.approval'].create({
            'order_id': order.id,
            'status': 'pending',
        })
        step = self.env['dealflow.approval.step'].create({
            'approval_id': approval.id,
            'rule_id': self.approval_rule.id,
            'status': 'pending',
        })

        # Simulate commercial modification by advancing dealflow_commercial_revision
        order.write({'dealflow_commercial_revision': 5, 'dealflow_approved_revision': 1})
        self.assertFalse(step._is_user_eligible(self.user_manager))
        
        with self.assertRaises(UserError):
            step.with_user(self.user_manager).action_approve(reason="Attempting approval on stale revision")

    def test_09_high_risk_query_filters_strictly(self):
        """I. High-risk query strictly uses risk_level == 'high'."""
        order_high = self._create_sale_order()
        order_high.write({'risk_score': 85.0, 'risk_level': 'high'})
        
        order_low = self._create_sale_order()
        order_low.write({'risk_score': 10.0, 'risk_level': 'low'})

        data = self.env['dealflow.dashboard'].with_user(self.user_manager).get_sales_manager_data()
        high_risk_ids = [d['id'] for d in data['high_risk_deals']]
        self.assertIn(order_high.id, high_risk_ids)
        self.assertNotIn(order_low.id, high_risk_ids)

    def test_10_team_deal_filtering(self):
        """J. Manager deal filtering includes active deals in allowed companies."""
        order1 = self._create_sale_order(user=self.user_rep)
        order2 = self._create_sale_order(user=self.user_manager)

        data = self.env['dealflow.dashboard'].with_user(self.user_manager).get_sales_manager_data()
        self.assertGreaterEqual(data['kpis']['team_active_deals'], 2)

    def test_11_multi_company_isolation(self):
        """K. Multi-company isolation excludes deals from other companies."""
        order_other = self._create_sale_order(company=self.company_other)
        approval_other = self.env['dealflow.approval'].create({
            'order_id': order_other.id,
            'status': 'pending',
        })

        manager_main = self.env['dealflow.dashboard'].with_user(self.user_manager).with_context(allowed_company_ids=[self.company_main.id])
        data = manager_main.get_sales_manager_data()
        
        pending_orders = [p['order_id'] for p in data['pending_approvals']]
        self.assertNotIn(order_other.id, pending_orders)

    def test_12_approval_log_write_rejected(self):
        """L. Approval log write is rejected."""
        order = self._create_sale_order()
        log = self.env['dealflow.approval.log'].create({
            'order_id': order.id,
            'user_id': self.user_manager.id,
            'action': 'requested',
            'reason': 'Log created for write test',
        })

        with self.assertRaises(UserError):
            log.with_user(self.user_manager).write({'reason': 'Attempting log mutation'})

    def test_13_approval_log_unlink_rejected(self):
        """M. Approval log unlink is rejected."""
        order = self._create_sale_order()
        log = self.env['dealflow.approval.log'].create({
            'order_id': order.id,
            'user_id': self.user_manager.id,
            'action': 'requested',
            'reason': 'Log created for unlink test',
        })

        with self.assertRaises(UserError):
            log.with_user(self.user_manager).unlink()

    def test_14_workflow_can_create_log(self):
        """N. Approval workflow can create new audit log cleanly."""
        order = self._create_sale_order()
        log_count_before = self.env['dealflow.approval.log'].search_count([('order_id', '=', order.id)])
        
        self.env['dealflow.approval.log'].sudo().create({
            'order_id': order.id,
            'user_id': self.user_rep.id,
            'action': 'requested',
            'reason': 'Workflow log creation test',
        })
        log_count_after = self.env['dealflow.approval.log'].search_count([('order_id', '=', order.id)])
        self.assertEqual(log_count_after, log_count_before + 1)

    def test_15_phase1_engine(self):
        """O. Existing Phase 1 risk engine calculation."""
        order = self._create_sale_order()
        self.assertIsNotNone(order.risk_score)
        self.assertIn(order.risk_level, ['low', 'medium', 'high'])

    def test_16_phase2_engine(self):
        """P. Existing Phase 2 discount governance check."""
        discount_rule = self.env.ref('dealflow360.rule_gold_hardware')
        self.assertEqual(discount_rule.max_discount, 15.0)

    def test_17_phase3_engine(self):
        """Q. Existing Phase 3 approval engine rule lookup."""
        rules = self.env['dealflow.approval.rule'].search([('company_id', '=', self.company_main.id)])
        self.assertGreaterEqual(len(rules), 1)

    def test_18_phase4_engine(self):
        """R. Existing Phase 4 recommendation engine lookup."""
        recs = self.env['dealflow.product.recommendation'].search([('company_id', '=', self.company_main.id)])
        self.assertGreaterEqual(len(recs), 1)

    def test_19_f1_command_center(self):
        """S. F1 get_dashboard_data() API regression check."""
        data = self.env['dealflow.dashboard'].with_user(self.user_manager).get_dashboard_data()
        self.assertIn('kpis', data)
        self.assertIn('active_deals', data['kpis'])
        self.assertIn('attention_deals', data)

    def test_20_f2_sales_rep_backend(self):
        """T. F2 get_sales_rep_workspace_data() API regression check."""
        data = self.env['dealflow.dashboard'].with_user(self.user_rep).get_sales_rep_workspace_data()
        self.assertIn('kpis', data)
        self.assertIn('my_quotations', data['kpis'])
        self.assertIn('my_deals', data)
