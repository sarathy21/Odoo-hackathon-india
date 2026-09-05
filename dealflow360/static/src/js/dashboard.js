/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class DealFlow360Dashboard extends Component {
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        
        this.state = useState({
            metrics: {
                activeDeals: 0,
                pipelineValue: 0,
                pendingApprovals: 0,
                atRiskDeals: 0
            },
            dealHealth: {
                healthy: 0,
                warning: 0,
                atRisk: 0,
                critical: 0
            },
            attentionRequired: [],
            approvals: [],
            discounts: [],
            fulfillment: {
                ready: 0,
                allocationPending: 0,
                stockShortage: 0,
                delayed: 0
            },
            recentActivity: []
        });

        onWillStart(async () => {
            await this.loadMockData();
        });
    }

    async loadMockData() {
        // In a real scenario, this would use this.orm.call() to fetch data from the backend.
        // For now, we populate it with mock data to build the UI structure.
        
        this.state.metrics = {
            activeDeals: 142,
            pipelineValue: "₹42,50,000",
            pendingApprovals: 12,
            atRiskDeals: 4
        };

        this.state.dealHealth = {
            healthy: 18,
            warning: 7,
            atRisk: 4,
            critical: 2
        };

        this.state.attentionRequired = [
            { id: 1, record: "DF-003", customer: "Acme Corp", issue: "Discount exceeds allowance by 5%", severity: "High", status: "Action Required" },
            { id: 2, record: "DF-012", customer: "Globex", issue: "Approval pending for 3 days", severity: "Medium", status: "Waiting" },
            { id: 3, record: "DF-045", customer: "Initech", issue: "Margin below 20% threshold", severity: "High", status: "Review" }
        ];

        this.state.approvals = [
            { id: 1, quotation: "Q-00042", customer: "ABC Corp", risk: "High", waiting: "2 days" },
            { id: 2, quotation: "Q-00051", customer: "XYZ Ltd", risk: "Medium", waiting: "8 hours" }
        ];

        this.state.discounts = [
            { id: 1, deal: "DF-001", category: "Hardware", allowed: "15%", requested: "12%", risk: "Low" },
            { id: 2, deal: "DF-002", category: "Services", allowed: "10%", requested: "18%", risk: "High" }
        ];

        this.state.fulfillment = {
            ready: 24,
            allocationPending: 5,
            stockShortage: 3,
            delayed: 2
        };

        this.state.recentActivity = [
            { id: 1, type: "approval", message: "Discount approval requested for DF-003", user: "Sales Manager", time: "10 minutes ago" },
            { id: 2, type: "quote", message: "Quotation Q-00052 created", user: "Sales Rep", time: "1 hour ago" },
            { id: 3, type: "deal", message: "Deal DF-001 approved", user: "Sales Director", time: "3 hours ago" }
        ];
    }

    openDeal(id) {
        // Placeholder for navigating to a specific deal
        console.log("Opening deal", id);
        // this.action.doAction(...)
    }
}

DealFlow360Dashboard.template = "dealflow360.Dashboard";
DealFlow360Dashboard.components = {};

registry.category("actions").add("dealflow360.dashboard_action", DealFlow360Dashboard);
