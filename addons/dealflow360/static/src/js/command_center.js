/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DealFlowCommandCenter extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        this.state = useState({
            data: {
                kpis: {
                    active_deals: 0,
                    pipeline_value: 0.0,
                    high_risk_deals: 0,
                    pending_approvals: 0,
                    currency_symbol: "",
                    currency_position: "before"
                },
                attention_deals: [],
                pending_approvals_list: [],
                recommendations_summary: { active_rules: 0, rules_list: [] }
            },
            isLoading: true,
            hasError: false,
            errorMessage: ""
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.isLoading = true;
        this.state.hasError = false;
        try {
            const data = await this.orm.call("dealflow.dashboard", "get_dashboard_data", []);
            if (data) {
                this.state.data = data;
            }
        } catch (error) {
            console.error("Failed to load DealFlow360 Command Center data:", error);
            this.state.hasError = true;
            this.state.errorMessage = "Unable to load DealFlow360 dashboard.";
        } finally {
            this.state.isLoading = false;
        }
    }

    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        }).format(value || 0);
    }

    // Navigation Actions
    openSaleOrders(filter) {
        let domain = [['state', 'in', ['draft', 'sent', 'sale']]];
        if (filter === 'high_risk') {
            domain.push(['risk_level', '=', 'high']);
        }
        
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: filter === 'high_risk' ? 'High Risk Deals' : 'Active Deals',
            res_model: 'sale.order',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
        });
    }

    openPendingApprovals() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Pending Approvals',
            res_model: 'dealflow.approval',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['status', '=', 'pending']],
        });
    }

    openCustomerNegotiations() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Customer Negotiations',
            res_model: 'dealflow.negotiation',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['state', 'in', ['submitted', 'under_review']]],
        });
    }

    openRecommendationRules() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Recommendation Rules',
            res_model: 'dealflow.product.recommendation',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['active', '=', true]],
        });
    }

    openSaleOrder(orderId) {
        if (!orderId) return;
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'sale.order',
            res_id: orderId,
            views: [[false, 'form']],
        });
    }

    openApproval(approvalId) {
        if (!approvalId) return;
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'dealflow.approval',
            res_id: approvalId,
            views: [[false, 'form']],
        });
    }
}

DealFlowCommandCenter.template = "dealflow360.CommandCenter";

// Register the component as an action in Odoo's action registry
registry.category("actions").add("dealflow_command_center", DealFlowCommandCenter);

