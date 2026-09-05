from odoo.tests.common import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestHybridBilling(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.partner = cls.env['res.partner'].create({'name': 'Billing Partner'})
        
        cls.product_one_time = cls.env['product.product'].create({
            'name': 'Laptop',
            'type': 'consu',
            'list_price': 1000.0,
        })
        
        cls.product_recurring = cls.env['product.product'].create({
            'name': 'Support Subscription',
            'type': 'service',
            'list_price': 500.0,
        })

    def test_b1_b2_b3_line_classification(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {'product_id': self.product_one_time.id, 'product_uom_qty': 1, 'is_recurring': False}),
                (0, 0, {'product_id': self.product_recurring.id, 'product_uom_qty': 1, 'is_recurring': True}),
            ]
        })
        
        line_ot = order.order_line.filtered(lambda l: l.product_id == self.product_one_time)
        line_rec = order.order_line.filtered(lambda l: l.product_id == self.product_recurring)
        
        self.assertEqual(line_ot.billing_classification, 'one_time')
        self.assertEqual(line_rec.billing_classification, 'recurring')

    def test_b8_risk_includes_recurring(self):
        # We need to test if discount risk is evaluated on recurring lines.
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {'product_id': self.product_recurring.id, 'product_uom_qty': 1, 'discount': 50, 'is_recurring': True}),
            ]
        })
        
        line = order.order_line[0]
        # Since there's no rule, 50% discount should trigger risk flag
        self.assertTrue(line.risk_flag)
        self.assertGreater(line.discount_excess, 0.0)
