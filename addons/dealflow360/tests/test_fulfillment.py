from odoo.tests.common import TransactionCase, tagged
from odoo.exceptions import UserError

@tagged('post_install', '-at_install')
class TestFulfillment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        
        cls.company = cls.env.company
        
        # Warehouses
        cls.warehouse_main = cls.env['stock.warehouse'].search([('company_id', '=', cls.company.id)], limit=1)
        cls.warehouse_main.dealflow_priority = 10
        cls.warehouse_main.dealflow_base_shipping_cost = 5.0
        
        cls.warehouse_alt = cls.env['stock.warehouse'].create({
            'name': 'Alt Warehouse',
            'code': 'ALT',
            'company_id': cls.company.id,
            'dealflow_priority': 5,  # Better priority
            'dealflow_base_shipping_cost': 10.0,
        })
        
        cls.warehouse_cheap = cls.env['stock.warehouse'].create({
            'name': 'Cheap Warehouse',
            'code': 'CHP',
            'company_id': cls.company.id,
            'dealflow_priority': 20,
            'dealflow_base_shipping_cost': 2.0,  # Best shipping cost
        })

        # Partner
        cls.partner = cls.env['res.partner'].create({'name': 'Fulfillment Partner'})
        
        # Product
        cls.product = cls.env['product.product'].create({
            'name': 'Stockable Product',
            'type': 'consu',
            'is_storable': True,
            'list_price': 100.0,
        })
        
        cls.service = cls.env['product.product'].create({
            'name': 'Service Product',
            'type': 'service',
            'list_price': 50.0,
        })

    def _update_qty_on_hand(self, product, warehouse, qty):
        location = warehouse.lot_stock_id
        available = self.env['stock.quant']._get_available_quantity(product, location)
        if available != 0:
            self.env['stock.quant']._update_available_quantity(product, location, -available)
        if qty > 0:
            self.env['stock.quant']._update_available_quantity(product, location, qty)

    def test_a1_a2_stockable_line_allocation(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'warehouse_id': self.warehouse_main.id,
            'order_line': [
                (0, 0, {'product_id': self.product.id, 'product_uom_qty': 10}),
                (0, 0, {'product_id': self.service.id, 'product_uom_qty': 5}),
            ]
        })
        
        self._update_qty_on_hand(self.product, self.warehouse_main, 15)
        
        plan = self.env['dealflow.fulfillment.plan'].create({'order_id': order.id})
        plan.action_generate_fulfillment_plan()
        
        # Service should not be allocated
        service_allocs = plan.allocation_ids.filtered(lambda a: a.product_id == self.service)
        self.assertEqual(len(service_allocs), 0)
        
        # Stockable should be allocated
        stock_allocs = plan.allocation_ids.filtered(lambda a: a.product_id == self.product)
        self.assertEqual(len(stock_allocs), 1)
        self.assertEqual(stock_allocs.allocated_qty, 10.0)
        self.assertEqual(stock_allocs.warehouse_id, self.warehouse_main)
        self.assertEqual(stock_allocs.backorder_qty, 0.0)

    def test_a3_a4_a5_warehouse_priority_and_split(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'warehouse_id': self.warehouse_main.id,
            'order_line': [
                (0, 0, {'product_id': self.product.id, 'product_uom_qty': 20}),
            ]
        })
        
        # Main has 5, Alt has 10, Cheap has 8.
        # Total needed: 20. None can fulfill fully.
        # Order of sorting when no full fulfill: Default (Main), then Cheap (cost), then Alt (priority).
        # Actually, let's check sorting:
        # Default first: Main
        # Then lower cost: Cheap
        # Then better priority: Alt
        self._update_qty_on_hand(self.product, self.warehouse_main, 5)
        self._update_qty_on_hand(self.product, self.warehouse_alt, 10)
        self._update_qty_on_hand(self.product, self.warehouse_cheap, 8)
        
        plan = self.env['dealflow.fulfillment.plan'].create({'order_id': order.id})
        plan.action_generate_fulfillment_plan()
        
        self.assertEqual(len(plan.allocation_ids), 3)
        # Should be: Main=5, Cheap=8, Alt=7
        main_alloc = plan.allocation_ids.filtered(lambda a: a.warehouse_id == self.warehouse_main)
        cheap_alloc = plan.allocation_ids.filtered(lambda a: a.warehouse_id == self.warehouse_cheap)
        alt_alloc = plan.allocation_ids.filtered(lambda a: a.warehouse_id == self.warehouse_alt)
        
        self.assertEqual(main_alloc.allocated_qty, 5.0)
        self.assertEqual(cheap_alloc.allocated_qty, 8.0)
        self.assertEqual(alt_alloc.allocated_qty, 7.0)

    def test_a6_a7_backorder(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'warehouse_id': self.warehouse_main.id,
            'order_line': [
                (0, 0, {'product_id': self.product.id, 'product_uom_qty': 50}),
            ]
        })
        
        self._update_qty_on_hand(self.product, self.warehouse_main, 10)
        self._update_qty_on_hand(self.product, self.warehouse_alt, 0)
        self._update_qty_on_hand(self.product, self.warehouse_cheap, 0)
        
        plan = self.env['dealflow.fulfillment.plan'].create({'order_id': order.id})
        plan.action_generate_fulfillment_plan()
        
        allocs = plan.allocation_ids
        self.assertEqual(len(allocs), 1)
        self.assertEqual(allocs.allocated_qty, 10)
        self.assertEqual(allocs.backorder_qty, 40)

    def test_a10_procurement_override(self):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'warehouse_id': self.warehouse_main.id,
            'order_line': [
                (0, 0, {'product_id': self.product.id, 'product_uom_qty': 20}),
            ]
        })
        
        self._update_qty_on_hand(self.product, self.warehouse_main, 5)
        self._update_qty_on_hand(self.product, self.warehouse_alt, 15)
        
        plan = self.env['dealflow.fulfillment.plan'].create({'order_id': order.id})
        plan.action_generate_fulfillment_plan()
        
        plan.action_validate_fulfillment_plan()
        plan.state = 'applied'
        
        # Call the actual override
        # We need to trigger procurement which happens on action_confirm
        order.action_confirm()
        
        pickings = order.picking_ids
        self.assertTrue(len(pickings) >= 2, "Should create pickings from multiple warehouses")
        
        wh_ids = pickings.mapped('picking_type_id.warehouse_id')
        self.assertIn(self.warehouse_main, wh_ids)
        self.assertIn(self.warehouse_alt, wh_ids)
