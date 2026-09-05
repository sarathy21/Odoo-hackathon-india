document.addEventListener('DOMContentLoaded', () => {
    
    // Navigation logic
    const navLinks = document.querySelectorAll('#sidebar ul.components li a');
    const sections = document.querySelectorAll('.view-section');

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            // Update active state in sidebar
            document.querySelectorAll('#sidebar ul li').forEach(li => li.classList.remove('active'));
            link.parentElement.classList.add('active');
            
            // Show corresponding section
            const targetId = link.getAttribute('href').substring(1);
            sections.forEach(sec => sec.classList.remove('active'));
            document.getElementById(targetId).classList.add('active');
            
            // Render content for that section if needed
            renderSection(targetId);
        });
    });

    // Helper to render content based on section
    function renderSection(sectionId) {
        switch(sectionId) {
            case 'customers':
                renderCustomers();
                break;
            case 'deals':
                renderDeals();
                break;
            case 'deal-workspace':
                renderDealWorkspace();
                break;
            case 'fulfillment':
                renderFulfillment();
                break;
            case 'allocation-workspace':
                renderAllocationWorkspace();
                break;
            case 'deal-health':
                renderDealHealth();
                break;
            case 'configuration':
                // Static, no dynamic render needed yet
                break;
        }
    }

    // Shared: Notification Helper
    function showNotification(message, type = 'success') {
        const toastContainer = document.getElementById('toast-container');
        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-white bg-${type} border-0 mb-2`;
        toastEl.setAttribute('role', 'alert');
        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" onclick="this.parentElement.parentElement.remove()"></button>
            </div>
        `;
        toastContainer.appendChild(toastEl);
        setTimeout(() => toastEl.remove(), 3000);
    }

    // Shared: Risk Indicator
    function getRiskBadge(level) {
        let badgeClass = 'bg-secondary';
        if (level === 'LOW') badgeClass = 'dealflow-bg-success';
        if (level === 'MEDIUM') badgeClass = 'dealflow-bg-warning';
        if (level === 'HIGH') badgeClass = 'dealflow-bg-danger';
        if (level === 'CRITICAL') badgeClass = 'dealflow-bg-dark';
        return `<span class="badge ${badgeClass}">${level}</span>`;
    }

    // --- RENDER FUNCTIONS ---

    function renderCustomers() {
        const tbody = document.querySelector('#customers-table tbody');
        tbody.innerHTML = '';
        MOCK_DATA.customers.forEach(c => {
            tbody.innerHTML += `
                <tr>
                    <td class="fw-bold">${c.name}</td>
                    <td>${c.tier}</td>
                    <td>${c.salesperson}</td>
                    <td>${c.email}</td>
                    <td>${c.phone}</td>
                    <td><span class="badge dealflow-bg-success">${c.status}</span></td>
                </tr>
            `;
        });
    }

    function renderDeals() {
        const tbody = document.querySelector('#deals-table tbody');
        tbody.innerHTML = '';
        MOCK_DATA.deals.forEach(d => {
            let statusBadge = 'dealflow-bg-info';
            if (d.status === 'Draft') statusBadge = 'bg-secondary';
            if (d.status === 'Sale Order') statusBadge = 'dealflow-bg-success';
            
            let approvalBadge = 'bg-secondary';
            if (d.approval === 'Pending') approvalBadge = 'dealflow-bg-warning';
            if (d.approval === 'Rejected') approvalBadge = 'dealflow-bg-danger';
            if (d.approval === 'Approved') approvalBadge = 'dealflow-bg-success';

            tbody.innerHTML += `
                <tr>
                    <td class="fw-bold"><a href="#deal-workspace" onclick="document.querySelector('a[href=\\'#deal-workspace\\']').click()">${d.name}</a></td>
                    <td>${d.customer}</td>
                    <td>${d.salesperson}</td>
                    <td>${d.amount}</td>
                    <td><span class="badge ${statusBadge}">${d.status}</span></td>
                    <td>${getRiskBadge(d.risk)}</td>
                    <td><span class="badge ${approvalBadge}">${d.approval}</span></td>
                </tr>
            `;
        });
    }

    function renderDealWorkspace() {
        const ws = MOCK_DATA.dealWorkspace;
        document.getElementById('dw-title').innerText = ws.dealName;
        document.getElementById('dw-customer').innerText = ws.customer;
        document.getElementById('dw-amount').innerText = ws.amount;
        
        // Cards
        document.getElementById('dw-req-discount').innerText = ws.discount.requested + '%';
        document.getElementById('dw-allow-discount').innerText = ws.discount.allowed + '%';
        document.getElementById('dw-discount-status').innerText = ws.discount.status;
        
        document.getElementById('dw-risk-score').innerText = ws.risk.score + '/100';
        document.getElementById('dw-risk-level').innerHTML = getRiskBadge(ws.risk.level);
        
        document.getElementById('dw-margin').innerText = ws.margin.percentage + '%';
        
        document.getElementById('dw-approval').innerText = ws.approval.status;

        // Lines
        const tbody = document.querySelector('#dw-lines-table tbody');
        tbody.innerHTML = '';
        ws.lines.forEach(l => {
            tbody.innerHTML += `
                <tr>
                    <td>${l.product}</td>
                    <td>${l.quantity}</td>
                    <td>${l.price}</td>
                    <td>${l.discount}%</td>
                </tr>
            `;
        });

        // Upsells
        const upsellContainer = document.getElementById('dw-upsells');
        upsellContainer.innerHTML = '';
        ws.upsells.forEach((u, idx) => {
            upsellContainer.innerHTML += `
                <div class="card mb-2" id="upsell-card-${idx}">
                    <div class="card-body d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1">${u.product} <span class="badge dealflow-bg-info ms-2">${u.type}</span></h6>
                            <p class="mb-0 small text-muted">Price: <strong>${u.price}</strong> | Margin: <span class="text-success">${u.marginImpact}</span> | Promo: ${u.promotion}</p>
                            <p class="mb-0 small fst-italic">Reason: ${u.reason}</p>
                        </div>
                        <div>
                            <button class="btn btn-sm btn-outline-primary" onclick="addUpsell(${idx}, '${u.product}')">Add to Quote</button>
                            <button class="btn btn-sm btn-outline-danger ms-2" onclick="dismissUpsell(${idx})">Dismiss</button>
                        </div>
                    </div>
                </div>
            `;
        });
    }

    // Export upsell functions to window so inline onclick works
    window.addUpsell = function(idx, product) {
        document.getElementById(`upsell-card-${idx}`).remove();
        showNotification(`${product} added to quote (Preview only)`, 'success');
    };
    
    window.dismissUpsell = function(idx) {
        document.getElementById(`upsell-card-${idx}`).remove();
    };

    function renderFulfillment() {
        const tbody = document.querySelector('#fulfillment-table tbody');
        tbody.innerHTML = '';
        MOCK_DATA.fulfillments.forEach(f => {
            let statusClass = f.status === 'Ready' ? 'dealflow-bg-success' : 'dealflow-bg-warning';
            tbody.innerHTML += `
                <tr>
                    <td class="fw-bold"><a href="#allocation-workspace" onclick="document.querySelector('a[href=\\'#allocation-workspace\\']').click()">${f.order}</a></td>
                    <td>${f.customer}</td>
                    <td>${f.date}</td>
                    <td><span class="badge ${statusClass}">${f.status}</span></td>
                </tr>
            `;
        });
    }

    function renderAllocationWorkspace() {
        const aw = MOCK_DATA.allocationWorkspace;
        document.getElementById('aw-order').innerText = aw.order;
        document.getElementById('aw-customer').innerText = aw.customer;
        
        const reqTbody = document.querySelector('#aw-required-table tbody');
        reqTbody.innerHTML = '';
        aw.requiredProducts.forEach(p => {
            reqTbody.innerHTML += `<tr><td>${p.product}</td><td>${p.required}</td></tr>`;
        });

        const whTbody = document.querySelector('#aw-warehouse-table tbody');
        whTbody.innerHTML = '';
        aw.warehouses.forEach(w => {
            whTbody.innerHTML += `<tr><td>${w.name}</td><td>${w.available}</td></tr>`;
        });

        const recTbody = document.querySelector('#aw-recommended-table tbody');
        recTbody.innerHTML = '';
        aw.recommendedSplit.forEach(r => {
            recTbody.innerHTML += `<tr><td>${r.warehouse}</td><td><input type="number" class="form-control form-control-sm aw-manual-input" value="${r.allocate}" disabled></td></tr>`;
        });
    }

    window.acceptSplit = function() {
        showNotification('Suggested allocation accepted for preview.', 'success');
    };

    window.enableManualOverride = function() {
        document.querySelectorAll('.aw-manual-input').forEach(input => {
            input.disabled = false;
        });
        document.getElementById('aw-confirm-manual-btn').style.display = 'inline-block';
        showNotification('Manual override enabled.', 'info');
    };

    window.confirmManualAllocation = function() {
        document.querySelectorAll('.aw-manual-input').forEach(input => {
            input.disabled = true;
        });
        document.getElementById('aw-confirm-manual-btn').style.display = 'none';
        showNotification('Manual allocation confirmed (Preview only).', 'success');
    };

    // Deal Health
    let currentHealthFilter = 'All';
    function renderDealHealth() {
        const dh = MOCK_DATA.dealHealth;
        
        // KPIs
        document.getElementById('dh-kpi-1').innerText = dh.kpis.highRiskDeals;
        document.getElementById('dh-kpi-2').innerText = dh.kpis.stalledDeals;
        document.getElementById('dh-kpi-3').innerText = dh.kpis.approvalDelays;
        document.getElementById('dh-kpi-4').innerText = dh.kpis.discountAnomalies;
        document.getElementById('dh-kpi-5').innerText = dh.kpis.deliverySlippage;

        // Risk Dist
        document.getElementById('dh-dist-low').style.width = dh.riskDistribution.low + '%';
        document.getElementById('dh-dist-low').innerText = `Low (${dh.riskDistribution.low}%)`;
        document.getElementById('dh-dist-med').style.width = dh.riskDistribution.medium + '%';
        document.getElementById('dh-dist-med').innerText = `Medium (${dh.riskDistribution.medium}%)`;
        document.getElementById('dh-dist-high').style.width = dh.riskDistribution.high + '%';
        document.getElementById('dh-dist-high').innerText = `High (${dh.riskDistribution.high}%)`;
        document.getElementById('dh-dist-crit').style.width = dh.riskDistribution.critical + '%';
        document.getElementById('dh-dist-crit').innerText = `Critical (${dh.riskDistribution.critical}%)`;

        // Filter text
        document.getElementById('dh-filter-text').innerText = currentHealthFilter;

        // Table
        const tbody = document.querySelector('#dh-table tbody');
        const emptyState = document.getElementById('dh-empty-state');
        const tableContainer = document.getElementById('dh-table-container');
        
        tbody.innerHTML = '';
        
        const filtered = currentHealthFilter === 'All' 
            ? dh.deals 
            : dh.deals.filter(d => d.issue_type === currentHealthFilter);

        document.getElementById('dh-count').innerText = `${filtered.length} Deals`;

        if (filtered.length === 0) {
            tableContainer.style.display = 'none';
            emptyState.style.display = 'block';
        } else {
            tableContainer.style.display = 'block';
            emptyState.style.display = 'none';
            
            filtered.forEach(d => {
                let badgeClass = (d.issue_severity === 'critical' || d.issue_severity === 'high') ? 'dealflow-bg-danger' : 'dealflow-bg-warning';
                tbody.innerHTML += `
                    <tr>
                        <td class="fw-bold">${d.deal_name}</td>
                        <td>${d.customer}</td>
                        <td><span class="badge ${badgeClass}">${d.issue_type}</span></td>
                        <td>${d.age}</td>
                        <td>${getRiskBadge(d.risk_level)}</td>
                        <td>${d.status}</td>
                        <td class="text-end">
                            <button class="btn btn-sm btn-outline-primary" onclick="openHealthDeal(${d.deal_id})">Open Deal</button>
                        </td>
                    </tr>
                `;
            });
        }
    }

    window.setHealthFilter = function(filter) {
        currentHealthFilter = filter;
        renderDealHealth();
    };

    window.openHealthDeal = function(id) {
        showNotification('Deal navigation is unavailable in frontend preview mode.', 'warning');
    };

    // Initialize Dashboard
    renderSection('dashboard');
});
