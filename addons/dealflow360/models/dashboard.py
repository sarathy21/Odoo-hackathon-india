# -*- coding: utf-8 -*-
from odoo import models, api, fields
from odoo.exceptions import AccessError

class DealFlowDashboard(models.AbstractModel):
    _name = 'dealflow.dashboard'
    _description = 'DealFlow Dashboard Data Provider'

    @api.model
    def get_current_user_info(self):
        user = self.env.user
        is_admin = user.has_group('base.group_system')
        is_dealflow_manager = user.has_group('dealflow360.group_dealflow_manager')
        is_sales_manager = user.has_group('sales_team.group_sale_manager')
        is_sales_rep = user.has_group('sales_team.group_sale_salesman') or user.has_group('sales_team.group_sale_salesman_all_leads')
        is_stock_manager = user.has_group('stock.group_stock_manager')
        is_portal = user.has_group('base.group_portal')

        if is_admin:
            role_code = "admin"
            role_name = "Administrator"
            can_manage = True
        elif is_dealflow_manager or is_sales_manager:
            role_code = "manager"
            role_name = "DealFlow Manager"
            can_manage = True
        elif is_stock_manager:
            role_code = "warehouse_manager"
            role_name = "Warehouse Manager"
            can_manage = False
        elif is_sales_rep:
            role_code = "sales_rep"
            role_name = "Sales Representative"
            can_manage = False
        elif is_portal:
            role_code = "portal"
            role_name = "Customer"
            can_manage = False
        else:
            role_code = "user"
            role_name = "Internal User"
            can_manage = False

        return {
            'user_id': user.id,
            'user_name': user.name,
            'user_login': user.login,
            'user_email': user.email or user.partner_id.email or '',
            'role_code': role_code,
            'role_name': role_name,
            'can_manage': can_manage,
            'is_admin': is_admin,
            'is_sales_rep': is_sales_rep,
            'is_portal': is_portal,
            'default_action': 'dealflow360.action_dealflow_command_center' if can_manage else 'dealflow360.action_dealflow_sales_rep_workspace',
        }

    @api.model
    def get_dashboard_data(self):
        if not (self.env.user.has_group('dealflow360.group_dealflow_manager') or self.env.user.has_group('base.group_system')):
            raise AccessError("Access denied: You do not have permissions to access the DealFlow360 Command Center.")

        company_ids = self.env.companies.ids
        company_currency = self.env.company.currency_id
        currency_symbol = company_currency.symbol or ''
        currency_position = company_currency.position or 'before'

        domain_active_deals = [('state', 'in', ['draft', 'sent', 'sale']), ('company_id', 'in', company_ids)]
        
        # 1. KPIs
        active_deals_count = self.env['sale.order'].search_count(domain_active_deals)
        active_deals = self.env['sale.order'].search(domain_active_deals)
        pipeline_value = sum(active_deals.mapped('amount_total'))

        # High Risk Deals
        high_risk_domain = domain_active_deals + [('risk_level', '=', 'high')]
        high_risk_count = self.env['sale.order'].search_count(high_risk_domain)

        # Pending Approvals
        pending_approval_count = self.env['dealflow.approval'].search_count([
            ('status', '=', 'pending'),
            '|', ('company_id', '=', False), ('company_id', 'in', company_ids)
        ])

        # Active Recommendation Rules
        active_rec_rules = self.env['dealflow.product.recommendation'].search_count([
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', 'in', company_ids)
        ])

        # 2. Deals Requiring Attention (Pending Approval or High Risk or Rejected)
        attention_domain = domain_active_deals + ['|', '|', ('approval_status', '=', 'pending'), ('risk_level', '=', 'high'), ('approval_status', '=', 'rejected')]
        attention_deals_records = self.env['sale.order'].search_read(
            attention_domain,
            ['name', 'partner_id', 'amount_total', 'risk_score', 'risk_level', 'approval_status', 'currency_id'],
            limit=10,
            order='risk_score desc, id desc'
        )
        
        # Fetch currencies for attention deals
        currency_ids = list(set(d['currency_id'][0] for d in attention_deals_records if d.get('currency_id')))
        currencies = self.env['res.currency'].browse(currency_ids)
        currency_map = {c.id: c.symbol or '' for c in currencies}

        attention_deals = []
        for d in attention_deals_records:
            cur_id = d['currency_id'][0] if d.get('currency_id') else False
            attention_deals.append({
                'id': d['id'],
                'name': d['name'],
                'customer': d['partner_id'][1] if d.get('partner_id') else 'Unknown',
                'amount_total': d['amount_total'],
                'currency_symbol': currency_map.get(cur_id, currency_symbol),
                'risk_score': round(d['risk_score'], 1) if d.get('risk_score') else 0.0,
                'risk_level': d['risk_level'] or 'low',
                'approval_status': d['approval_status'] or 'none'
            })

        # 3. Pending Approvals List
        pending_approval_records = self.env['dealflow.approval'].search([
            ('status', '=', 'pending'),
            '|', ('company_id', '=', False), ('company_id', 'in', company_ids)
        ], limit=10, order='id desc')
        
        pending_approvals = []
        for app in pending_approval_records:
            current_step = False
            for step in app.step_ids:
                if step.status == 'pending':
                    current_step = step.rule_id.name
                    break
            
            pending_approvals.append({
                'id': app.id,
                'order_id': app.order_id.id if app.order_id else False,
                'order_name': app.order_id.name if app.order_id else 'Unknown',
                'customer': app.order_id.partner_id.name if (app.order_id and app.order_id.partner_id) else 'Unknown',
                'risk_score': round(app.order_id.risk_score, 1) if app.order_id else 0.0,
                'status': app.status,
                'current_step': current_step or 'Pending Review',
                'requester': app.create_uid.name if app.create_uid else 'System',
                'create_date': app.create_date.strftime('%Y-%m-%d %H:%M') if app.create_date else ''
            })

        # 4. Recommendation Rules Summary List (top 3)
        rec_rules_records = self.env['dealflow.product.recommendation'].search_read([
            ('active', '=', True),
            '|', ('company_id', '=', False), ('company_id', 'in', company_ids)
        ], ['name', 'source_product_id', 'recommended_product_id', 'recommendation_type', 'priority'], limit=3, order='priority desc, id desc')

        rec_rules_list = []
        for r in rec_rules_records:
            rec_rules_list.append({
                'id': r['id'],
                'name': r['name'],
                'source_product': r['source_product_id'][1] if r.get('source_product_id') else '',
                'recommended_product': r['recommended_product_id'][1] if r.get('recommended_product_id') else '',
                'type_label': 'Upsell' if r.get('recommendation_type') == 'upsell' else 'Cross-sell',
                'priority': r.get('priority', 0)
            })

        return {
            'kpis': {
                'active_deals': active_deals_count,
                'pipeline_value': pipeline_value,
                'high_risk_deals': high_risk_count,
                'pending_approvals': pending_approval_count,
                'currency_symbol': currency_symbol,
                'currency_position': currency_position
            },
            'attention_deals': attention_deals,
            'pending_approvals_list': pending_approvals,
            'recommendations_summary': {
                'active_rules': active_rec_rules,
                'rules_list': rec_rules_list
            }
        }

    @api.model
    def get_sales_rep_workspace_data(self):
        company_ids = self.env.companies.ids
        company_currency = self.env.company.currency_id
        currency_symbol = company_currency.symbol or ''
        currency_position = company_currency.position or 'before'

        # Current user filters
        uid = self.env.uid
        user_domain = [('user_id', '=', uid), ('company_id', 'in', company_ids)]
        
        # 1. KPIs
        
        # My Quotations
        my_quotations_domain = user_domain + [('state', 'in', ['draft', 'sent'])]
        my_quotations_count = self.env['sale.order'].search_count(my_quotations_domain)

        # Pending Approval (Approvals for My Deals)
        pending_approval_domain = [('status', '=', 'pending'), ('order_id.user_id', '=', uid), ('company_id', 'in', company_ids)]
        pending_approval_count = self.env['dealflow.approval'].search_count(pending_approval_domain)

        # High Risk
        high_risk_domain = my_quotations_domain + [('risk_level', '=', 'high')]
        high_risk_count = self.env['sale.order'].search_count(high_risk_domain)

        # Orders (Confirmed)
        orders_domain = user_domain + [('state', '=', 'sale')]
        orders_count = self.env['sale.order'].search_count(orders_domain)

        # 2. My Deals Table
        my_deals_domain = user_domain + [('state', 'in', ['draft', 'sent', 'sale'])]
        my_deals_records = self.env['sale.order'].search_read(
            my_deals_domain,
            ['name', 'partner_id', 'amount_total', 'state', 'risk_score', 'risk_level', 'approval_status', 'currency_id'],
            limit=20,
            order='id desc'
        )

        # Fetch currencies for my deals
        currency_ids = list(set(d['currency_id'][0] for d in my_deals_records if d.get('currency_id')))
        currencies = self.env['res.currency'].browse(currency_ids)
        currency_map = {c.id: c.symbol or '' for c in currencies}

        my_deals = []
        for d in my_deals_records:
            cur_id = d['currency_id'][0] if d.get('currency_id') else False
            my_deals.append({
                'id': d['id'],
                'name': d['name'],
                'customer': d['partner_id'][1] if d.get('partner_id') else 'Unknown',
                'amount_total': d['amount_total'],
                'currency_symbol': currency_map.get(cur_id, currency_symbol),
                'state': d['state'],
                'risk_score': round(d['risk_score'], 1) if d.get('risk_score') else 0.0,
                'risk_level': d['risk_level'] or 'low',
                'approval_status': d['approval_status'] or 'none'
            })

        return {
            'kpis': {
                'my_quotations': my_quotations_count,
                'pending_approvals': pending_approval_count,
                'high_risk': high_risk_count,
                'orders': orders_count,
                'currency_symbol': currency_symbol,
                'currency_position': currency_position
            },
            'my_deals': my_deals
        }

    @api.model
    def get_sales_manager_data(self):
        if not (self.env.user.has_group('dealflow360.group_dealflow_manager') or self.env.user.has_group('base.group_system')):
            raise AccessError("Access denied: You do not have permissions to access the Sales Manager dashboard.")

        company_ids = self.env.companies.ids
        company_currency = self.env.company.currency_id
        currency_symbol = company_currency.symbol or ''
        currency_position = company_currency.position or 'before'

        domain_active_deals = [('state', 'in', ['draft', 'sent', 'sale']), ('company_id', 'in', company_ids)]

        # 1. KPIs
        team_active_deals = self.env['sale.order'].search_count(domain_active_deals)
        active_deals = self.env['sale.order'].search(domain_active_deals)
        pipeline_value = sum(active_deals.mapped('amount_total'))

        # High Risk Deals (MUST strictly use risk_level == 'high')
        high_risk_count = self.env['sale.order'].search_count(
            domain_active_deals + [('risk_level', '=', 'high')]
        )

        # Pending Approvals
        pending_approval_count = self.env['dealflow.approval'].search_count([
            ('status', '=', 'pending'),
            ('company_id', 'in', company_ids)
        ])

        # Approved & Rejected counts
        approved_count = self.env['dealflow.approval'].search_count([
            ('status', '=', 'approved'),
            ('company_id', 'in', company_ids)
        ])
        rejected_count = self.env['dealflow.approval'].search_count([
            ('status', '=', 'rejected'),
            ('company_id', 'in', company_ids)
        ])

        # 2. Detailed Pending Approvals List for Sales Manager
        pending_approval_records = self.env['dealflow.approval'].search([
            ('status', '=', 'pending'),
            ('company_id', 'in', company_ids)
        ], order='id desc')

        user_groups = self.env.user.all_group_ids
        pending_approvals = []
        for app in pending_approval_records:
            current_step = False
            current_step_id = False
            required_group_name = False
            is_eligible = False

            sorted_steps = app.step_ids.sorted(key=lambda s: (s.sequence, s.id))
            for step in sorted_steps:
                if step.status == 'pending':
                    current_step = step.rule_id.name
                    current_step_id = step.id
                    required_group_name = step.group_id.name
                    is_eligible = step._is_user_eligible(self.env.user)
                    break

            cur_symbol = app.order_id.currency_id.symbol if (app.order_id and app.order_id.currency_id) else currency_symbol

            pending_approvals.append({
                'id': app.id,
                'order_id': app.order_id.id if app.order_id else False,
                'order_name': app.order_id.name if app.order_id else 'Unknown',
                'customer': app.order_id.partner_id.name if (app.order_id and app.order_id.partner_id) else 'Unknown',
                'amount_total': app.order_id.amount_total if app.order_id else 0.0,
                'currency_symbol': cur_symbol,
                'risk_score': round(app.order_id.risk_score, 1) if app.order_id else 0.0,
                'risk_level': app.order_id.risk_level if app.order_id else 'low',
                'status': app.status,
                'current_step_id': current_step_id,
                'current_step': current_step or 'Pending Review',
                'required_group': required_group_name or 'N/A',
                'is_eligible': is_eligible,
                'requester': app.create_uid.name if app.create_uid else 'System',
                'create_date': app.create_date.strftime('%Y-%m-%d %H:%M') if app.create_date else ''
            })

        # 3. High Risk Deals List (strictly risk_level == 'high')
        high_risk_records = self.env['sale.order'].search_read(
            domain_active_deals + [('risk_level', '=', 'high')],
            ['name', 'partner_id', 'user_id', 'amount_total', 'risk_score', 'approval_status', 'currency_id'],
            limit=10,
            order='risk_score desc, id desc'
        )

        high_risk_deals = []
        for d in high_risk_records:
            high_risk_deals.append({
                'id': d['id'],
                'name': d['name'],
                'customer': d['partner_id'][1] if d.get('partner_id') else 'Unknown',
                'salesperson': d['user_id'][1] if d.get('user_id') else 'Unassigned',
                'amount_total': d['amount_total'],
                'risk_score': round(d['risk_score'], 1) if d.get('risk_score') else 0.0,
                'approval_status': d['approval_status'] or 'none'
            })

        return {
            'kpis': {
                'team_active_deals': team_active_deals,
                'pipeline_value': pipeline_value,
                'high_risk_deals': high_risk_count,
                'pending_approvals': pending_approval_count,
                'approved_approvals': approved_count,
                'rejected_approvals': rejected_count,
                'currency_symbol': currency_symbol,
                'currency_position': currency_position
            },
            'pending_approvals': pending_approvals,
            'high_risk_deals': high_risk_deals
        }
