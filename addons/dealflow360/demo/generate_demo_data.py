import random
from datetime import datetime, timedelta

def generate_demo_data(env):
    print("=========================================")
    print("Starting DealFlow360 Demo Data Generation")
    print("=========================================")

    # 1. Tiers
    print("Ensuring Customer Tiers...")
    tier_model = env['dealflow.customer.tier']
    tiers = {
        'Gold': tier_model.search([('name', '=', 'Gold')], limit=1) or tier_model.create({'name': 'Gold'}),
        'Silver': tier_model.search([('name', '=', 'Silver')], limit=1) or tier_model.create({'name': 'Silver'}),
        'Bronze': tier_model.search([('name', '=', 'Bronze')], limit=1) or tier_model.create({'name': 'Bronze'})
    }

    # 2. Customers
    print("Creating Customers...")
    partner_model = env['res.partner']
    customer_names = [
        "ABC Technologies", "Vertex Systems", "BluePeak Solutions", "Nova Industrial Works", 
        "GlobalEdge Enterprises", "TechNova India", "Apex Manufacturing", "Prime Logistics", 
        "Orbit Systems", "NextGen Digital", "Pinnacle Corp", "Synergy Global", "Quantum Computing Ltd",
        "Titan Industries", "Eagle Eye Solutions", "Orion Tech", "Genesis Group", "Omega Systems",
        "Vanguard Logic", "Zenith Corporation", "Horizon Networks", "Silverline Technologies",
        "Meridian Partners", "Starlight Data", "Equinox Trading", "Crestview Holdings", "Summit IT",
        "Canyon Electronics", "Boreal Softworks", "Paramount Web", "Velocity Motors", "Dynamic Logistics",
        "Frontier Robotics", "Alpha Precision", "Beta Innovations", "Gamma Solutions", "Delta Networks",
        "Epsilon Systems", "Zeta Tech", "Theta Group"
    ]
    
    customers = []
    for i, name in enumerate(customer_names):
        existing = partner_model.search([('name', '=', name)], limit=1)
        if not existing:
            # Distribute tiers: Gold (10), Silver (15), Bronze (15)
            tier_name = 'Gold' if i < 10 else ('Silver' if i < 25 else 'Bronze')
            existing = partner_model.create({
                'name': name,
                'is_company': True,
                'email': f"contact@{name.lower().replace(' ', '')}.demo",
                'phone': f"+91 98000 {10000 + i}",
                'dealflow_tier_id': tiers[tier_name].id
            })
        customers.append(existing)

    # 3. Product Categories
    print("Ensuring Product Categories...")
    category_model = env['product.category']
    categories = {}
    for cat_name in ['Hardware', 'Software', 'Services', 'Support', 'Networking', 'Infrastructure']:
        cat = category_model.search([('name', '=', cat_name)], limit=1)
        if not cat:
            cat = category_model.create({'name': cat_name})
        categories[cat_name] = cat

    # 4. Products
    print("Creating Products...")
    product_model = env['product.product']
    products_data = [
        ("Enterprise Laptop", 1500.0, 1200.0, "consu", "Hardware"),
        ("Business Monitor", 300.0, 200.0, "consu", "Hardware"),
        ("Workstation Pro", 2500.0, 2000.0, "consu", "Hardware"),
        ("Network Switch", 800.0, 600.0, "consu", "Networking"),
        ("Enterprise Router", 1200.0, 900.0, "consu", "Networking"),
        ("Server Rack Unit", 5000.0, 4000.0, "consu", "Infrastructure"),
        ("UPS Battery Backup", 450.0, 350.0, "consu", "Infrastructure"),
        ("Video Conferencing Kit", 1800.0, 1400.0, "consu", "Hardware"),
        ("IP Phone Set", 250.0, 180.0, "consu", "Hardware"),
        ("Biometric Scanner", 400.0, 300.0, "consu", "Hardware"),
        ("CRM License (Annual)", 1200.0, 0.0, "service", "Software"),
        ("ERP License (Annual)", 5000.0, 0.0, "service", "Software"),
        ("Security Suite (Annual)", 800.0, 0.0, "service", "Software"),
        ("Cloud Backup (1TB)", 300.0, 0.0, "service", "Software"),
        ("HRMS License", 2000.0, 0.0, "service", "Software"),
        ("Analytics Dashboard", 1500.0, 0.0, "service", "Software"),
        ("Email Security Gateway", 600.0, 0.0, "service", "Software"),
        ("Database Enterprise License", 10000.0, 0.0, "service", "Software"),
        ("Project Management Tool", 400.0, 0.0, "service", "Software"),
        ("Helpdesk Software", 750.0, 0.0, "service", "Software"),
        ("Implementation Service", 3000.0, 0.0, "service", "Services"),
        ("Premium Support (Monthly)", 500.0, 0.0, "service", "Support"),
        ("Annual Support Contract", 5000.0, 0.0, "service", "Support"),
        ("Data Migration Service", 2000.0, 0.0, "service", "Services"),
        ("Training Package (5 Days)", 2500.0, 0.0, "service", "Services"),
        ("Network Architecture Consulting", 4000.0, 0.0, "service", "Services"),
        ("Security Audit", 3500.0, 0.0, "service", "Services"),
        ("Custom Development (Per Hour)", 150.0, 0.0, "service", "Services"),
        ("Cloud Migration Strategy", 2500.0, 0.0, "service", "Services"),
        ("System Integration", 3000.0, 0.0, "service", "Services"),
    ]
    
    products = {}
    for name, price, cost, ptype, cat_name in products_data:
        existing = product_model.search([('name', '=', name)], limit=1)
        if not existing:
            existing = product_model.create({
                'name': name,
                'list_price': price,
                'standard_price': cost,
                'type': 'consu', # base type
                'is_storable': True if ptype == 'consu' else False,
                'categ_id': categories[cat_name].id,
            })
        products[name] = existing

    # Add some stock to consu (stockable) products to support fulfillment demo
    print("Initializing Stock...")
    warehouse = env['stock.warehouse'].search([], limit=1)
    if warehouse:
        quant_model = env['stock.quant']
        for p in products.values():
            if getattr(p, 'is_storable', False) or p.type == 'consu':
                existing_quant = quant_model.search([('product_id', '=', p.id), ('location_id', '=', warehouse.lot_stock_id.id)], limit=1)
                if not existing_quant or existing_quant.quantity < 100:
                    try:
                        quant_model.with_context(inventory_mode=True).create({
                            'product_id': p.id,
                            'location_id': warehouse.lot_stock_id.id,
                            'inventory_quantity': 500,
                        }).action_apply_inventory()
                    except Exception as e:
                        print(f"Skipping quant for {p.name}: {e}")

    # 5. Discount Rules
    print("Creating Discount Rules...")
    dr_model = env['dealflow.discount.rule']
    dr_data = [
        ('Gold', 'Hardware', 15.0), ('Gold', 'Software', 12.0), ('Gold', 'Services', 10.0), ('Gold', 'Support', 15.0),
        ('Silver', 'Hardware', 10.0), ('Silver', 'Software', 8.0), ('Silver', 'Services', 8.0), ('Silver', 'Support', 10.0),
        ('Bronze', 'Hardware', 5.0), ('Bronze', 'Software', 5.0), ('Bronze', 'Services', 5.0), ('Bronze', 'Support', 5.0)
    ]
    for tier_name, cat_name, max_disc in dr_data:
        existing = dr_model.search([
            ('tier_id', '=', tiers[tier_name].id),
            ('category_id', '=', categories[cat_name].id)
        ], limit=1)
        if not existing:
            dr_model.create({
                'name': f"{tier_name} - {cat_name} Rule",
                'tier_id': tiers[tier_name].id,
                'category_id': categories[cat_name].id,
                'max_discount': max_disc
            })

    # 6. Recommendation Rules
    print("Creating Recommendation Rules...")
    rec_model = env['dealflow.product.recommendation']
    rec_data = [
        ("Enterprise Laptop", "Premium Support (Monthly)", "upsell", "Premium Support ensures 24/7 coverage for critical hardware."),
        ("Enterprise Laptop", "Workstation Pro", "upsell", "Consider upgrading to Workstation Pro for heavy workloads."),
        ("Business Monitor", "Premium Support (Monthly)", "cross_sell", "Add support for peace of mind."),
        ("CRM License (Annual)", "Implementation Service", "cross_sell", "Implementation service ensures a smooth CRM rollout."),
        ("ERP License (Annual)", "Data Migration Service", "cross_sell", "Safely migrate your existing data to the new ERP."),
        ("ERP License (Annual)", "Training Package (5 Days)", "cross_sell", "Train your staff to maximize ROI."),
        ("Server Rack Unit", "UPS Battery Backup", "cross_sell", "Protect your infrastructure from power surges."),
        ("Enterprise Router", "Network Architecture Consulting", "cross_sell", "Optimize your network topology with our experts."),
        ("Cloud Backup (1TB)", "Security Suite (Annual)", "cross_sell", "Enhance your backup security with our premium suite."),
        ("Project Management Tool", "Analytics Dashboard", "upsell", "Get deeper insights into your projects with the Analytics Dashboard.")
    ]
    for src, tgt, rtype, reason in rec_data:
        existing = rec_model.search([
            ('source_product_id', '=', products[src].id),
            ('recommended_product_id', '=', products[tgt].id)
        ], limit=1)
        if not existing:
            rec_model.create({
                'source_product_id': products[src].id,
                'recommended_product_id': products[tgt].id,
                'recommendation_type': rtype,
                'reason': reason,
                'active': True
            })

    # Find Sales Reps
    sales_reps = env['res.users'].search([('share', '=', False)])
    if not sales_reps:
        sales_reps = env.user
        
    admin_user = env.ref('base.user_admin')

    # 7 & 8. Quotations and Scenarios
    print("Creating Quotations (100 total)...")
    so_model = env['sale.order']
    
    # We will spread creation over the last 90 days
    now = datetime.now()
    
    quotations = []
    
    # Helper to create SO
    def create_scenario_so(scenario, risk_profile, state, with_negotiation=False):
        cust = random.choice(customers)
        rep = random.choice(sales_reps)
        days_ago = random.randint(1, 90)
        so_date = now - timedelta(days=days_ago)
        
        # Create SO
        so = so_model.create({
            'partner_id': cust.id,
            'user_id': rep.id,
            'date_order': so_date,
        })
        
        # Determine allowed discount for customer's tier
        # Pick 2-4 products
        prods = random.sample(list(products.values()), random.randint(2, 4))
        for p in prods:
            qty = random.randint(1, 20)
            
            # Figure out max discount allowed
            dr = dr_model.search([
                ('tier_id', '=', cust.dealflow_tier_id.id),
                ('category_id', '=', p.categ_id.id)
            ], limit=1)
            allowed = dr.max_discount if dr else 0.0
            
            if risk_profile == 'low':
                # Discount below or equal to allowed
                disc = random.uniform(0, allowed) if allowed > 0 else 0.0
            elif risk_profile == 'medium':
                # Discount slightly above allowed (trigger medium risk)
                disc = allowed + random.uniform(1, 5)
            else: # high
                # Discount significantly above allowed (trigger high risk & approval)
                disc = allowed + random.uniform(10, 25)
                
            env['sale.order.line'].create({
                'order_id': so.id,
                'product_id': p.id,
                'product_uom_qty': qty,
                'price_unit': p.list_price,
                'discount': disc
            })
            
        # Recompute Risk
        so._compute_dealflow_risk_score()
        
        # Update State
        if state in ('sent', 'sale'):
            so.action_quotation_send() # just to move state to sent usually
            if state == 'sale':
                # For high risk, it needs approval before confirmation
                if so.approval_required:
                    # Request approval
                    so.action_request_approval()
                    # Manager approves
                    appr = env['dealflow.approval'].search([('order_id', '=', so.id), ('status', '=', 'pending')], limit=1)
                    if appr:
                        appr.with_user(admin_user).action_approve()
                
                # If there's a negotiation, don't confirm yet
                if not with_negotiation:
                    so.action_confirm()
                    
        # Request approval naturally if high risk and not sale (if sale, we handled it above)
        if risk_profile == 'high' and state != 'sale' and so.approval_required and so.approval_status == 'none':
            so.action_request_approval()
            # Randomly approve or reject some
            appr = env['dealflow.approval'].search([('order_id', '=', so.id), ('status', '=', 'pending')], limit=1)
            if appr:
                rnd = random.random()
                if rnd < 0.3:
                    appr.with_user(admin_user).action_approve()
                elif rnd < 0.5:
                    appr.with_user(admin_user).action_reject()
                    
        # Update dates via SQL since ORM sometimes overrides them
        env.cr.execute("UPDATE sale_order SET create_date=%s, date_order=%s WHERE id=%s", (so_date, so_date, so.id))
        
        return so

    # Distribution
    # Low Risk: ~40
    # Medium Risk: ~35
    # High Risk: ~25
    
    print("Generating Low Risk Scenarios (No Approval)...")
    for _ in range(40):
        create_scenario_so('low', 'low', random.choice(['draft', 'sent', 'sale']))
        
    print("Generating Medium Risk Scenarios (Some Approval)...")
    for _ in range(35):
        create_scenario_so('medium', 'medium', random.choice(['draft', 'sent', 'sale']))
        
    print("Generating High Risk Scenarios (Requires Approval)...")
    for _ in range(25):
        create_scenario_so('high', 'high', random.choice(['draft', 'sent', 'sale']))

    # 11. Negotiations
    print("Creating Negotiations...")
    neg_model = env['dealflow.negotiation']
    neg_line_model = env['dealflow.negotiation.line']
    
    # Pick some 'sent' deals
    sent_deals = so_model.search([('state', '=', 'sent')], limit=25)
    
    neg_states = ['submitted'] * 7 + ['under_review'] * 5 + ['accepted'] * 6 + ['rejected'] * 4 + ['stale'] * 3
    random.shuffle(neg_states)
    
    for i, deal in enumerate(sent_deals):
        if i >= len(neg_states):
            break
        n_state = neg_states[i]
        
        # Create negotiation
        neg = neg_model.create({
            'order_id': deal.id,
            'customer_reason': f"Requesting better terms for our upcoming Q{random.randint(1,4)} rollout.",
        })
        
        # Create neg lines
        for line in deal.order_line:
            # Request 5% more discount
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
            neg.action_review()
        elif n_state == 'accepted':
            neg.action_review()
            neg.with_user(admin_user).action_accept()
        elif n_state == 'rejected':
            neg.action_review()
            neg.with_user(admin_user).action_reject()
        elif n_state == 'stale':
            # simulate stale by updating quotation line
            if deal.order_line:
                deal.order_line[0].product_uom_qty += 1

    # 13. Fulfillment Scenarios
    print("Creating Fulfillment Scenarios...")
    confirmed_deals = so_model.search([('state', '=', 'sale')], limit=20)
    for deal in confirmed_deals:
        # The fulfillment plan might have been created automatically if standard flow does it.
        plan = env['dealflow.fulfillment.plan'].search([('order_id', '=', deal.id)], limit=1)
        if not plan:
            plan = env['dealflow.fulfillment.plan'].create({'order_id': deal.id})
            
        # Allocate some stock
        plan.action_generate_fulfillment_plan()
        
    # 15. Deal Health and Anomalies
    print("Evaluating Deal Health & Anomalies...")
    # Run the scheduled actions manually for all generated deals
    all_deals = so_model.search([])
    for deal in all_deals:
        # If Deal Health engine has a manual compute:
        if hasattr(deal, '_compute_health_score'):
            deal._compute_health_score()
            
    anomaly_engine = env.get('dealflow.anomaly')
    if anomaly_engine and hasattr(anomaly_engine, 'action_run_anomaly_detection'):
        anomaly_engine.action_run_anomaly_detection()
        
    print("=========================================")
    print("Demo Data Generation Complete!")
    print(f"Total Customers: {partner_model.search_count([('dealflow_tier_id', '!=', False)])}")
    print(f"Total Quotations: {so_model.search_count([])}")
    print(f"Total Negotiations: {neg_model.search_count([])}")
    print(f"Total Approvals: {env['dealflow.approval'].search_count([])}")
    print(f"Total Health Records: {env['dealflow.deal.health'].search_count([])}")
    print("=========================================")

# If run directly via shell
if __name__ == '__main__':
    generate_demo_data(env)
