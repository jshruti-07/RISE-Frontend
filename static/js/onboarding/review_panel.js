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
            const data = await res.json();
            
            if (data.success || data.joinee) {
                renderPanelData(data);
                reviewContentArea.classList.remove('d-none');
            } else {
                alert('Failed to load joinee details.');
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
        const decData = dec.data || {};
        if (Object.keys(decData).length > 0) {
            for (const [sectionKey, sectionObj] of Object.entries(decData)) {
                if (typeof sectionObj === 'object' && sectionObj !== null) {
                    const sectionHtml = `
                        <div class="dec-section">
                            <h6>${sectionKey.replace(/_/g, ' ')}</h6>
                            ${Object.entries(sectionObj).map(([k, v]) => `
                                <div class="dec-row">
                                    <div class="fw-medium text-muted small">${k.replace(/_/g, ' ')}</div>
                                    <div class="text-dark small">${v || '-'}</div>
                                </div>
                            `).join('')}
                        </div>
                    `;
                    declarationGrid.insertAdjacentHTML('beforeend', sectionHtml);
                }
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
});
