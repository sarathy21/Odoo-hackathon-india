# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError, AccessError

class TestCustomerNegotiationPortal(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_main = cls.env.ref('base.main_company')
        cls.company_other = cls.env['res.company'].create({'name': 'Secondary Portal Test Company'})

        cls.group_user = cls.env.ref('base.group_user')
        cls.group_portal = cls.env.ref('base.group_portal')
        cls.group_sale_user = cls.env.ref('sales_team.group_sale_salesman')
        cls.group_sale_all = cls.env.ref('sales_team.group_sale_salesman_all_leads')
        cls.group_manager = cls.env.ref('dealflow360.group_dealflow_manager')

        cls.tier_gold = cls.env.ref('dealflow360.tier_gold')
        cls.tier_silver = cls.env.ref('dealflow360.tier_silver')

        # Partners
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Customer Portal Partner A',
            'is_company': True,
            'dealflow_tier_id': cls.tier_gold.id,
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'Customer Portal Partner B',
            'is_company': True,
            'dealflow_tier_id': cls.tier_silver.id,
        })

        # Users
        cls.user_portal_a = cls.env['res.users'].create({
            'name': 'Portal User A',
            'login': 'portal_user_a_df360',
            'email': 'portal_a@example.com',
            'partner_id': cls.partner_a.id,
            'group_ids': [(6, 0, [cls.group_portal.id])],
            'company_id': cls.company_main.id,
            'company_ids': [(6, 0, [cls.company_main.id])],
        })

        cls.user_portal_b = cls.env['res.users'].create({
            'name': 'Portal User B',
            'login': 'portal_user_b_df360',
            'email': 'portal_b@example.com',
            'partner_id': cls.partner_b.id,
            'group_ids': [(6, 0, [cls.group_portal.id])],
            'company_id': cls.company_main.id,
            'company_ids': [(6, 0, [cls.company_main.id])],
        })

        cls.user_rep = cls.env['res.users'].create({
            'name': 'Sales Rep User',
            'login': 'rep_portal_test_df360',
            'email': 'rep_portal@example.com',
            'group_ids': [(6, 0, [cls.group_user.id, cls.group_sale_user.id])],
            'company_id': cls.company_main.id,
            'company_ids': [(6, 0, [cls.company_main.id, cls.company_other.id])],
        })

        cls.user_manager = cls.env['res.users'].create({
            'name': 'Sales Manager User',
            'login': 'mgr_portal_test_df360',
            'email': 'mgr_portal@example.com',
            'group_ids': [(6, 0, [cls.group_user.id, cls.group_sale_all.id, cls.group_manager.id])],
            'company_id': cls.company_main.id,
            'company_ids': [(6, 0, [cls.company_main.id, cls.company_other.id])],
        })

        cls.product = cls.env.ref('dealflow360.product_enterprise_laptop')

        # Create approval rule for test_25
        cls.approval_rule = cls.env['dealflow.approval.rule'].create({
            'name': 'Portal Test High Risk Rule',
            'min_risk_score': 50.0,
            'max_risk_score': 100.0,
            'group_id': cls.group_manager.id,
            'company_id': cls.company_main.id,
        })

        # Create base quotation for Partner A
        cls.order_a = cls.env['sale.order'].with_user(cls.user_rep).create({
            'partner_id': cls.partner_a.id,
            'user_id': cls.user_rep.id,
            'company_id': cls.company_main.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 2,
                'price_unit': 100000.0,
                'discount': 0.0,
            })]
        })
        cls.order_a.write({
            'dealflow_approved_revision': cls.order_a.dealflow_commercial_revision,
            'dealflow_approved_risk_score': cls.order_a.risk_score,
        })

        # Create base quotation for Partner B
        cls.order_b = cls.env['sale.order'].with_user(cls.user_rep).create({
            'partner_id': cls.partner_b.id,
            'user_id': cls.user_rep.id,
            'company_id': cls.company_main.id,
            'order_line': [(0, 0, {
                'product_id': cls.product.id,
                'product_uom_qty': 5,
                'price_unit': 100000.0,
                'discount': 0.0,
            })]
        })

    def test_01_portal_customer_accesses_own_quotation(self):
        """A. Portal customer can access own eligible quotation."""
        controller = self.env['dealflow.negotiation']
        # Partner A can search own order via partner record rule
        orders = self.env['sale.order'].with_user(self.user_portal_a).search([('id', '=', self.order_a.id)])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders.id, self.order_a.id)

    def test_02_portal_customer_cannot_access_other_quotation(self):
        """B. Portal customer cannot access another customer's quotation."""
        orders = self.env['sale.order'].with_user(self.user_portal_a).search([('id', '=', self.order_b.id)])
        self.assertEqual(len(orders), 0)

    def test_03_portal_customer_creates_negotiation(self):
        """C. Portal customer can create negotiation request for own quotation."""
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'reason': 'Bulk discount request',
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 3,
                'requested_unit_price': 95000.0,
                'requested_discount': 5.0,
            })]
        })
        self.assertEqual(neg.state, 'draft')
        neg.action_submit()
        self.assertEqual(neg.state, 'submitted')

    def test_04_portal_customer_cannot_create_other_negotiation(self):
        """D. Portal customer cannot create negotiation for another customer's quotation."""
        line_b = self.order_b.order_line[0]
        with self.assertRaises(AccessError):
            self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
                'order_id': self.order_b.id,
                'reason': 'Unauthorized request',
                'line_ids': [(0, 0, {
                    'order_line_id': line_b.id,
                    'requested_quantity': 10,
                    'requested_unit_price': 50000.0,
                    'requested_discount': 20.0,
                })]
            })

    def test_05_negotiation_lines_reference_real_order_lines(self):
        """E. Negotiation lines reference real sale.order.lines."""
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 2,
                'requested_unit_price': 100000.0,
                'requested_discount': 10.0,
            })]
        })
        self.assertEqual(neg.line_ids[0].order_line_id, line_a)

    def test_06_invalid_discount_rejected(self):
        """F. Invalid discount request (>100% or <0%) rejected by constraint."""
        line_a = self.order_a.order_line[0]
        with self.assertRaises(ValidationError):
            self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
                'order_id': self.order_a.id,
                'line_ids': [(0, 0, {
                    'order_line_id': line_a.id,
                    'requested_quantity': 1,
                    'requested_unit_price': 100000.0,
                    'requested_discount': 150.0,
                })]
            })

    def test_07_invalid_quantity_rejected(self):
        """G. Invalid quantity request (<0) rejected by constraint."""
        line_a = self.order_a.order_line[0]
        with self.assertRaises(ValidationError):
            self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
                'order_id': self.order_a.id,
                'line_ids': [(0, 0, {
                    'order_line_id': line_a.id,
                    'requested_quantity': -5,
                    'requested_unit_price': 100000.0,
                    'requested_discount': 0.0,
                })]
            })

    def test_08_invalid_price_rejected(self):
        """H. Invalid price request (<0) rejected by constraint."""
        line_a = self.order_a.order_line[0]
        with self.assertRaises(ValidationError):
            self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
                'order_id': self.order_a.id,
                'line_ids': [(0, 0, {
                    'order_line_id': line_a.id,
                    'requested_quantity': 1,
                    'requested_unit_price': -100.0,
                    'requested_discount': 0.0,
                })]
            })

    def test_09_customer_cannot_modify_sale_order_directly(self):
        """I. Customer cannot directly modify sale.order."""
        with self.assertRaises(AccessError):
            self.order_a.with_user(self.user_portal_a).write({'amount_total': 1.0})

    def test_10_customer_cannot_access_approval_records(self):
        """J. Customer cannot access approval records."""
        approval = self.env['dealflow.approval'].sudo().create({
            'order_id': self.order_a.id,
            'status': 'pending',
        })
        with self.assertRaises(AccessError):
            self.env['dealflow.approval'].with_user(self.user_portal_a).search([('id', '=', approval.id)])

    def test_11_customer_cannot_access_risk_config(self):
        """K. Customer cannot access internal risk configuration."""
        with self.assertRaises(AccessError):
            self.env['dealflow.approval.rule'].with_user(self.user_portal_a).search([])

    def test_12_submitted_negotiation_immutable_by_customer(self):
        """L. Submitted negotiation cannot be modified by customer."""
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 2,
                'requested_unit_price': 90000.0,
                'requested_discount': 10.0,
            })]
        })
        neg.action_submit()
        with self.assertRaises(AccessError):
            neg.with_user(self.user_portal_a).write({'reason': 'Customer trying to mutate submitted request'})

    def test_13_stale_negotiation_detected_on_revision_change(self):
        """M. Stale negotiation is detected when commercial revision changes."""
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 2,
                'requested_unit_price': 90000.0,
                'requested_discount': 10.0,
            })]
        })
        # Sales team modifies quotation, advancing commercial revision
        self.order_a.with_user(self.user_rep).write({
            'dealflow_commercial_revision': self.order_a.dealflow_commercial_revision + 1
        })
        neg.action_submit()
        self.assertEqual(neg.state, 'stale')

    def test_14_stale_negotiation_cannot_be_applied(self):
        """N. Stale negotiation cannot be applied."""
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'base_commercial_revision': self.order_a.dealflow_commercial_revision,
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 2,
                'requested_unit_price': 90000.0,
                'requested_discount': 10.0,
            })]
        })
        neg.sudo().write({'state': 'submitted'})
        # Revision changes
        self.order_a.sudo().write({'dealflow_commercial_revision': self.order_a.dealflow_commercial_revision + 1})
        with self.assertRaises(UserError):
            neg.with_user(self.user_manager).action_accept()

    def test_15_authorized_user_accepts_negotiation(self):
        """O. Authorized internal user can review/accept valid negotiation."""
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 2,
                'requested_unit_price': 90000.0,
                'requested_discount': 10.0,
            })]
        })
        neg.action_submit()
        neg.with_user(self.user_manager).action_accept()
        self.assertEqual(neg.state, 'accepted')

    def test_16_accepting_negotiation_updates_sale_order_line(self):
        """P. Accepting negotiation changes actual sale.order.line values."""
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 5,
                'requested_unit_price': 85000.0,
                'requested_discount': 12.0,
            })]
        })
        neg.action_submit()
        neg.with_user(self.user_manager).action_accept()

        self.assertEqual(line_a.product_uom_qty, 5)
        self.assertEqual(line_a.price_unit, 85000.0)
        self.assertEqual(line_a.discount, 12.0)

    def test_17_commercial_revision_increments_after_acceptance(self):
        """Q. Commercial revision changes after accepted commercial modification."""
        initial_rev = self.order_a.dealflow_commercial_revision
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 2,
                'requested_unit_price': 80000.0,
                'requested_discount': 15.0,
            })]
        })
        neg.action_submit()
        neg.with_user(self.user_manager).action_accept()
        self.assertGreater(self.order_a.dealflow_commercial_revision, initial_rev)

    def test_18_approval_invalidated_after_negotiation_acceptance(self):
        """R. Existing approval is invalidated/requires reapproval when applicable."""
        approval = self.env['dealflow.approval'].sudo().create({
            'order_id': self.order_a.id,
            'status': 'approved',
        })
        self.order_a.sudo().write({'approval_status': 'approved'})
        
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 2,
                'requested_unit_price': 70000.0,
                'requested_discount': 20.0,
            })]
        })
        neg.action_submit()
        neg.with_user(self.user_manager).action_accept()

        self.assertEqual(approval.status, 'stale')
        self.assertEqual(self.order_a.approval_status, 'none')

    def test_19_unauthorized_internal_user_cannot_action_negotiation(self):
        """S. Unauthorized internal user without sales access cannot accept/reject negotiation."""
        user_no_sales = self.env['res.users'].create({
            'name': 'No Sales User',
            'login': 'no_sales_user_df360',
            'email': 'nosales@example.com',
            'group_ids': [(6, 0, [self.group_user.id])],
        })
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 2,
                'requested_unit_price': 90000.0,
                'requested_discount': 5.0,
            })]
        })
        neg.action_submit()
        with self.assertRaises(AccessError):
            neg.with_user(user_no_sales).action_accept()

    def test_20_rejected_negotiation_cannot_be_accepted(self):
        """T. Rejected negotiation cannot be accepted."""
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 2,
                'requested_unit_price': 90000.0,
                'requested_discount': 5.0,
            })]
        })
        neg.action_submit()
        neg.with_user(self.user_manager).action_reject(reason="Price too low")
        self.assertEqual(neg.state, 'rejected')

        with self.assertRaises(UserError):
            neg.with_user(self.user_manager).action_accept()

    def test_21_accepted_negotiation_cannot_be_reaccepted(self):
        """U. Accepted negotiation cannot be accepted again."""
        line_a = self.order_a.order_line[0]
        neg = self.env['dealflow.negotiation'].with_user(self.user_portal_a).create({
            'order_id': self.order_a.id,
            'line_ids': [(0, 0, {
                'order_line_id': line_a.id,
                'requested_quantity': 2,
                'requested_unit_price': 90000.0,
                'requested_discount': 5.0,
            })]
        })
        neg.action_submit()
        neg.with_user(self.user_manager).action_accept()
        self.assertEqual(neg.state, 'accepted')

        with self.assertRaises(UserError):
            neg.with_user(self.user_manager).action_accept()

    def test_22_multi_company_isolation_on_negotiations(self):
        """V. Multi-company isolation on negotiations."""
        order_other = self.env['sale.order'].with_user(self.user_rep).with_company(self.company_other).create({
            'partner_id': self.partner_a.id,
            'company_id': self.company_other.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'price_unit': 100000.0,
            })]
        })
        neg_other = self.env['dealflow.negotiation'].sudo().create({
            'order_id': order_other.id,
            'state': 'submitted',
        })

        mgr_main = self.env['dealflow.negotiation'].with_user(self.user_manager).with_context(allowed_company_ids=[self.company_main.id])
        negs = mgr_main.search([('id', '=', neg_other.id)])
        self.assertEqual(len(negs), 0)

    def test_23_phase1_risk_engine_regression(self):
        """W. Existing Phase 1 risk engine calculation."""
        self.assertIsNotNone(self.order_a.risk_score)
        self.assertIn(self.order_a.risk_level, ['low', 'medium', 'high'])

    def test_24_phase2_discount_governance_regression(self):
        """X. Existing Phase 2 discount governance check."""
        rule = self.env.ref('dealflow360.rule_gold_hardware')
        self.assertEqual(rule.max_discount, 15.0)

    def test_25_phase3_approval_engine_regression(self):
        """Y. Existing Phase 3 approval engine rule lookup."""
        rules = self.env['dealflow.approval.rule'].search([('company_id', '=', self.company_main.id)])
        self.assertGreaterEqual(len(rules), 1)

    def test_26_phase4_recommendation_engine_regression(self):
        """Z. Existing Phase 4 recommendation engine lookup."""
        recs = self.env['dealflow.product.recommendation'].search([('company_id', '=', self.company_main.id)])
        self.assertGreaterEqual(len(recs), 1)

    def test_27_f1_command_center_regression(self):
        """AA. F1 get_dashboard_data() regression check."""
        data = self.env['dealflow.dashboard'].with_user(self.user_manager).get_dashboard_data()
        self.assertIn('kpis', data)

    def test_28_f2_sales_rep_workspace_regression(self):
        """AB. F2 get_sales_rep_workspace_data() regression check."""
        data = self.env['dealflow.dashboard'].with_user(self.user_rep).get_sales_rep_workspace_data()
        self.assertIn('kpis', data)

    def test_29_f3_sales_manager_data_regression(self):
        """AC. F3 get_sales_manager_data() regression check."""
        data = self.env['dealflow.dashboard'].with_user(self.user_manager).get_sales_manager_data()
        self.assertIn('kpis', data)

    def test_30_negotiation_status_endpoint_own_negotiation_only(self):
        """AD. Negotiation status endpoint only exposes own negotiation."""
        from odoo.addons.dealflow360.controllers.portal import DealFlowPortalController
        controller = DealFlowPortalController()
        
        # Create negotiation for Partner B
        line_b = self.order_b.order_line[0]
        neg_b = self.env['dealflow.negotiation'].sudo().create({
            'order_id': self.order_b.id,
            'state': 'submitted',
            'line_ids': [(0, 0, {
                'order_line_id': line_b.id,
                'requested_quantity': 10,
                'requested_unit_price': 90000.0,
                'requested_discount': 5.0,
            })]
        })

        # Partner A user attempts to get status of Partner B's negotiation
        controller._test_env = self.env(user=self.user_portal_a)
        res = controller.get_negotiation_status(neg_b.id)
        self.assertEqual(res.get('status'), 'error')
        self.assertIn('Access denied', res.get('message', ''))

    def test_31_quotation_endpoint_customer_safe_fields_only(self):
        """AE. Quotation endpoint only exposes customer-safe fields."""
        from odoo.addons.dealflow360.controllers.portal import DealFlowPortalController
        controller = DealFlowPortalController()
        controller._test_env = self.env(user=self.user_portal_a)

        res = controller.get_quotation_details(self.order_a.id)
        self.assertEqual(res.get('status'), 'success')
        quot = res.get('quotation', {})
        # Verify safe fields present
        self.assertIn('name', quot)
        self.assertIn('amount_total', quot)
        self.assertIn('lines', quot)
        # Verify internal fields strictly omitted
        self.assertNotIn('risk_score', quot)
        self.assertNotIn('risk_level', quot)
        self.assertNotIn('approval_logs', quot)
        self.assertNotIn('margin', quot)

    def test_32_controller_submit_negotiation(self):
        """AF. Controller negotiation submission endpoint."""
        from odoo.addons.dealflow360.controllers.portal import DealFlowPortalController
        controller = DealFlowPortalController()
        controller._test_env = self.env(user=self.user_portal_a)

        line_a = self.order_a.order_line[0]
        res = controller.submit_negotiation(
            order_id=self.order_a.id,
            lines=[{
                'order_line_id': line_a.id,
                'requested_quantity': 4,
                'requested_unit_price': 92000.0,
                'requested_discount': 8.0,
            }],
            reason="Controller test request"
        )
        self.assertEqual(res.get('status'), 'success')
        self.assertEqual(res['negotiation']['state'], 'submitted')
