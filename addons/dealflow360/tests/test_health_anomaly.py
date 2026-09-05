from odoo.tests.common import TransactionCase, tagged

@tagged('post_install', '-at_install')
class TestHealthAnomaly(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env['res.partner'].create({'name': 'Health Partner'})
        cls.product = cls.env['product.product'].create({
            'name': 'Laptop',
            'type': 'consu',
            'list_price': 1000.0,
        })
        
    def test_c1_d1_health_and_anomaly(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [
                (0, 0, {'product_id': self.product.id, 'product_uom_qty': 1}),
            ]
        })
        
        # Initial health should be healthy
        health = self.env['dealflow.deal.health'].search([('order_id', '=', order.id), ('status', '=', 'active')], limit=1)
        self.assertEqual(health.health_level, 'healthy')
        self.assertEqual(health.health_score, 100)
        
        # Trigger extreme discount anomaly by writing huge discount
        # Note: since we don't have a specific rule set up in this test class, discount_allowed defaults to 0
        order.order_line[0].discount = 50.0
        
        # Writing triggers detect_anomalies which triggers health evaluation
        anomaly = self.env['dealflow.anomaly'].search([('order_id', '=', order.id), ('anomaly_type', '=', 'extreme_discount'), ('state', '=', 'active')], limit=1)
        self.assertTrue(anomaly, "Extreme discount anomaly should be created")
        
        # Re-fetch active health
        health = self.env['dealflow.deal.health'].search([('order_id', '=', order.id), ('status', '=', 'active')], limit=1)
        
        # Health score should be lower. 
        # Risk > 20 -> -25
        # Anomaly -> -15
        self.assertLess(health.health_score, 100)
        self.assertIn("Extreme discount requested", anomaly.description)
