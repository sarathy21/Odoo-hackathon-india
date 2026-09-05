/** @odoo-module **/

function initDealflowPortal() {
    const container = document.getElementById("dealflow_negotiation_portal_container");
    if (!container) {
        return;
    }

    const orderId = container.dataset.orderId;
    const accessToken = container.dataset.accessToken || "";

    if (!orderId) {
        return;
    }

    let quotationData = null;
    let activeNegotiation = null;

    // Helper for JSON-RPC 2.0 requests
    async function jsonRpc(url, params = {}) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                method: "call",
                params: params,
                id: Math.floor(Math.random() * 1000000),
            }),
        });
        const data = await response.json();
        if (data.error) {
            throw new Error(data.error.data?.message || data.error.message || "RPC Error");
        }
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
            <div class="df360-portal-card p-4 text-center text-muted">
                <i class="fa fa-circle-o-notch fa-spin fa-2x mb-2 text-primary"></i>
                <p class="mb-0">Loading negotiation options...</p>
            </div>
        `;

        try {
            const quotRes = await jsonRpc(`/dealflow/api/quotation/${orderId}`, {
                order_id: parseInt(orderId),
                access_token: accessToken,
            });

            if (quotRes.status !== "success") {
                container.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="fa fa-exclamation-triangle me-2"></i> ${quotRes.message || "Unable to load quotation details."}
                    </div>
                `;
                return;
            }

            quotationData = quotRes.quotation;

            // Check if there is an existing negotiation status
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
            console.error("DealFlow360 Portal Load Error:", err);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fa fa-exclamation-circle me-2"></i> We couldn't load negotiation details. Please try again.
                </div>
            `;
        }
    }

    function renderPortalCard() {
        if (!quotationData) return;

        // Determine UI State
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
        container.innerHTML = `
            <div class="df360-portal-card">
                <div class="df360-portal-header">
                    <h5>🤝 DealFlow360 Commercial Negotiation</h5>
                    <span class="badge bg-primary rounded-pill">Available</span>
                </div>
                <div class="df360-portal-body">
                    <p class="text-secondary mb-3">
                        Want to request different commercial terms? You can propose changes to quantity, unit price, or discount for selected quotation lines.
                    </p>
                    <button id="df360_btn_start_negotiation" class="btn btn-primary px-4 fw-bold">
                        <i class="fa fa-handshake-o me-1"></i> Start Negotiation
                    </button>
                </div>
            </div>
        `;

        document.getElementById("df360_btn_start_negotiation")?.addEventListener("click", openNegotiationModal);
    }

    function renderActiveState() {
        const linesHtml = (activeNegotiation.lines || []).map(l => `
            <div class="border-bottom pb-2 mb-2">
                <div class="fw-bold text-dark">${l.product_name}</div>
                <div class="small text-muted">
                    <span>Qty: ${l.current_quantity} <span class="df360-arrow">→</span> <strong>${l.requested_quantity}</strong></span> | 
                    <span>Price: ${formatCurrency(l.current_unit_price, quotationData.currency_symbol)} <span class="df360-arrow">→</span> <strong>${formatCurrency(l.requested_unit_price, quotationData.currency_symbol)}</strong></span> | 
                    <span>Discount: ${l.current_discount}% <span class="df360-arrow">→</span> <strong>${l.requested_discount}%</strong></span>
                </div>
            </div>
        `).join("");

        container.innerHTML = `
            <div class="df360-portal-card border-warning">
                <div class="df360-portal-header bg-dark">
                    <h5>🤝 DealFlow360 Negotiation</h5>
                    <span class="df360-badge df360-badge-${activeNegotiation.state}">
                        🟡 ${activeNegotiation.state === 'submitted' ? 'Submitted' : 'Under Review'}
                    </span>
                </div>
                <div class="df360-portal-body">
                    <div class="alert alert-warning py-2 mb-3 small">
                        <i class="fa fa-clock-o me-1"></i> You already have an active negotiation request pending review for this quotation.
                    </div>
                    <div class="mb-3">
                        <div class="small text-muted mb-1">Submitted Date: ${activeNegotiation.requested_date || 'Recently'}</div>
                        <div class="bg-light p-3 rounded">
                            ${linesHtml}
                        </div>
                    </div>
                    ${activeNegotiation.reason ? `<p class="small text-muted mb-0"><strong>Customer Reason:</strong> ${activeNegotiation.reason}</p>` : ''}
                </div>
            </div>
        `;
    }

    function renderAcceptedState() {
        container.innerHTML = `
            <div class="df360-portal-card border-success">
                <div class="df360-portal-header bg-success">
                    <h5>✓ Commercial Negotiation Accepted</h5>
                    <span class="df360-badge df360-badge-accepted">Accepted</span>
                </div>
                <div class="df360-portal-body">
                    <p class="text-success fw-bold mb-2">
                        Your requested commercial changes have been accepted and applied to the quotation!
                    </p>
                    <button class="btn btn-outline-success btn-sm mt-2" onclick="window.location.reload();">
                        <i class="fa fa-refresh me-1"></i> Refresh Page to View Updated Quotation
                    </button>
                </div>
            </div>
        `;
    }

    function renderRejectedState() {
        container.innerHTML = `
            <div class="df360-portal-card border-danger">
                <div class="df360-portal-header bg-danger">
                    <h5>✕ Commercial Negotiation Response</h5>
                    <span class="df360-badge df360-badge-rejected">Not Accepted</span>
                </div>
                <div class="df360-portal-body">
                    <p class="text-danger fw-bold mb-2">Your requested changes were not accepted by the sales team.</p>
                    ${activeNegotiation && activeNegotiation.rejection_reason ? `
                        <div class="alert alert-light border border-danger-subtle small mb-3">
                            <strong>Reason:</strong> ${activeNegotiation.rejection_reason}
                        </div>
                    ` : ''}
                    <button id="df360_btn_renegotiate" class="btn btn-outline-primary btn-sm">
                        <i class="fa fa-repeat me-1"></i> Propose New Negotiation
                    </button>
                </div>
            </div>
        `;

        document.getElementById("df360_btn_renegotiate")?.addEventListener("click", openNegotiationModal);
    }

    function renderStaleState() {
        container.innerHTML = `
            <div class="df360-portal-card border-secondary">
                <div class="df360-portal-header bg-secondary">
                    <h5>⚠ Negotiation Request Outdated</h5>
                    <span class="df360-badge df360-badge-stale">Stale</span>
                </div>
                <div class="df360-portal-body">
                    <p class="text-muted mb-3">
                        This quotation has undergone commercial changes since your request was created. Please review the updated quotation terms.
                    </p>
                    <button id="df360_btn_stale_new" class="btn btn-primary btn-sm fw-bold">
                        <i class="fa fa-plus me-1"></i> Start New Negotiation Request
                    </button>
                </div>
            </div>
        `;

        document.getElementById("df360_btn_stale_new")?.addEventListener("click", openNegotiationModal);
    }

    function openNegotiationModal() {
        if (!quotationData || !quotationData.lines || quotationData.lines.length === 0) {
            alert("No editable quotation lines available for negotiation.");
            return;
        }

        let existingModal = document.getElementById("df360_modal_root");
        if (existingModal) {
            existingModal.remove();
        }

        const linesListHtml = quotationData.lines.map((line, idx) => `
            <div class="df360-line-card" id="df360_line_card_${line.id}">
                <div class="form-check df360-line-title">
                    <input class="form-check-input df360-line-select" type="checkbox" value="${line.id}" id="df360_chk_${line.id}" ${idx === 0 ? 'checked' : ''}>
                    <label class="form-check-label text-dark fw-bold ms-1" for="df360_chk_${line.id}">
                        ${line.product_name}
                    </label>
                </div>
                
                <div class="df360-grid-diff">
                    <!-- Quantity -->
                    <div class="df360-diff-box">
                        <div class="df360-diff-label">Quantity</div>
                        <div class="df360-diff-current mb-1">Current: <strong>${line.quantity}</strong></div>
                        <div class="df360-diff-input-group">
                            <input type="number" step="any" min="0" class="form-control form-control-sm df360-input-qty" data-line-id="${line.id}" value="${line.quantity}">
                        </div>
                    </div>

                    <!-- Unit Price -->
                    <div class="df360-diff-box">
                        <div class="df360-diff-label">Unit Price (${quotationData.currency_symbol})</div>
                        <div class="df360-diff-current mb-1">Current: <strong>${formatCurrency(line.price_unit, quotationData.currency_symbol)}</strong></div>
                        <div class="df360-diff-input-group">
                            <input type="number" step="any" min="0" class="form-control form-control-sm df360-input-price" data-line-id="${line.id}" value="${line.price_unit}">
                        </div>
                    </div>

                    <!-- Discount -->
                    <div class="df360-diff-box">
                        <div class="df360-diff-label">Discount %</div>
                        <div class="df360-diff-current mb-1">Current: <strong>${line.discount}%</strong></div>
                        <div class="df360-diff-input-group">
                            <input type="number" step="any" min="0" max="100" class="form-control form-control-sm df360-input-discount" data-line-id="${line.id}" value="${line.discount}">
                        </div>
                    </div>
                </div>

                <div class="mt-2">
                    <input type="text" class="form-control form-control-sm df360-input-line-reason" data-line-id="${line.id}" placeholder="Reason for line change (optional)...">
                </div>
            </div>
        `).join("");

        const modalDom = document.createElement("div");
        modalDom.id = "df360_modal_root";
        modalDom.className = "modal fade show d-block";
        modalDom.style.backgroundColor = "rgba(15, 23, 42, 0.6)";
        modalDom.setAttribute("tabindex", "-1");

        modalDom.innerHTML = `
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content shadow-lg border-0">
                    <div class="modal-header bg-dark text-white">
                        <h5 class="modal-title font-weight-bold"><i class="fa fa-handshake-o me-2"></i> Request Commercial Terms Negotiation</h5>
                        <button type="button" class="btn-close btn-close-white" id="df360_modal_close"></button>
                    </div>
                    
                    <div class="modal-body df360-modal-body" id="df360_modal_step_1">
                        <div class="alert alert-info py-2 small mb-3">
                            <i class="fa fa-info-circle me-1"></i> Select the quotation lines you wish to negotiate and specify your requested terms.
                        </div>

                        <div id="df360_modal_validation_alert" class="alert alert-danger d-none py-2 small mb-3"></div>

                        <div class="mb-3">
                            ${linesListHtml}
                        </div>

                        <div class="mb-3">
                            <label class="form-label font-weight-bold text-dark small">Overall Negotiation Reason / Message</label>
                            <textarea id="df360_overall_reason" class="form-control" rows="3" placeholder="Explain your overall proposal or commercial request..."></textarea>
                        </div>
                    </div>

                    <div class="modal-body df360-modal-body d-none" id="df360_modal_step_2">
                        <h6 class="fw-bold mb-3">Review Your Proposed Changes</h6>
                        <div id="df360_modal_submit_alert" class="alert alert-danger d-none py-2 small mb-3"></div>
                        <div id="df360_review_summary" class="bg-light p-3 rounded mb-3"></div>
                        <div class="alert alert-warning py-2 small mb-0">
                            <i class="fa fa-shield me-1"></i> Submitting this request sends your proposal to the sales team for review. Your quotation remains active.
                        </div>
                    </div>

                    <div class="modal-footer bg-light">
                        <button type="button" class="btn btn-secondary" id="df360_btn_cancel">Cancel</button>
                        <button type="button" class="btn btn-outline-primary d-none" id="df360_btn_back"><i class="fa fa-arrow-left me-1"></i> Edit Changes</button>
                        <button type="button" class="btn btn-primary font-weight-bold" id="df360_btn_next">Review Proposal <i class="fa fa-arrow-right ms-1"></i></button>
                        <button type="button" class="btn btn-success font-weight-bold d-none" id="df360_btn_submit">Submit Negotiation <i class="fa fa-paper-plane ms-1"></i></button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modalDom);

        // Highlight selected lines
        modalDom.querySelectorAll(".df360-line-select").forEach(chk => {
            chk.addEventListener("change", (e) => {
                const card = document.getElementById(`df360_line_card_${e.target.value}`);
                if (card) {
                    if (e.target.checked) card.classList.add("selected");
                    else card.classList.remove("selected");
                }
            });
            if (chk.checked) {
                const card = document.getElementById(`df360_line_card_${chk.value}`);
                if (card) card.classList.add("selected");
            }
        });

        // Close handlers
        const closeModal = () => modalDom.remove();
        document.getElementById("df360_modal_close")?.addEventListener("click", closeModal);
        document.getElementById("df360_btn_cancel")?.addEventListener("click", closeModal);

        let selectedPayloadLines = [];

        // Step 1 -> Step 2 Review
        document.getElementById("df360_btn_next")?.addEventListener("click", () => {
            const valAlert = document.getElementById("df360_modal_validation_alert");
            valAlert.classList.add("d-none");
            valAlert.innerHTML = "";

            const selectedCheckboxes = modalDom.querySelectorAll(".df360-line-select:checked");
            if (selectedCheckboxes.length === 0) {
                valAlert.innerHTML = "<i class='fa fa-exclamation-triangle me-1'></i> Please select at least one quotation line to negotiate.";
                valAlert.classList.remove("d-none");
                return;
            }

            selectedPayloadLines = [];
            let isValid = true;

            selectedCheckboxes.forEach(chk => {
                const lineId = parseInt(chk.value);
                const lineObj = quotationData.lines.find(l => l.id === lineId);
                
                const qtyInput = modalDom.querySelector(`.df360-input-qty[data-line-id='${lineId}']`);
                const priceInput = modalDom.querySelector(`.df360-input-price[data-line-id='${lineId}']`);
                const discInput = modalDom.querySelector(`.df360-input-discount[data-line-id='${lineId}']`);
                const reasonInput = modalDom.querySelector(`.df360-input-line-reason[data-line-id='${lineId}']`);

                const reqQty = parseFloat(qtyInput?.value);
                const reqPrice = parseFloat(priceInput?.value);
                const reqDisc = parseFloat(discInput?.value);

                if (isNaN(reqQty) || reqQty < 0) {
                    valAlert.innerHTML = `<i class='fa fa-exclamation-triangle me-1'></i> Invalid requested quantity for <strong>${lineObj.product_name}</strong>. Must be >= 0.`;
                    isValid = false;
                    return;
                }
                if (isNaN(reqPrice) || reqPrice < 0) {
                    valAlert.innerHTML = `<i class='fa fa-exclamation-triangle me-1'></i> Invalid requested price for <strong>${lineObj.product_name}</strong>. Must be >= 0.`;
                    isValid = false;
                    return;
                }
                if (isNaN(reqDisc) || reqDisc < 0 || reqDisc > 100) {
                    valAlert.innerHTML = `<i class='fa fa-exclamation-triangle me-1'></i> Invalid requested discount for <strong>${lineObj.product_name}</strong>. Must be between 0 and 100%.`;
                    isValid = false;
                    return;
                }

                selectedPayloadLines.push({
                    order_line_id: lineId,
                    requested_quantity: reqQty,
                    requested_unit_price: reqPrice,
                    requested_discount: reqDisc,
                    customer_reason: reasonInput?.value || "",
                    orig_name: lineObj.product_name,
                    curr_qty: lineObj.quantity,
                    curr_price: lineObj.price_unit,
                    curr_disc: lineObj.discount,
                });
            });

            if (!isValid) {
                valAlert.classList.remove("d-none");
                return;
            }

            // Build Review Screen HTML
            const reviewHtml = selectedPayloadLines.map(l => `
                <div class="df360-review-line">
                    <div class="fw-bold text-dark mb-1">${l.orig_name}</div>
                    <div class="small">
                        <div>Quantity: ${l.curr_qty} <span class="df360-arrow">→</span> <strong>${l.requested_quantity}</strong></div>
                        <div>Unit Price: ${formatCurrency(l.curr_price, quotationData.currency_symbol)} <span class="df360-arrow">→</span> <strong>${formatCurrency(l.requested_unit_price, quotationData.currency_symbol)}</strong></div>
                        <div>Discount: ${l.curr_disc}% <span class="df360-arrow">→</span> <strong>${l.requested_discount}%</strong></div>
                        ${l.customer_reason ? `<div class="text-muted italic mt-1">Reason: ${l.customer_reason}</div>` : ''}
                    </div>
                </div>
            `).join("");

            document.getElementById("df360_review_summary").innerHTML = reviewHtml;

            // Switch to Step 2
            document.getElementById("df360_modal_step_1").classList.add("d-none");
            document.getElementById("df360_modal_step_2").classList.remove("d-none");

            document.getElementById("df360_btn_next").classList.add("d-none");
            document.getElementById("df360_btn_back").classList.remove("d-none");
            document.getElementById("df360_btn_submit").classList.remove("d-none");
        });

        // Step 2 -> Step 1 Back
        document.getElementById("df360_btn_back")?.addEventListener("click", () => {
            document.getElementById("df360_modal_step_2").classList.add("d-none");
            document.getElementById("df360_modal_step_1").classList.remove("d-none");

            document.getElementById("df360_btn_next").classList.remove("d-none");
            document.getElementById("df360_btn_back").classList.add("d-none");
            document.getElementById("df360_btn_submit").classList.add("d-none");
        });

        // Submit Negotiation
        document.getElementById("df360_btn_submit")?.addEventListener("click", async () => {
            const btnSubmit = document.getElementById("df360_btn_submit");
            const btnBack = document.getElementById("df360_btn_back");
            const submitAlert = document.getElementById("df360_modal_submit_alert");
            
            submitAlert.classList.add("d-none");
            submitAlert.innerHTML = "";
            
            btnSubmit.disabled = true;
            btnBack.disabled = true;

            btnSubmit.innerHTML = `<i class="fa fa-circle-o-notch fa-spin me-1"></i> Submitting negotiation...`;

            const overallReason = document.getElementById("df360_overall_reason")?.value || "";

            try {
                const res = await jsonRpc("/dealflow/api/negotiation/submit", {
                    order_id: parseInt(orderId),
                    lines: selectedPayloadLines.map(l => ({
                        order_line_id: l.order_line_id,
                        requested_quantity: l.requested_quantity,
                        requested_unit_price: l.requested_unit_price,
                        requested_discount: l.requested_discount,
                        customer_reason: l.customer_reason,
                    })),
                    reason: overallReason,
                    access_token: accessToken,
                });

                if (res.status === "success") {
                    modalDom.remove();
                    // Reload portal card status
                    await loadData();
                } else {
                    submitAlert.innerHTML = `<i class='fa fa-exclamation-triangle me-1'></i> ${res.message || "Failed to submit negotiation request. The quotation might have changed."}`;
                    submitAlert.classList.remove("d-none");
                    btnSubmit.disabled = false;
                    btnBack.disabled = false;
                    btnSubmit.innerHTML = `Submit Negotiation <i class="fa fa-paper-plane ms-1"></i>`;
                }
            } catch (err) {
                console.error("Negotiation Submit Error:", err);
                submitAlert.innerHTML = `<i class='fa fa-exclamation-triangle me-1'></i> An error occurred while submitting your negotiation request. Please try again.`;
                submitAlert.classList.remove("d-none");
                btnSubmit.disabled = false;
                btnBack.disabled = false;
                btnSubmit.innerHTML = `Submit Negotiation <i class="fa fa-paper-plane ms-1"></i>`;
            }
        });
    }

    // Initialize portal loader
    loadData();
}

if (document.readyState !== "loading") {
    initDealflowPortal();
} else {
    document.addEventListener("DOMContentLoaded", initDealflowPortal);
}

