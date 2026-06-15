document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const reviewPanel = document.getElementById('reviewPanel');
    const reviewPanelOverlay = document.getElementById('reviewPanelOverlay');
    const btnCloseReviewPanel = document.getElementById('btnCloseReviewPanel');
    const reviewSpinner = document.getElementById('reviewSpinner');
    const reviewContentArea = document.getElementById('reviewContentArea');
    const tabButtons = document.querySelectorAll('.review-tab');
    const tabContents = document.querySelectorAll('.review-tab-content');
    
    // Banner
    const verifiedBanner = document.getElementById('verifiedBanner');
    const btnProceedMigration = document.getElementById('btnProceedMigration');
    
    // Tab 1 Elements
    const reviewFullName = document.getElementById('reviewFullName');
    const reviewPhone = document.getElementById('reviewPhone');
    const reviewPersonalEmail = document.getElementById('reviewPersonalEmail');
    const reviewCompanyEmail = document.getElementById('reviewCompanyEmail');
    const reviewJoiningDate = document.getElementById('reviewJoiningDate');
    const reviewRole = document.getElementById('reviewRole');
    const reviewDepartment = document.getElementById('reviewDepartment');
    const reviewStatusBadge = document.getElementById('reviewStatusBadge');
    const reviewPersonId = document.getElementById('reviewPersonId');
    const btnCopyReviewId = document.getElementById('btnCopyReviewId');
    
    // Tab 2 Elements
    const declarationGrid = document.getElementById('declarationGrid');
    const decStatusBadge = document.getElementById('decStatusBadge');
    const decApprovedBanner = document.getElementById('decApprovedBanner');
    const decHrNotesBox = document.getElementById('decHrNotesBox');
    const decHrNotesText = document.getElementById('decHrNotesText');
    const decActionButtons = document.getElementById('decActionButtons');
    const btnRequestChanges = document.getElementById('btnRequestChanges');
    const btnApproveDeclaration = document.getElementById('btnApproveDeclaration');
    const decRequestChangesInput = document.getElementById('decRequestChangesInput');
    const decNotesInput = document.getElementById('decNotesInput');
    const btnConfirmRequestChanges = document.getElementById('btnConfirmRequestChanges');
    const btnCancelRequestChanges = document.getElementById('btnCancelRequestChanges');
    
    // Tab 3 & 4
    const documentsContainer = document.getElementById('documentsContainer');
    const docSummaryCount = document.getElementById('docSummaryCount');
    const auditTimelineContainer = document.getElementById('auditTimelineContainer');
    
    let currentJoineeId = null;

    // Helper functions
    const getBaseUrl = () => window.BASE_URL || localStorage.getItem('BASE_URL') || '';
    const getHeaders = () => ({
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token') || ''}`
    });

    const getStatusBadgeHtml = (status) => {
        const s = (status || '').toUpperCase();
        let color = 'secondary';
        if (s === 'PENDING' || s === 'DRAFT') color = 'warning';
        else if (s === 'APPROVED' || s === 'VERIFIED') color = 'success';
        else if (s === 'CHANGES_REQUESTED' || s === 'REJECTED') color = 'danger';
        else if (s === 'SUBMITTED') color = 'primary';
        return `<span class="badge bg-${color}">${status || 'N/A'}</span>`;
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return 'N/A';
        const d = new Date(dateStr);
        return isNaN(d) ? dateStr : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };

    const formatDateTime = (dateStr) => {
        if (!dateStr) return 'N/A';
        const d = new Date(dateStr);
        return isNaN(d) ? dateStr : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' });
    };

    // Close Panel
    const closePanel = () => {
        reviewPanel.classList.remove('open');
        reviewPanelOverlay.classList.add('d-none');
        currentJoineeId = null;
    };

    btnCloseReviewPanel.addEventListener('click', closePanel);
    reviewPanelOverlay.addEventListener('click', closePanel);

    // Tab Switching
    tabButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            tabButtons.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            tabContents.forEach(c => c.classList.add('d-none'));
            document.getElementById(e.target.dataset.target).classList.remove('d-none');
        });
    });

    // Copy Person ID
    btnCopyReviewId.addEventListener('click', () => {
        navigator.clipboard.writeText(reviewPersonId.textContent).then(() => {
            const icon = btnCopyReviewId.querySelector('i');
            icon.className = 'bi bi-check';
            setTimeout(() => icon.className = 'bi bi-clipboard', 2000);
        });
    });

    // Open Panel Function
    window.openPanel = async (joineeId) => {
        currentJoineeId = joineeId;
        
        // Reset UI
        reviewPanelOverlay.classList.remove('d-none');
        reviewPanel.classList.add('open');
        reviewContentArea.classList.add('d-none');
        reviewSpinner.classList.remove('d-none');
        verifiedBanner.classList.add('d-none');
        
        tabButtons.forEach(b => b.classList.remove('active'));
        tabButtons[0].classList.add('active');
        tabContents.forEach(c => c.classList.add('d-none'));
        document.getElementById('tabJoineeInfo').classList.remove('d-none');

        try {
            const res = await fetch(`${getBaseUrl()}/onboarding/joinees/${joineeId}/summary`, { headers: getHeaders() });
            const rawData = await res.json();
            console.log("Summary API response:", rawData);
            
            if (rawData.success === false && rawData.error) {
                alert(`Error: ${rawData.error}`);
                closePanel();
                return;
            }

            // Handle various response wrappers
            const data = rawData.data || rawData;
            
            if (data.joinee || rawData.success || data.id) {
                // If the backend returns flat joinee data without a 'joinee' wrapper
                if (!data.joinee && data.id) {
                    renderPanelData({ joinee: data, declaration: {}, documents: [], audit_logs: [] });
                } else {
                    renderPanelData(data);
                }
                reviewContentArea.classList.remove('d-none');
            } else {
                alert('Failed to load joinee details. Check console for response format.');
                closePanel();
            }
        } catch (err) {
            console.error(err);
            alert('An error occurred while fetching joinee data.');
            closePanel();
        } finally {
            reviewSpinner.classList.add('d-none');
        }
    };

    const renderPanelData = (data) => {
        const joinee = data.joinee || {};
        const dec = data.declaration || {};
        const docs = data.documents || [];
        const logs = data.audit_logs || [];

        // Tab 1: Joinee Info
        reviewFullName.textContent = joinee.full_name || joinee.name || 'N/A';
        reviewPhone.textContent = joinee.phone || 'N/A';
        reviewPersonalEmail.textContent = joinee.personal_email || joinee.email || 'N/A';
        reviewCompanyEmail.value = joinee.company_email || '';
        reviewJoiningDate.textContent = formatDate(joinee.joining_date || joinee.date_of_joining);
        reviewRole.textContent = joinee.assigned_role || joinee.role || 'N/A';
        reviewDepartment.textContent = joinee.assigned_department || joinee.department || 'N/A';
        reviewStatusBadge.innerHTML = getStatusBadgeHtml(joinee.onboarding_status || joinee.status);
        reviewPersonId.textContent = joinee.person_id || 'N/A';

        // Tab 2: Declaration Form
        decStatusBadge.innerHTML = getStatusBadgeHtml(dec.status || 'NOT STARTED');
        declarationGrid.innerHTML = '';
        
        if (dec.status === 'APPROVED') {
            decApprovedBanner.classList.remove('d-none');
        } else {
            decApprovedBanner.classList.add('d-none');
        }

        if (dec.hr_notes) {
            decHrNotesBox.classList.remove('d-none');
            decHrNotesText.textContent = dec.hr_notes;
        } else {
            decHrNotesBox.classList.add('d-none');
        }

        // Render declaration fields dynamically
        let decData = dec.data || dec.form_data || dec.fields || dec.details;
        
        // If data is directly on the declaration object, copy it and remove known metadata
        if (!decData && Object.keys(dec).length > 0) {
            decData = { ...dec };
            ['id', 'joinee_id', 'status', 'hr_notes', 'created_at', 'updated_at'].forEach(k => delete decData[k]);
        }
        
        decData = decData || {};

        if (typeof decData === 'string') {
            try { decData = JSON.parse(decData); } catch (e) { decData = { 'Raw Data': decData }; }
        }

        const renderValue = (val) => {
            if (val === null || val === undefined || val === '') return '-';
            if (typeof val !== 'object') return String(val);
            
            // If it's an array
            if (Array.isArray(val)) {
                if (val.length === 0) return '-';
                return `<div class="d-flex flex-column gap-2 mt-1">` + val.map((item, idx) => `
                    <div class="p-2 bg-light rounded border">
                        <div class="fw-bold text-secondary mb-1" style="font-size: 0.75rem;">ITEM ${idx + 1}</div>
                        ${renderValue(item)}
                    </div>
                `).join('') + `</div>`;
            }
            
            // If it's an object
            return `<div class="w-100 mt-1">` + Object.entries(val).map(([k, v]) => `
                <div class="d-flex justify-content-between border-bottom border-light pb-1 mb-1">
                    <span class="text-muted small me-3">${String(k).replace(/_/g, ' ')}</span>
                    <span class="text-dark small text-end text-break">${renderValue(v)}</span>
                </div>
            `).join('') + `</div>`;
        };

        if (Object.keys(decData).length > 0) {
            let flatFields = {};
            
            for (const [key, value] of Object.entries(decData)) {
                if (typeof value === 'object' && value !== null) {
                    const sectionHtml = `
                        <div class="dec-section mb-4">
                            <h6 class="text-secondary border-bottom pb-2 mb-2 text-uppercase" style="font-size: 0.85rem; font-weight: 600; letter-spacing: 0.5px;">${String(key).replace(/_/g, ' ')}</h6>
                            ${renderValue(value)}
                        </div>
                    `;
                    declarationGrid.insertAdjacentHTML('beforeend', sectionHtml);
                } else {
                    flatFields[key] = value;
                }
            }
            
            if (Object.keys(flatFields).length > 0) {
                 const sectionHtml = `
                     <div class="dec-section mb-4">
                         <h6 class="text-secondary border-bottom pb-2 mb-2 text-uppercase" style="font-size: 0.85rem; font-weight: 600; letter-spacing: 0.5px;">Details</h6>
                         ${Object.entries(flatFields).map(([k, v]) => `
                             <div class="dec-row d-flex justify-content-between align-items-center mb-2">
                                 <div class="fw-medium text-muted small">${String(k).replace(/_/g, ' ')}</div>
                                 <div class="text-dark small text-end text-break ms-3">${renderValue(v)}</div>
                             </div>
                         `).join('')}
                     </div>
                 `;
                 declarationGrid.insertAdjacentHTML('afterbegin', sectionHtml);
            }
        } else {
            declarationGrid.innerHTML = '<div class="text-muted small">No declaration data submitted yet.</div>';
        }

        // Action buttons
        decActionButtons.classList.add('d-none');
        decRequestChangesInput.classList.add('d-none');
        document.getElementById('decPrimaryButtons').classList.remove('d-none');
        
        if (dec.status === 'SUBMITTED') {
            decActionButtons.classList.remove('d-none');
        }

        // Tab 3: Documents
        documentsContainer.innerHTML = '';
        let approvedCount = 0;
        
        if (docs.length === 0) {
            documentsContainer.innerHTML = '<div class="text-muted small">No documents uploaded yet.</div>';
        } else {
            docs.forEach(doc => {
                if (doc.verification_status === 'APPROVED') approvedCount++;
                const isPending = doc.verification_status === 'PENDING';
                const statusClass = doc.verification_status ? `status-${doc.verification_status.toLowerCase()}` : '';
                
                documentsContainer.insertAdjacentHTML('beforeend', `
                    <div class="doc-card ${statusClass}">
                        <div>
                            <div class="d-flex align-items-center gap-2 mb-1">
                                <h6 class="mb-0 text-dark">${doc.document_type || 'Document'}</h6>
                                ${getStatusBadgeHtml(doc.verification_status)}
                            </div>
                            <div class="text-muted small mb-2">${doc.document_label || 'No description'}</div>
                            <div class="text-muted" style="font-size: 0.7rem;">Uploaded: ${formatDateTime(doc.uploaded_at)}</div>
                            ${doc.rejection_reason ? `<div class="text-danger mt-1" style="font-size: 0.75rem;">Reason: ${doc.rejection_reason}</div>` : ''}
                        </div>
                        <div class="d-flex flex-column gap-2 text-end">
                            <a href="/onboarding/documents/${doc.id}/view" target="_blank" class="btn btn-sm btn-outline-primary">
                                <i class="bi bi-box-arrow-up-right me-1"></i> View
                            </a>
                            ${isPending ? `
                                <div class="d-flex gap-1 mt-2">
                                    <button class="btn btn-sm btn-success btn-approve-doc" data-id="${doc.id}">Approve</button>
                                    <button class="btn btn-sm btn-danger btn-reject-doc" data-id="${doc.id}">Reject</button>
                                </div>
                                <div class="d-none mt-1" id="rejectInput_${doc.id}">
                                    <input type="text" class="form-control form-control-sm mb-1 doc-reject-reason" placeholder="Reason...">
                                    <button class="btn btn-sm btn-warning btn-confirm-reject-doc" data-id="${doc.id}">Confirm</button>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                `);
            });
        }
        
        docSummaryCount.textContent = `${approvedCount} of ${docs.length} approved`;

        // Tab 4: Audit Log
        auditTimelineContainer.innerHTML = '';
        if (logs.length === 0) {
            auditTimelineContainer.innerHTML = '<div class="text-muted small ms-2">No activity recorded.</div>';
        } else {
            logs.forEach(log => {
                auditTimelineContainer.insertAdjacentHTML('beforeend', `
                    <div class="audit-item">
                        <div class="audit-action">${log.action ? log.action.replace(/_/g, ' ') : 'Action Taken'}</div>
                        <div class="audit-meta">${formatDateTime(log.timestamp || log.created_at)} &bull; ${log.performed_by_name || log.performed_by || 'System'}</div>
                        ${log.notes ? `<div class="audit-notes">${log.notes}</div>` : ''}
                    </div>
                `);
            });
        }

        checkFullyVerified(dec.status, approvedCount, docs.length);
    };

    const checkFullyVerified = (decStatus, approvedDocs, totalDocs) => {
        if (decStatus === 'APPROVED' && totalDocs > 0 && approvedDocs === totalDocs) {
            verifiedBanner.classList.remove('d-none');
        } else {
            verifiedBanner.classList.add('d-none');
        }
    };

    // Declaration Actions
    btnRequestChanges.addEventListener('click', () => {
        document.getElementById('decPrimaryButtons').classList.add('d-none');
        decRequestChangesInput.classList.remove('d-none');
        decRequestChangesInput.classList.add('d-flex');
    });

    btnCancelRequestChanges.addEventListener('click', () => {
        document.getElementById('decPrimaryButtons').classList.remove('d-none');
        decRequestChangesInput.classList.add('d-none');
        decRequestChangesInput.classList.remove('d-flex');
        decNotesInput.value = '';
    });

    btnConfirmRequestChanges.addEventListener('click', async () => {
        const notes = decNotesInput.value.trim();
        if (!notes) return alert('Please enter a reason for requesting changes.');
        
        try {
            const res = await fetch(`${getBaseUrl()}/onboarding/declaration/${currentJoineeId}/review`, {
                method: 'PUT',
                headers: getHeaders(),
                body: JSON.stringify({ status: 'CHANGES_REQUESTED', hr_notes: notes })
            });
            const data = await res.json();
            if (data.success) window.openPanel(currentJoineeId); // reload panel
            else alert(data.error || 'Failed to update declaration.');
        } catch (e) {
            console.error(e);
            alert('Network error.');
        }
    });

    btnApproveDeclaration.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to approve this declaration?')) return;
        try {
            const res = await fetch(`${getBaseUrl()}/onboarding/declaration/${currentJoineeId}/review`, {
                method: 'PUT',
                headers: getHeaders(),
                body: JSON.stringify({ status: 'APPROVED' })
            });
            const data = await res.json();
            if (data.success) window.openPanel(currentJoineeId); // reload panel
            else alert(data.error || 'Failed to approve declaration.');
        } catch (e) {
            console.error(e);
            alert('Network error.');
        }
    });

    // Document Actions
    documentsContainer.addEventListener('click', async (e) => {
        if (e.target.closest('.btn-approve-doc')) {
            const id = e.target.closest('.btn-approve-doc').dataset.id;
            try {
                const res = await fetch(`${getBaseUrl()}/onboarding/documents/${id}/verify`, {
                    method: 'PUT',
                    headers: getHeaders(),
                    body: JSON.stringify({ verification_status: 'APPROVED' })
                });
                if (res.ok) window.openPanel(currentJoineeId);
                else alert('Failed to approve document.');
            } catch (err) { alert('Network error'); }
        }
        
        if (e.target.closest('.btn-reject-doc')) {
            const id = e.target.closest('.btn-reject-doc').dataset.id;
            const rejectInput = document.getElementById(`rejectInput_${id}`);
            e.target.closest('div').classList.add('d-none');
            rejectInput.classList.remove('d-none');
            rejectInput.classList.add('d-flex');
        }

        if (e.target.closest('.btn-confirm-reject-doc')) {
            const id = e.target.closest('.btn-confirm-reject-doc').dataset.id;
            const container = document.getElementById(`rejectInput_${id}`);
            const input = container.querySelector('.doc-reject-reason');
            if (!input.value.trim()) return alert('Please enter a rejection reason.');
            
            try {
                const res = await fetch(`${getBaseUrl()}/onboarding/documents/${id}/verify`, {
                    method: 'PUT',
                    headers: getHeaders(),
                    body: JSON.stringify({ verification_status: 'REJECTED', rejection_reason: input.value.trim() })
                });
                if (res.ok) window.openPanel(currentJoineeId);
                else alert('Failed to reject document.');
            } catch (err) { alert('Network error'); }
        }
    });

    // ---- Login Migration Logic ----
    const migrationModal = document.getElementById('migration-modal');
    const migrationPersonalEmail = document.getElementById('migration-personal-email');
    const migrationCompanyEmailInput = document.getElementById('migration-company-email-input');
    const radioPersonal = document.getElementById('radio-personal');
    const radioCompany = document.getElementById('radio-company');
    const radioPersonalVal = document.getElementById('migration-radio-personal-val');
    const radioCompanyVal = document.getElementById('migration-radio-company-val');
    const migrationErrorBanner = document.getElementById('migration-error-banner');
    const migrationSuccessBanner = document.getElementById('migration-success-banner');
    const migrationConfirmBtn = document.getElementById('migration-confirm-btn');
    const migrationBtnText = document.getElementById('migration-btn-text');
    const migrationBtnSpinner = document.getElementById('migration-btn-spinner');
    const migrationCreateTeamBtn = document.getElementById('migration-create-team-btn');

    let currentMigrationEmail = '';

    if (btnProceedMigration) {
        btnProceedMigration.addEventListener('click', () => {
            // Populate modal data
            currentMigrationEmail = reviewPersonalEmail.textContent.trim();
            migrationPersonalEmail.textContent = currentMigrationEmail;
            radioPersonalVal.textContent = currentMigrationEmail;
            
            migrationCompanyEmailInput.value = reviewCompanyEmail.value.trim();
            updateCompanyRadio();
            
            // Reset state
            radioPersonal.checked = true;
            migrationErrorBanner.classList.add('d-none');
            migrationSuccessBanner.classList.add('d-none');
            migrationConfirmBtn.classList.remove('d-none');
            migrationCreateTeamBtn.classList.add('d-none');
            migrationConfirmBtn.disabled = false;
            
            // Close panel and show modal
            closePanel();
            migrationModal.classList.remove('d-none');
        });
    }

    const updateCompanyRadio = () => {
        const val = migrationCompanyEmailInput.value.trim();
        if (val) {
            radioCompany.disabled = false;
            radioCompanyVal.textContent = val;
            radioCompanyVal.classList.remove('text-muted', 'fst-italic');
        } else {
            radioCompany.disabled = true;
            radioCompanyVal.textContent = 'enter above';
            radioCompanyVal.classList.add('text-muted', 'fst-italic');
            radioPersonal.checked = true;
        }
    };

    if (migrationCompanyEmailInput) {
        migrationCompanyEmailInput.addEventListener('input', updateCompanyRadio);
    }

    const closeMigrationModal = () => {
        migrationModal.classList.add('d-none');
    };

    document.getElementById('migration-modal-close')?.addEventListener('click', closeMigrationModal);
    document.getElementById('migration-cancel-btn')?.addEventListener('click', closeMigrationModal);
    migrationModal?.addEventListener('click', (e) => {
        if (e.target === migrationModal) closeMigrationModal();
    });

    if (migrationConfirmBtn) {
        migrationConfirmBtn.addEventListener('click', async () => {
            const companyEmail = migrationCompanyEmailInput.value.trim();
            let loginEmail = '';

            if (radioCompany.checked) {
                if (!companyEmail || !/^\S+@\S+\.\S+$/.test(companyEmail)) {
                    migrationErrorBanner.textContent = 'Please enter a valid company email, or select Personal Email.';
                    migrationErrorBanner.classList.remove('d-none');
                    return;
                }
                loginEmail = companyEmail;
            } else {
                loginEmail = currentMigrationEmail;
            }

            migrationErrorBanner.classList.add('d-none');
            migrationConfirmBtn.disabled = true;
            migrationBtnText.classList.add('d-none');
            migrationBtnSpinner.classList.remove('d-none');

            try {
                const res = await fetch(`${getBaseUrl()}/onboarding/joinees/${currentJoineeId}/migrate-login`, {
                    method: 'PUT',
                    headers: getHeaders(),
                    body: JSON.stringify({
                        login_email: loginEmail,
                        company_email: companyEmail || null
                    })
                });
                const data = await res.json();

                if (res.ok && data.success !== false) {
                    migrationConfirmBtn.classList.add('d-none');
                    migrationSuccessBanner.textContent = `Login updated. The joinee can now log in with ${loginEmail}`;
                    migrationSuccessBanner.classList.remove('d-none');
                    migrationCreateTeamBtn.classList.remove('d-none');
                    
                    // Refresh table if needed
                    if (typeof window.fetchJoinees === 'function') window.fetchJoinees();
                } else {
                    migrationErrorBanner.textContent = data.message || data.error || 'Failed to update login.';
                    migrationErrorBanner.classList.remove('d-none');
                    migrationConfirmBtn.disabled = false;
                }
            } catch (err) {
                console.error(err);
                migrationErrorBanner.textContent = 'Network error. Please try again.';
                migrationErrorBanner.classList.remove('d-none');
                migrationConfirmBtn.disabled = false;
            } finally {
                migrationBtnText.classList.remove('d-none');
                migrationBtnSpinner.classList.add('d-none');
            }
        });
    }

    if (migrationCreateTeamBtn) {
        migrationCreateTeamBtn.addEventListener('click', () => {
            window.location.href = `/team-members/add?prefill_joinee_id=${currentJoineeId}`;
        });
    }
});
