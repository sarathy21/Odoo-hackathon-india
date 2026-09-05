/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

export class DealFlowSalesRepWorkspace extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        this.state = useState({
            data: {
                kpis: {
                    my_quotations: 0,
                    pending_approvals: 0,
                    high_risk: 0,
                    orders: 0,
                    currency_symbol: "",
                    currency_position: "before"
                },
                my_deals: []
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
            const data = await this.orm.call("dealflow.dashboard", "get_sales_rep_workspace_data", []);
            if (data) {
                this.state.data = data;
            }
        } catch (error) {
            console.error("Failed to load Sales Representative workspace data:", error);
            this.state.hasError = true;
            this.state.errorMessage = "Unable to load Sales Representative workspace.";
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
    createQuotation() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'sale.order',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'current',
            context: {
                default_user_id: user.userId
            }
        });
    }

    openDeal(orderId) {
        if (!orderId) return;
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'sale.order',
            res_id: orderId,
            views: [[false, 'form']],
            target: 'current'
        });
    }

    openFilteredDeals(filterType) {
        let domain = [['user_id', '=', user.userId]];
        
        if (filterType === 'draft') {
            domain.push(['state', 'in', ['draft', 'sent']]);
        } else if (filterType === 'sale') {
            domain.push(['state', '=', 'sale']);
        } else if (filterType === 'high_risk') {
            domain.push(['state', 'in', ['draft', 'sent']]);
            domain.push(['risk_level', '=', 'high']);
        }
        
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: filterType === 'high_risk' ? 'High Risk Deals' : 'My Deals',
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
            domain: [['status', '=', 'pending'], ['order_id.user_id', '=', user.userId]],
        });
    }
}

DealFlowSalesRepWorkspace.template = "dealflow360.SalesRepWorkspace";

// Register the component as an action in Odoo's action registry
registry.category("actions").add("dealflow_sales_rep_workspace", DealFlowSalesRepWorkspace);
