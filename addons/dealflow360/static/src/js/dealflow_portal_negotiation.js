/** @odoo-module **/

function initDealflowPortal() {
    const container = document.getElementById("dealflow_negotiation_portal_container");
    if (!container) return;

    const orderId = container.dataset.orderId;
    const accessToken = container.dataset.accessToken || "";

    if (!orderId) return;

    // Inject CSS to hide native Odoo elements to create a clean slate for DealFlow360
    const style = document.createElement('style');
    style.innerHTML = `
        #introduction, #quote_content table#sales_order_table, #quote_content .o_portal_sale_sidebar, section#terms { display: none !important; }
        .df360-wizard-step { width: 33.33%; text-align: center; position: relative; z-index: 1; }
        .df360-wizard-step::before { content: ''; position: absolute; top: 12px; left: -50%; width: 100%; height: 2px; background: #dee2e6; z-index: -1; }
        .df360-wizard-step:first-child::before { display: none; }
        .df360-wizard-step.active::before, .df360-wizard-step.completed::before { background: #0d6efd; }
        .df360-step-indicator { width: 26px; height: 26px; border-radius: 50%; background: #dee2e6; color: white; display: inline-flex; align-items: center; justify-content: center; font-size: 0.8rem; font-weight: bold; margin-bottom: 8px; }
        .df360-wizard-step.active .df360-step-indicator, .df360-wizard-step.completed .df360-step-indicator { background: #0d6efd; }
        .df360-wizard-step.active { font-weight: bold; color: #0d6efd; }
    `;
    document.head.appendChild(style);

    let quotationData = null;
    let activeNegotiation = null;
    let selectedPayloadLines = [];
    let overallReason = "";
    
    // Find the native Odoo accept button
    let nativeAcceptBtn = document.querySelector('a[data-bs-target="#modalaccept"]');

    async function jsonRpc(url, params = {}) {
        const response = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: params,
                id: Math.floor(Math.random() * 1000000),
            }),
        });
        const data = await response.json();
        if (data.error) throw new Error(data.error.data?.message || data.error.message || "RPC Error");
        return data.result;
    }

    function formatCurrency(amount, symbol) {
        symbol = symbol || "$";
        const val = parseFloat(amount || 0).toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        });
        return `${symbol}${val}`;
    }

    async function loadData() {
        container.innerHTML = `
            <div class="py-5 text-center text-muted">
                <i class="fa fa-circle-o-notch fa-spin fa-2x mb-3 text-primary"></i>
                <h5 class="mb-0">Loading DealFlow360 Quotation...</h5>
            </div>
        `;

        try {
            const quotRes = await jsonRpc(`/dealflow/api/quotation/${orderId}`, {
                order_id: parseInt(orderId),
                access_token: accessToken,
            });

            if (quotRes.status !== "success") {
                container.innerHTML = `<div class="alert alert-warning shadow-sm border-0"><i class="fa fa-exclamation-triangle me-2"></i> ${quotRes.message}</div>`;
                return;
            }

            quotationData = quotRes.quotation;

            if (quotationData.active_negotiation_id) {
                const statusRes = await jsonRpc(`/dealflow/api/negotiation/status/${quotationData.active_negotiation_id}`, {
                    negotiation_id: quotationData.active_negotiation_id,
                    access_token: accessToken,
                });
                if (statusRes.status === "success") {
                    activeNegotiation = statusRes.negotiation;
                }
            }

            renderPortalCard();
        } catch (err) {
            console.error(err);
            container.innerHTML = `<div class="alert alert-danger shadow-sm border-0"><i class="fa fa-exclamation-circle me-2"></i> Failed to load details.</div>`;
        }
    }

    function renderPortalCard() {
        if (!quotationData) return;

        const state = activeNegotiation ? activeNegotiation.state : "none";

        if (state === "submitted" || state === "under_review") {
            renderActiveState();
        } else if (state === "accepted") {
            renderAcceptedState();
        } else if (state === "rejected") {
            renderRejectedState();
        } else if (state === "stale") {
            renderStaleState();
        } else {
            renderDefaultState();
        }
    }

    function renderDefaultState() {
        let linesHtml = quotationData.lines.map(line => `
            <div class="d-flex justify-content-between align-items-center py-3 border-bottom">
                <div class="flex-grow-1">
                    <h6 class="fw-bold text-dark mb-1">${line.product_name}</h6>
                    <small class="text-muted">Quantity: ${line.quantity} &nbsp;&bull;&nbsp; Discount: ${line.discount}%</small>
                </div>
                <div class="text-end">
                    <h5 class="fw-bold text-dark mb-0">${formatCurrency(line.price_unit, quotationData.currency_symbol)}</h5>
                </div>
            </div>
        `).join("");

        container.innerHTML = `
            <div class="card border-0 shadow-sm rounded-4 mb-4" style="background: linear-gradient(145deg, #ffffff, #f8f9fa);">
                <div class="card-body p-4 p-md-5">
                    <div class="text-center mb-5">
                        <h5 class="text-uppercase text-muted fw-bold tracking-wide mb-2" style="letter-spacing: 2px;">DealFlow360</h5>
                        <h2 class="display-6 fw-bold text-dark mb-2">Quotation ${quotationData.name}</h2>
                        <h5 class="text-secondary fw-normal mb-3">${quotationData.partner_name || 'Customer'}</h5>
                        <span class="badge bg-primary-subtle text-primary rounded-1 px-4 py-2 fs-6 fw-bold text-uppercase">Awaiting Your Response</span>
                    </div>

                    <h4 class="fw-bold text-dark mb-3">YOUR QUOTATION</h4>
                    <div class="bg-white rounded-3 shadow-sm border p-4 mb-5">
                        ${linesHtml}
                        <div class="d-flex justify-content-between align-items-center pt-4 mt-2">
                            <h4 class="fw-bold text-muted mb-0">Total</h4>
                            <h2 class="fw-bold text-dark mb-0">${formatCurrency(quotationData.amount_total, quotationData.currency_symbol)}</h2>
                        </div>
                    </div>

                    <div class="d-flex flex-column flex-md-row justify-content-center gap-4">
                        <div id="df360_accept_btn_wrapper"></div>
                        <button id="df360_btn_start_negotiation" class="btn btn-outline-dark btn-lg px-5 fw-bold rounded-pill" style="border-width: 2px;">
                            <i class="fa fa-pencil me-2"></i> Request Changes
                        </button>
                    </div>
                </div>
            </div>
        `;

        if (nativeAcceptBtn) {
            let clonedBtn = nativeAcceptBtn.cloneNode(true);
            clonedBtn.className = "btn btn-primary btn-lg px-5 fw-bold rounded-pill";
            clonedBtn.innerHTML = "<i class='fa fa-check me-2'></i> Accept Quotation";
            document.getElementById("df360_accept_btn_wrapper").appendChild(clonedBtn);
        }

        document.getElementById("df360_btn_start_negotiation")?.addEventListener("click", renderNegotiationWizard);
    }
    
    // Status banners visually distinct and premium
    function renderStatusHeader(title, message, iconClass, colorClass) {
        return `
            <div class="card border-0 shadow-sm rounded-4 mb-4" style="background: linear-gradient(145deg, #ffffff, #f8f9fa);">
                <div class="card-body p-5 text-center">
                    <i class="${iconClass} text-${colorClass} mb-4" style="font-size: 4rem;"></i>
                    <h2 class="fw-bold text-dark mb-3">${title}</h2>
                    <p class="text-secondary fs-5 mb-4">${message}</p>
                    <div class="d-flex justify-content-center gap-3">
                        <button class="btn btn-outline-dark rounded-pill px-4 fw-bold" onclick="window.location.href='/my/quotes'">Back to My Quotes</button>
                        <button class="btn btn-light border shadow-sm rounded-pill px-4" onclick="window.location.reload();">Refresh Status</button>
                    </div>
                </div>
            </div>
        `;
    }

    function renderActiveState() {
        const isSubmitted = activeNegotiation.state === 'submitted';
        const title = isSubmitted ? 'REQUEST SUBMITTED' : 'BEING REVIEWED';
        const message = isSubmitted ? 'Your request has been sent to the sales team.' : 'Our sales team is actively reviewing your request.';
        const icon = isSubmitted ? 'fa fa-paper-plane' : 'fa fa-search';
        const color = isSubmitted ? 'primary' : 'warning';
        container.innerHTML = renderStatusHeader(title, message, icon, color);
    }

    function renderAcceptedState() {
        container.innerHTML = renderStatusHeader('CHANGES ACCEPTED', 'Your requested changes have been approved by the sales team.', 'fa fa-check-circle', 'success');
    }

    function renderRejectedState() {
        const html = renderStatusHeader('REQUEST DECLINED', 'The sales team has declined this specific request.', 'fa fa-times-circle', 'danger');
        container.innerHTML = html + `
            <div class="text-center mt-3">
                <button id="df360_btn_renegotiate" class="btn btn-primary rounded-pill px-4 fw-bold shadow-sm">Request Different Changes</button>
            </div>
        `;
        setTimeout(() => {
            document.getElementById("df360_btn_renegotiate")?.addEventListener("click", renderNegotiationWizard);
        }, 100);
    }

    function renderStaleState() {
        const html = renderStatusHeader('QUOTATION UPDATED', 'This request was created against an older version of the quotation.', 'fa fa-info-circle', 'secondary');
        container.innerHTML = html + `
            <div class="text-center mt-3">
                <button id="df360_btn_stale_new" class="btn btn-primary rounded-pill px-4 fw-bold shadow-sm">Start New Request</button>
            </div>
        `;
        setTimeout(() => {
            document.getElementById("df360_btn_stale_new")?.addEventListener("click", renderNegotiationWizard);
        }, 100);
    }

    function renderNegotiationWizard() {
        if (!quotationData || !quotationData.lines || quotationData.lines.length === 0) return;

        const linesListHtml = quotationData.lines.map((line, idx) => `
            <div class="card mb-4 border-0 shadow-sm rounded-4" style="background: #ffffff;">
                <div class="card-header bg-transparent border-bottom-0 pt-4 pb-0 px-4">
                    <h5 class="fw-bold text-dark mb-0">${line.product_name}</h5>
                </div>
                <div class="card-body p-4">
                    <div class="row align-items-center">
                        <div class="col-md-4 border-end-md mb-3 mb-md-0 px-md-4">
                            <h6 class="text-uppercase text-muted fw-bold mb-2" style="font-size: 0.8rem;">Current</h6>
                            <div class="small text-secondary">
                                <div>Qty: <strong class="text-dark">${line.quantity}</strong></div>
                                <div>Price: <strong class="text-dark">${formatCurrency(line.price_unit, quotationData.currency_symbol)}</strong></div>
                                <div>Disc: <strong class="text-dark">${line.discount}%</strong></div>
                            </div>
                        </div>
                        <div class="col-md-8 px-md-4">
                            <h6 class="text-uppercase text-primary fw-bold mb-3" style="font-size: 0.8rem;">Your Request</h6>
                            <div class="row g-3">
                                <div class="col-4">
                                    <label class="form-label text-muted small fw-bold mb-1">Quantity</label>
                                    <input type="number" step="any" min="0" class="form-control form-control-lg bg-light border-0 df360-input-qty text-center fw-bold" data-line-id="${line.id}" value="${line.quantity}">
                                </div>
                                <div class="col-4">
                                    <label class="form-label text-muted small fw-bold mb-1">Price</label>
                                    <input type="number" step="any" min="0" class="form-control form-control-lg bg-light border-0 df360-input-price text-center fw-bold" data-line-id="${line.id}" value="${line.price_unit}">
                                </div>
                                <div class="col-4">
                                    <label class="form-label text-muted small fw-bold mb-1">Discount %</label>
                                    <input type="number" step="any" min="0" max="100" class="form-control form-control-lg bg-light border-0 df360-input-discount text-center fw-bold" data-line-id="${line.id}" value="${line.discount}">
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `).join("");

        container.innerHTML = `
            <div class="card border-0 shadow-sm rounded-4 mb-4 bg-light">
                <div class="card-body p-4 p-md-5">
                    
                    <div class="d-flex justify-content-between mb-5 px-3 px-md-5 text-muted">
                        <div class="df360-wizard-step active" id="df360_nav_1">
                            <div class="df360-step-indicator shadow-sm">1</div>
                            <div class="small text-uppercase tracking-wide mt-1">Changes</div>
                        </div>
                        <div class="df360-wizard-step" id="df360_nav_2">
                            <div class="df360-step-indicator shadow-sm">2</div>
                            <div class="small text-uppercase tracking-wide mt-1">Reason</div>
                        </div>
                        <div class="df360-wizard-step" id="df360_nav_3">
                            <div class="df360-step-indicator shadow-sm">3</div>
                            <div class="small text-uppercase tracking-wide mt-1">Review</div>
                        </div>
                    </div>
                    
                    <!-- STEP 1 -->
                    <div id="df360_step_1">
                        <div class="text-center mb-4">
                            <h3 class="fw-bold text-dark">What would you like to change?</h3>
                            <p class="text-muted">Adjust the quantities, pricing, or discounts you need.</p>
                        </div>
                        <div id="df360_val_alert" class="alert alert-danger d-none rounded-3 border-0 shadow-sm"></div>
                        ${linesListHtml}
                        <div class="text-end mt-4">
                            <button id="df360_btn_cancel" class="btn btn-link text-muted fw-bold me-3 text-decoration-none">Cancel</button>
                            <button id="df360_btn_next_1" class="btn btn-primary btn-lg px-5 rounded-pill fw-bold shadow-sm">Continue</button>
                        </div>
                    </div>

                    <!-- STEP 2 -->
                    <div id="df360_step_2" class="d-none">
                        <div class="text-center mb-4">
                            <h3 class="fw-bold text-dark">Why are you requesting these changes?</h3>
                            <p class="text-muted">Tell the sales team about your request.</p>
                        </div>
                        <div class="card border-0 shadow-sm rounded-4 mb-4">
                            <div class="card-body p-4">
                                <textarea id="df360_overall_reason" class="form-control form-control-lg border-0 bg-light rounded-3" rows="8" placeholder="Type your message here..."></textarea>
                            </div>
                        </div>
                        <div class="d-flex justify-content-between mt-4">
                            <button id="df360_btn_back_1" class="btn btn-outline-dark btn-lg px-5 rounded-pill fw-bold">Back</button>
                            <button id="df360_btn_next_2" class="btn btn-primary btn-lg px-5 rounded-pill fw-bold shadow-sm">Continue</button>
                        </div>
                    </div>

                    <!-- STEP 3 -->
                    <div id="df360_step_3" class="d-none">
                        <div class="text-center mb-4">
                            <h3 class="fw-bold text-dark">Review Your Request</h3>
                            <p class="text-muted">Please confirm your changes before submitting.</p>
                        </div>
                        <div id="df360_submit_alert" class="alert alert-danger d-none rounded-3 border-0 shadow-sm"></div>
                        
                        <div class="row">
                            <div class="col-md-8 mx-auto">
                                <div class="card border-0 shadow-sm rounded-4 mb-4">
                                    <div class="card-header bg-white border-bottom pt-4 pb-3 px-4">
                                        <div class="row fw-bold text-muted small text-uppercase">
                                            <div class="col-4">Current Terms</div>
                                            <div class="col-4 text-center"><i class="fa fa-arrow-right"></i></div>
                                            <div class="col-4 text-end text-primary">Requested Terms</div>
                                        </div>
                                    </div>
                                    <div class="card-body p-0" id="df360_review_summary">
                                    </div>
                                </div>
                                <div class="card border-0 shadow-sm rounded-4 mb-4">
                                    <div class="card-body p-4 bg-white rounded-4">
                                        <h6 class="text-uppercase text-muted fw-bold mb-2" style="font-size: 0.8rem;">Message</h6>
                                        <p class="text-dark mb-0 fst-italic" id="df360_review_reason"></p>
                                    </div>
                                </div>
                                
                                <div class="d-flex justify-content-between mt-5">
                                    <button id="df360_btn_back_2" class="btn btn-outline-dark btn-lg px-5 rounded-pill fw-bold">Back</button>
                                    <button id="df360_btn_submit" class="btn btn-success btn-lg px-5 rounded-pill fw-bold shadow-sm">Submit Request</button>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                </div>
            </div>
        `;

        // Event Listeners
        document.getElementById("df360_btn_cancel")?.addEventListener("click", renderDefaultState);

        // Navigation Elements
        const step1 = document.getElementById("df360_step_1");
        const step2 = document.getElementById("df360_step_2");
        const step3 = document.getElementById("df360_step_3");
        const nav1 = document.getElementById("df360_nav_1");
        const nav2 = document.getElementById("df360_nav_2");
        const nav3 = document.getElementById("df360_nav_3");

        document.getElementById("df360_btn_next_1")?.addEventListener("click", () => {
            const valAlert = document.getElementById("df360_val_alert");
            valAlert.classList.add("d-none");
            
            selectedPayloadLines = [];
            let isValid = true;
            let hasChanges = false;

            quotationData.lines.forEach(lineObj => {
                const qtyInput = document.querySelector(`.df360-input-qty[data-line-id='${lineObj.id}']`);
                const priceInput = document.querySelector(`.df360-input-price[data-line-id='${lineObj.id}']`);
                const discInput = document.querySelector(`.df360-input-discount[data-line-id='${lineObj.id}']`);

                const reqQty = parseFloat(qtyInput?.value);
                const reqPrice = parseFloat(priceInput?.value);
                const reqDisc = parseFloat(discInput?.value);

                if (isNaN(reqQty) || reqQty < 0 || isNaN(reqPrice) || reqPrice < 0 || isNaN(reqDisc) || reqDisc < 0 || reqDisc > 100) {
                    valAlert.innerText = `Invalid values entered for ${lineObj.product_name}.`;
                    isValid = false;
                    return;
                }

                if (reqQty !== lineObj.quantity || reqPrice !== lineObj.price_unit || reqDisc !== lineObj.discount) {
                    hasChanges = true;
                }

                selectedPayloadLines.push({
                    order_line_id: lineObj.id,
                    requested_quantity: reqQty,
                    requested_unit_price: reqPrice,
                    requested_discount: reqDisc,
                    customer_reason: "",
                    orig_name: lineObj.product_name,
                    curr_qty: lineObj.quantity,
                    curr_price: lineObj.price_unit,
                    curr_disc: lineObj.discount,
                });
            });

            if (!hasChanges) {
                valAlert.innerText = "Please make at least one change to continue.";
                isValid = false;
            }

            if (isValid) {
                step1.classList.add("d-none");
                step2.classList.remove("d-none");
                nav1.classList.remove("active");
                nav1.classList.add("completed");
                nav2.classList.add("active");
            } else {
                valAlert.classList.remove("d-none");
            }
        });

        document.getElementById("df360_btn_back_1")?.addEventListener("click", () => {
            step2.classList.add("d-none");
            step1.classList.remove("d-none");
            nav2.classList.remove("active");
            nav1.classList.add("active");
            nav1.classList.remove("completed");
        });

        document.getElementById("df360_btn_next_2")?.addEventListener("click", () => {
            overallReason = document.getElementById("df360_overall_reason")?.value || "";
            
            // Build Review HTML - only showing changed lines
            const changedLines = selectedPayloadLines.filter(l => l.curr_qty !== l.requested_quantity || l.curr_price !== l.requested_unit_price || l.curr_disc !== l.requested_discount);
            
            const reviewHtml = changedLines.map(l => `
                <div class="px-4 py-3 border-bottom">
                    <h6 class="fw-bold text-dark mb-2">${l.orig_name}</h6>
                    <div class="row align-items-center text-center small">
                        <div class="col-4 text-muted">
                            ${l.curr_qty !== l.requested_quantity ? `<div>Qty: ${l.curr_qty}</div>` : ''}
                            ${l.curr_price !== l.requested_unit_price ? `<div>Price: ${formatCurrency(l.curr_price, quotationData.currency_symbol)}</div>` : ''}
                            ${l.curr_disc !== l.requested_discount ? `<div>Disc: ${l.curr_disc}%</div>` : ''}
                        </div>
                        <div class="col-4"><i class="fa fa-arrow-right text-primary"></i></div>
                        <div class="col-4 text-primary fw-bold">
                            ${l.curr_qty !== l.requested_quantity ? `<div>${l.requested_quantity}</div>` : ''}
                            ${l.curr_price !== l.requested_unit_price ? `<div>${formatCurrency(l.requested_unit_price, quotationData.currency_symbol)}</div>` : ''}
                            ${l.curr_disc !== l.requested_discount ? `<div>${l.requested_discount}%</div>` : ''}
                        </div>
                    </div>
                </div>
            `).join("");

            document.getElementById("df360_review_summary").innerHTML = reviewHtml;
            document.getElementById("df360_review_reason").innerText = overallReason ? `"${overallReason}"` : "No message provided.";

            step2.classList.add("d-none");
            step3.classList.remove("d-none");
            nav2.classList.remove("active");
            nav2.classList.add("completed");
            nav3.classList.add("active");
        });

        document.getElementById("df360_btn_back_2")?.addEventListener("click", () => {
            step3.classList.add("d-none");
            step2.classList.remove("d-none");
            nav3.classList.remove("active");
            nav2.classList.add("active");
            nav2.classList.remove("completed");
        });

        document.getElementById("df360_btn_submit")?.addEventListener("click", async () => {
            const submitAlert = document.getElementById("df360_submit_alert");
            const btnSubmit = document.getElementById("df360_btn_submit");
            const btnBack = document.getElementById("df360_btn_back_2");
            
            submitAlert.classList.add("d-none");
            btnSubmit.disabled = true;
            btnBack.disabled = true;
            btnSubmit.innerHTML = `<i class="fa fa-circle-o-notch fa-spin me-2"></i> Submitting...`;

            try {
                // Only send changed lines
                const changedLines = selectedPayloadLines.filter(l => l.curr_qty !== l.requested_quantity || l.curr_price !== l.requested_unit_price || l.curr_disc !== l.requested_discount);
                
                const res = await jsonRpc("/dealflow/api/negotiation/submit", {
                    order_id: parseInt(orderId),
                    lines: changedLines.map(l => ({
                        order_line_id: l.order_line_id,
                        requested_quantity: l.requested_quantity,
                        requested_unit_price: l.requested_unit_price,
                        requested_discount: l.requested_discount,
                        customer_reason: "",
                    })),
                    reason: overallReason,
                    access_token: accessToken,
                });

                if (res.status === "success") {
                    container.innerHTML = renderStatusHeader('REQUEST SUBMITTED', 'Your request has been sent to the sales team.', 'fa fa-paper-plane', 'primary');
                } else {
                    submitAlert.innerText = res.message || "Failed to submit request.";
                    submitAlert.classList.remove("d-none");
                    btnSubmit.disabled = false;
                    btnBack.disabled = false;
                    btnSubmit.innerHTML = "Submit Request";
                }
            } catch (err) {
                console.error(err);
                submitAlert.innerText = "An error occurred. Please try again.";
                submitAlert.classList.remove("d-none");
                btnSubmit.disabled = false;
                btnBack.disabled = false;
                btnSubmit.innerHTML = "Submit Request";
            }
        });
    }

    loadData();
}

if (document.readyState !== "loading") {
    initDealflowPortal();
} else {
    document.addEventListener("DOMContentLoaded", initDealflowPortal);
}
