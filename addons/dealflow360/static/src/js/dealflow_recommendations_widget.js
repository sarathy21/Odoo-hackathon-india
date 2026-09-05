/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class DealflowRecommendationsWidget extends Component {
    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
    }

    get recommendations() {
        const data = this.props.record.data[this.props.name];
        if (!data) {
            return [];
        }
        if (typeof data === "string") {
            try {
                return JSON.parse(data) || [];
            } catch (e) {
                console.error("DealflowRecommendationsWidget: Invalid recommendation data", e);
                return [];
            }
        }
        return data; // It's already parsed (fields.Json)
    }

    async onAddProduct(productId) {
        if (!this.props.record.resId) {
            return; // Needs to be a saved record
        }
        
        try {
            const result = await this.orm.call(
                "sale.order",
                "action_add_dealflow_recommendation",
                [[this.props.record.resId], productId],
                {}
            );
            
            if (result && (result.tag === 'reload' || result.tag === 'display_notification')) {
                this.action.doAction(result);
            }
        } catch (error) {
            console.error(error);
        }
    }
}

DealflowRecommendationsWidget.template = "dealflow360.RecommendationsWidget";

export const dealflowRecommendationsWidget = {
    component: DealflowRecommendationsWidget,
    supportedTypes: ["json", "text", "char"],
};

registry.category("fields").add("dealflow_recommendations", dealflowRecommendationsWidget);
