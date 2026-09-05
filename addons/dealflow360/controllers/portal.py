# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, UserError, ValidationError

class DealFlowPortalController(http.Controller):

    def _env(self):
        if getattr(self, '_test_env', None):
            return self._test_env
        try:
            if request and hasattr(request, 'env') and request.env:
                return request.env
        except Exception:
            pass
        return http.request.env if http.request else None

    def _check_quotation_access(self, order, access_token=None):
        if not order.exists():
            return False, "Quotation not found."

        # Check access token if provided
        if access_token and hasattr(order, 'access_token') and order.access_token == access_token:
            return True, ""

        # Check authenticated user partner ownership
        env = self._env()
        user = env.user if env else False
        if not user or user._is_public():
            if not access_token:
                return False, "Authentication required."
            return False, "Invalid access token."

        user_partner = user.partner_id.commercial_partner_id
        order_partner = order.partner_id.commercial_partner_id
        if user_partner and order_partner and user_partner == order_partner:
            return True, ""

        return False, "Access denied for this quotation."

    @http.route('/dealflow/api/quotation/<int:order_id>', type='json', auth='public', methods=['POST', 'GET'], csrf=False)
    def get_quotation_details(self, order_id, access_token=None, **kw):
        env = self._env()
        order = env['sale.order'].sudo().browse(order_id)
        valid, msg = self._check_quotation_access(order, access_token=access_token)
        if not valid:
            return {'status': 'error', 'message': msg}

        lines = []
        for line in order.order_line:
            lines.append({
                'id': line.id,
                'product_name': line.product_id.name if line.product_id else '',
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit,
                'discount': line.discount,
                'price_subtotal': line.price_subtotal,
            })

        # Find active or latest negotiation for this quotation
        active_neg = env['dealflow.negotiation'].sudo().search([
            ('order_id', '=', order.id)
        ], order='id desc', limit=1)

        # Deliberately hide internal risk score, risk level, internal approval logs, margins, costs
        return {
            'status': 'success',
            'quotation': {
                'id': order.id,
                'name': order.name,
                'date_order': order.date_order.strftime('%Y-%m-%d %H:%M:%S') if order.date_order else '',
                'expiration_date': order.validity_date.strftime('%Y-%m-%d') if order.validity_date else '',
                'currency_symbol': order.currency_id.symbol if order.currency_id else '',
                'amount_untaxed': order.amount_untaxed,
                'amount_total': order.amount_total,
                'state': order.state,
                'commercial_revision': order.dealflow_commercial_revision,
                'active_negotiation_id': active_neg.id if active_neg else False,
                'lines': lines
            }
        }

    @http.route('/dealflow/api/negotiation/submit', type='json', auth='public', methods=['POST'], csrf=False)
    def submit_negotiation(self, order_id, lines=None, reason='', access_token=None, **kw):
        env = self._env()
        order = env['sale.order'].sudo().browse(order_id)
        valid, msg = self._check_quotation_access(order, access_token=access_token)
        if not valid:
            return {'status': 'error', 'message': msg}

        if not lines or not isinstance(lines, list):
            return {'status': 'error', 'message': 'At least one line modification must be provided.'}

        try:
            negotiation = env['dealflow.negotiation'].sudo().create({
                'order_id': order.id,
                'reason': reason,
                'base_commercial_revision': order.dealflow_commercial_revision,
                'state': 'draft'
            })

            for l in lines:
                line_id = l.get('order_line_id')
                order_line = env['sale.order.line'].sudo().browse(line_id)
                if not order_line.exists() or order_line.order_id.id != order.id:
                    raise ValidationError(f"Invalid order line ID: {line_id}")

                env['dealflow.negotiation.line'].sudo().create({
                    'negotiation_id': negotiation.id,
                    'order_line_id': order_line.id,
                    'requested_quantity': float(l.get('requested_quantity', order_line.product_uom_qty)),
                    'requested_unit_price': float(l.get('requested_unit_price', order_line.price_unit)),
                    'requested_discount': float(l.get('requested_discount', order_line.discount)),
                    'customer_reason': l.get('customer_reason', '')
                })

            negotiation.action_submit()

            return {
                'status': 'success',
                'negotiation': {
                    'id': negotiation.id,
                    'name': negotiation.name,
                    'state': negotiation.state,
                    'requested_date': negotiation.requested_date.strftime('%Y-%m-%d %H:%M:%S') if negotiation.requested_date else ''
                }
            }
        except (UserError, ValidationError) as e:
            return {'status': 'error', 'message': str(e)}
        except Exception as e:
            return {'status': 'error', 'message': 'Failed to submit negotiation request.'}

    @http.route('/dealflow/api/negotiation/status/<int:negotiation_id>', type='json', auth='public', methods=['POST', 'GET'], csrf=False)
    def get_negotiation_status(self, negotiation_id, access_token=None, **kw):
        env = self._env()
        negotiation = env['dealflow.negotiation'].sudo().browse(negotiation_id)
        if not negotiation.exists():
            return {'status': 'error', 'message': 'Negotiation not found.'}

        valid, msg = self._check_quotation_access(negotiation.order_id, access_token=access_token)
        if not valid:
            return {'status': 'error', 'message': msg}

        lines = []
        for l in negotiation.line_ids:
            lines.append({
                'id': l.id,
                'product_name': l.product_id.name if l.product_id else '',
                'current_quantity': l.current_quantity,
                'requested_quantity': l.requested_quantity,
                'current_unit_price': l.current_unit_price,
                'requested_unit_price': l.requested_unit_price,
                'current_discount': l.current_discount,
                'requested_discount': l.requested_discount,
                'change_type': l.change_type,
            })

        return {
            'status': 'success',
            'negotiation': {
                'id': negotiation.id,
                'name': negotiation.name,
                'order_name': negotiation.order_id.name,
                'state': negotiation.state,
                'requested_date': negotiation.requested_date.strftime('%Y-%m-%d %H:%M:%S') if negotiation.requested_date else '',
                'processed_date': negotiation.processed_date.strftime('%Y-%m-%d %H:%M:%S') if negotiation.processed_date else '',
                'rejection_reason': negotiation.rejection_reason or '',
                'lines': lines
            }
        }
