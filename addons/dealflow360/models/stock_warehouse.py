from odoo import models, fields

class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    dealflow_priority = fields.Integer(
        string='DealFlow Priority',
        default=10,
        help='Lower number = higher preference during automatic fulfillment allocation.'
    )
    dealflow_base_shipping_cost = fields.Float(
        string='Base Shipping Cost',
        default=0.0,
        help='Estimated shipping cost used as a planning tie-breaker.'
    )
