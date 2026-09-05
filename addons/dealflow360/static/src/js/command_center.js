/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

export class DealFlowCommandCenter extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        
        this.state = useState({
            user: {
                user_id: user.userId,
                user_name: user.name || "Administrator",
                user_email: "",
                role_code: "admin",
                role_name: "DealFlow Manager",
                can_manage: true,
                is_admin: user.isAdmin,
            },
            isUserMenuOpen: false,
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
            // 1. Identify current user & role
            const userInfo = await this.orm.call("dealflow.dashboard", "get_current_user_info", []);
            if (userInfo) {
                this.state.user = userInfo;
                // Guard: If not manager/admin, route directly to their Sales Representative Workspace
                if (!userInfo.can_manage && !userInfo.is_admin) {
                    this.action.doAction("dealflow360.action_dealflow_sales_rep_workspace", { clear_breadcrumbs: true });
                    return;
                }
            }

            // 2. Fetch dashboard data
            const data = await this.orm.call("dealflow.dashboard", "get_dashboard_data", []);
            if (data) {
                this.state.data = data;
            }
        } catch (error) {
            console.error("Failed to load DealFlow360 Command Center data:", error);
            this.state.hasError = true;
            this.state.errorMessage = error.data?.message || "Unable to load DealFlow360 dashboard.";
        } finally {
            this.state.isLoading = false;
        }
    }

    toggleUserDropdown() {
        this.state.isUserMenuOpen = !this.state.isUserMenuOpen;
    }

    onLogout() {
        window.location.href = "/web/session/logout";
    }

    openSalesWorkspace() {
        this.state.isUserMenuOpen = false;
        this.action.doAction("dealflow360.action_dealflow_sales_rep_workspace");
    }

    openConfigDiscountRules() {
        this.state.isUserMenuOpen = false;
        this.action.doAction("dealflow360.action_dealflow_discount_rule");
    }

    openConfigCustomerTiers() {
        this.state.isUserMenuOpen = false;
        this.action.doAction("dealflow360.action_dealflow_customer_tier");
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

