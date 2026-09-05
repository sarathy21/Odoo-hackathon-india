from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import AccessError, ValidationError

@tagged('post_install', '-at_install')
class TestCRUDOperations(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.manager_user = cls.env['res.users'].create({
            'name': 'Test Manager CRUD',
            'login': 'manager_crud',
            'group_ids': [(6, 0, [cls.env.ref('dealflow360.group_dealflow_manager').id, cls.env.ref('base.group_user').id])]
        })

        cls.rep_user = cls.env['res.users'].create({
            'name': 'Test Rep CRUD',
            'login': 'rep_crud',
            'group_ids': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman').id, cls.env.ref('base.group_user').id])]
        })
        
        cls.company = cls.env.company
        cls.category = cls.env['product.category'].create({'name': 'Test Category'})
        
    def test_01_customer_tier_crud(self):
        # Manager creates
        tier = self.env['dealflow.customer.tier'].with_user(self.manager_user).create({
            'name': 'Diamond Tier'
        })
        self.assertTrue(tier.id)
        
        # Manager reads
        read_tier = self.env['dealflow.customer.tier'].with_user(self.manager_user).browse(tier.id)
        self.assertEqual(read_tier.name, 'Diamond Tier')
        
        # Manager updates
        tier.with_user(self.manager_user).write({'name': 'Platinum Tier'})
        self.assertEqual(tier.name, 'Platinum Tier')
        
        # Rep reads
        read_tier_rep = self.env['dealflow.customer.tier'].with_user(self.rep_user).browse(tier.id)
        self.assertEqual(read_tier_rep.name, 'Platinum Tier')
        
        # Rep cannot create
        with self.assertRaises(AccessError):
            self.env['dealflow.customer.tier'].with_user(self.rep_user).create({
                'name': 'Hacker Tier'
            })
            
        # Manager archives
        tier.with_user(self.manager_user).write({'active': False})
        self.assertFalse(tier.active)
        
    def test_02_discount_rule_crud(self):
        tier = self.env['dealflow.customer.tier'].create({'name': 'Test Tier D'})
        
        # Manager creates
        rule = self.env['dealflow.discount.rule'].with_user(self.manager_user).create({
            'name': 'Test Discount',
            'tier_id': tier.id,
            'category_id': self.category.id,
            'max_discount': 25.0
        })
        self.assertTrue(rule.id)
            
        with self.assertRaises(ValidationError):
            rule.with_user(self.manager_user).write({'max_discount': 150.0})
            
    def test_03_approval_rule_crud(self):
        group = self.env.ref('dealflow360.group_dealflow_manager')
        
        # Manager creates
        rule = self.env['dealflow.approval.rule'].with_user(self.manager_user).create({
            'name': 'Test Approval Rule',
            'min_risk_score': 10,
            'max_risk_score': 50,
            'group_id': group.id,
            'sequence': 99
        })
        self.assertTrue(rule.id)

    def test_04_product_recommendation_crud(self):
        prod_a = self.env['product.product'].create({'name': 'Source Prod'})
        prod_b = self.env['product.product'].create({'name': 'Rec Prod'})
        
        rec = self.env['dealflow.product.recommendation'].with_user(self.manager_user).create({
            'source_product_id': prod_a.id,
            'recommended_product_id': prod_b.id,
            'recommendation_type': 'upsell'
        })
        self.assertTrue(rec.id)
