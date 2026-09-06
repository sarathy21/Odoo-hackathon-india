import random
from datetime import datetime

def patch_demo_data(env):
    print("=========================================")
    print("Patching DealFlow360 Demo Data (Approvals & Negotiations)")
    print("=========================================")

    rule_model = env['dealflow.approval.rule']
    admin_user = env.ref('base.user_admin')
    so_model = env['sale.order']
    
    # 1. Ensure Approval Rules Exist
    print("Creating Approval Rules...")
    if rule_model.search_count([]) == 0:
        sales_mgr_group = env.ref('dealflow360.group_dealflow_manager')
        rule_model.create([
            {
                'name': 'Medium Risk Review',
                'min_risk_score': 20.01,
                'max_risk_score': 60.0,
                'group_id': sales_mgr_group.id,
                'sequence': 10
            },
            {
                'name': 'High Risk Review - Level 1',
                'min_risk_score': 60.01,
                'max_risk_score': 100.0,
                'group_id': sales_mgr_group.id,
                'sequence': 20
            }
        ])
        print("Created 2 Approval Rules.")
        
    # 2. Force Create Approvals
    print("Creating Approvals...")
    
    draft_deals = so_model.search([('state', 'in', ['draft', 'sent'])], limit=15)
    for so in draft_deals:
        # Create approval request directly
        appr = env['dealflow.approval'].create({
            'order_id': so.id,
            'status': 'pending'
        })
        # Add a step
        rule = rule_model.search([], limit=1)
        step = env['dealflow.approval.step'].create({
            'approval_id': appr.id,
            'rule_id': rule.id
        })
        so.write({
            'approval_status': 'pending',
            'dealflow_approved_risk_score': 75.0,
            'dealflow_approved_revision': so.dealflow_commercial_revision
        })
        rnd = random.random()
        if rnd < 0.3:
            appr.sudo().write({'status': 'approved'})
            step.sudo().write({'status': 'approved', 'approver_id': admin_user.id})
            so.write({'approval_status': 'approved'})
        elif rnd < 0.5:
            appr.sudo().write({'status': 'rejected'})
            step.sudo().write({'status': 'rejected', 'approver_id': admin_user.id})
            so.write({'approval_status': 'rejected'})
                    
    # 3. Create More Negotiations
    print("Creating Negotiations...")
    neg_model = env['dealflow.negotiation']
    neg_line_model = env['dealflow.negotiation.line']
    
    # We want ~25 total. We have 4. Find deals without negotiations.
    current_negs = neg_model.search_count([])
    needed = max(0, 25 - current_negs)
    
    if needed > 0:
        deals_for_neg = so_model.search([('state', 'in', ['draft', 'sent'])])
        deals_filtered = []
        for d in deals_for_neg:
            if not neg_model.search_count([('order_id', '=', d.id)]) and any(not l.display_type for l in d.order_line):
                deals_filtered.append(d)
                
        random.shuffle(deals_filtered)
        deals_to_process = deals_filtered[:needed]
        
        neg_states = ['submitted', 'under_review', 'accepted', 'rejected', 'stale']
        
        for deal in deals_to_process:
            n_state = random.choice(neg_states)
            
            neg = neg_model.create({
                'order_id': deal.id,
                'reason': f"Requesting better terms for our upcoming rollout.",
            })
            
            for line in deal.order_line:
                if not line.display_type:
                    req_disc = min(100.0, line.discount + 5.0)
                    neg_line_model.create({
                        'negotiation_id': neg.id,
                        'order_line_id': line.id,
                        'requested_quantity': line.product_uom_qty,
                        'requested_unit_price': line.price_unit,
                        'requested_discount': req_disc
                    })
                    
            neg.action_submit()
            
            if n_state == 'under_review':
                neg.sudo().write({'state': 'under_review'})
            elif n_state == 'accepted':
                neg.sudo().action_accept()
            elif n_state == 'rejected':
                neg.sudo().action_reject()
            elif n_state == 'stale':
                if deal.order_line:
                    line = [l for l in deal.order_line if not l.display_type][0]
                    line.product_uom_qty += 1

    print("=========================================")
    print("Patch Complete!")
    print(f"Total Approvals: {env['dealflow.approval'].search_count([])}")
    print(f"Total Negotiations: {neg_model.search_count([])}")
    print("=========================================")

if __name__ == '__main__':
    patch_demo_data(env)
