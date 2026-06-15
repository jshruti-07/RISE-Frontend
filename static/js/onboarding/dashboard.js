document.addEventListener('DOMContentLoaded', () => {
    // 1. Check Auth Token & Role
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = '/login';
        return;
    }

    try {
        const payloadBase64 = token.split('.')[1];
        // base64 decode and parse JWT payload
        const payloadDecoded = JSON.parse(atob(payloadBase64.replace(/-/g, '+').replace(/_/g, '/')));
        if (!['admin', 'hr'].includes(payloadDecoded.role)) {
            window.location.href = '/login';
            return;
        }
    } catch (e) {
        console.error("Token parse error", e);
        window.location.href = '/login';
        return;
    }

    // State
    let currentPage = 1;
    const perPage = 10;
    let currentStatus = ''; // empty means all
    let totalItems = 0;

    // DOM Elements
    const statTotal = document.getElementById('statTotalJoinees');
    const statPending = document.getElementById('statPendingTasks');
    const statForms = document.getElementById('statFormsSubmitted');
    const statCleared = document.getElementById('statClearedToStart');
    
    const tableBody = document.getElementById('joineesTableBody');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const errorAlert = document.getElementById('errorAlert');
    
    const btnPrevPage = document.getElementById('btnPrevPage');
    const btnNextPage = document.getElementById('btnNextPage');
    const paginationInfo = document.getElementById('paginationInfo');
    
    const tabButtons = document.querySelectorAll('#onboardingTabs .nav-link');

    // Headers for fetch
    const headers = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };

    // Helper: Show/Hide Loading
    const toggleLoading = (show) => {
        if (show) loadingOverlay.classList.remove('d-none');
        else loadingOverlay.classList.add('d-none');
    };

    // Helper: Show Error
    const showError = (msg) => {
        errorAlert.textContent = msg;
        errorAlert.classList.remove('d-none');
        setTimeout(() => {
            errorAlert.classList.add('d-none');
        }, 5000);
    };

    // Helper: Format Date
    const formatDate = (dateStr) => {
        if (!dateStr) return 'N/A';
        const d = new Date(dateStr);
        if (isNaN(d)) return dateStr;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    };

    // Helper: Get Initials
    const getInitials = (name) => {
        if (!name) return '?';
        const parts = name.split(' ').filter(n => n);
        if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
        return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
    };

    // Helper: Badge Classes & Labels
    const getStatusBadgeInfo = (status) => {
        const s = (status || '').toLowerCase();
        if (s === 'pending') return { class: 'badge-pending', label: 'Pending' };
        if (s === 'documents_submitted') return { class: 'badge-submitted', label: 'Forms Submitted' };
        if (s === 'changes_requested') return { class: 'badge-changes', label: 'Changes Requested' };
        if (s === 'verified') return { class: 'badge-verified', label: 'Verified' };
        return { class: 'badge-pending', label: status || 'Unknown' };
    };

    // Fetch Stats
    const fetchStats = async () => {
        try {
            const baseUrl = window.BASE_URL || localStorage.getItem('BASE_URL') || '';
            const url = baseUrl ? `${baseUrl}/onboarding/stats` : '/onboarding/stats';
            const response = await fetch(url, { headers });
            
            if (response.ok) {
                const data = await response.json();
                statTotal.textContent = data.total_joinees || 0;
                statPending.textContent = data.pending_tasks || 0;
                statForms.textContent = data.forms_submitted || 0;
                statCleared.textContent = data.cleared_to_start || 0;
            } else {
                console.warn('Failed to fetch stats, deriving from current list...');
            }
        } catch (err) {
            console.error('Error fetching stats:', err);
        }
    };

    let currentJoineesList = [];

    // Fetch Joinees
    const fetchJoinees = async () => {
        toggleLoading(true);
        errorAlert.classList.add('d-none');
        try {
            const baseUrl = window.BASE_URL || localStorage.getItem('BASE_URL') || '';
            const url = new URL(baseUrl ? `${baseUrl}/onboarding/joinees` : '/onboarding/joinees', window.location.origin);
            url.searchParams.append('page', currentPage);
            url.searchParams.append('per_page', perPage);
            url.searchParams.append('_t', Date.now()); // cache buster
            if (currentStatus) {
                url.searchParams.append('status', currentStatus);
            }

            const response = await fetch(url.toString(), { headers, cache: 'no-store' });
            
            if (!response.ok) {
                let errMsg = `HTTP ${response.status}`;
                try {
                    const errData = await response.json();
                    console.error('Joinees fetch error body:', errData);
                    errMsg = errData.error || errData.message || errMsg;
                } catch (_) {}
                throw new Error(errMsg);
            }

            const data = await response.json();
            console.log('Joinees response:', data);
            
            currentJoineesList = data.data || data.joinees || data.items || (Array.isArray(data) ? data : []);
            totalItems = data.total || data.total_items || currentJoineesList.length;
            
            // Fallback stats update
            statTotal.textContent = totalItems;
            
            let pendingCount = 0;
            let formCount = 0;
            let clearedCount = 0;
            currentJoineesList.forEach(j => {
                const s = (j.onboarding_status || j.status || '').toUpperCase();
                if (s === 'PENDING') pendingCount++;
                if (s === 'DOCUMENTS_SUBMITTED') formCount++;
                if (s === 'VERIFIED') clearedCount++;
            });
            statPending.textContent = pendingCount;
            statForms.textContent = formCount;
            statCleared.textContent = clearedCount;

            renderTable(currentJoineesList);
            updatePagination();
            
        } catch (err) {
            console.error('fetchJoinees error:', err);
            showError(err.message || 'Error loading data.');
            renderTable([]);
        } finally {
            toggleLoading(false);
        }
    };

    // Render Table
    const renderTable = (joinees) => {
        tableBody.innerHTML = '';
        
        if (!joinees || joinees.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="5">
                        <div class="onboarding-empty">
                            <i class="bi bi-person-lines-fill"></i>
                            <h6>No joinees found</h6>
                            <p class="mb-0 small">No team members match the selected filter. Create a new joinee to get started.</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        joinees.forEach((joinee, index) => {
            const tr = document.createElement('tr');
            
            // Name column
            const name = joinee.full_name || joinee.name || 'Unknown Name';
            const email = joinee.personal_email || joinee.email || 'No email provided';
            const initials = getInitials(name);
            const colorClass = `bg-color-${(index % 4) + 1}`;
            
            // Role
            const role = joinee.assigned_role || joinee.role || 'New Hire';
            const dept = joinee.assigned_department || joinee.department || 'General';
            
            // Dates
            const joinDate = formatDate(joinee.joining_date);
            
            // Status
            const statusInfo = getStatusBadgeInfo(joinee.onboarding_status || joinee.status);
            const isVerified = (joinee.onboarding_status || joinee.status || '').toLowerCase() === 'verified';
            
            tr.innerHTML = `
                <td>
                    <div class="d-flex align-items-center gap-3">
                        <div class="avatar-initials ${colorClass}">
                            ${initials}
                        </div>
                        <div>
                            <div class="fw-semibold text-dark">${name}</div>
                            <div class="text-muted" style="font-size: 0.8rem;">${email}</div>
                        </div>
                    </div>
                </td>
                <td>
                    <div class="fw-medium">${role}</div>
                    <div class="text-muted" style="font-size: 0.8rem;">${dept}</div>
                </td>
                <td>${joinDate}</td>
                <td>
                    <span class="badge-status ${statusInfo.class}">${statusInfo.label}</span>
                </td>
                <td class="text-end">
                    <div class="d-inline-flex align-items-center gap-2">
                        <button class="onboarding-action-btn" data-joinee-id="${joinee.id}" title="Edit / View">
                            <i class="bi bi-pencil-square"></i>
                        </button>
                        <button
                            class="onboarding-action-btn btn-delete ${isVerified ? 'btn-disabled' : ''}"
                            data-joinee-id="${joinee.id}"
                            data-joinee-name="${name}"
                            data-joinee-status="${joinee.onboarding_status || joinee.status || ''}"
                            title="${isVerified ? 'Cannot delete a verified joinee' : 'Delete Joinee'}"
                            ${isVerified ? 'disabled' : ''}>
                            <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" fill="currentColor" viewBox="0 0 16 16">
                                <path d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"/>
                                <path fill-rule="evenodd" d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4H4.118zM2.5 3V2h11v1h-11z"/>
                            </svg>
                        </button>
                    </div>
                </td>
            `;
            tableBody.appendChild(tr);
        });
    };

    // Pagination
    const updatePagination = () => {
        const totalPages = Math.ceil(totalItems / perPage);
        const start = ((currentPage - 1) * perPage) + 1;
        const end = Math.min(currentPage * perPage, totalItems);
        
        if (totalItems === 0) {
            paginationInfo.textContent = 'Showing 0 to 0 of 0 entries';
        } else {
            paginationInfo.textContent = `Showing ${start} to ${end} of ${totalItems} entries`;
        }
        
        btnPrevPage.disabled = currentPage <= 1;
        btnNextPage.disabled = currentPage >= totalPages || totalPages === 0;
    };

    btnPrevPage.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            fetchJoinees();
        }
    });

    btnNextPage.addEventListener('click', () => {
        const totalPages = Math.ceil(totalItems / perPage);
        if (currentPage < totalPages) {
            currentPage++;
            fetchJoinees();
        }
    });

    // Tab Clicks
    tabButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            // Remove active from all
            tabButtons.forEach(b => b.classList.remove('active'));
            // Add to clicked
            const clicked = e.currentTarget;
            clicked.classList.add('active');
            
            // Update status and fetch
            currentStatus = clicked.dataset.status || '';
            currentPage = 1; // reset page
            fetchJoinees();
        });
    });

    // Table Action Click Delegation (Edit + Delete)
    tableBody.addEventListener('click', (e) => {
        // Edit button
        const editBtn = e.target.closest('.onboarding-action-btn:not(.btn-delete)');
        if (editBtn && editBtn.dataset.joineeId) {
            const joineeId = editBtn.dataset.joineeId;
            if (typeof window.openPanel === 'function') {
                window.openPanel(joineeId);
            } else {
                console.warn('openPanel is not defined. Ensure review_panel.js is loaded.');
            }
            return;
        }

        // Delete button
        const deleteBtn = e.target.closest('.btn-delete:not(.btn-disabled)');
        if (deleteBtn && deleteBtn.dataset.joineeId) {
            openDeleteModal(
                deleteBtn.dataset.joineeId,
                deleteBtn.dataset.joineeName,
                deleteBtn.dataset.joineeStatus
            );
        }
    });

    // ---- Delete Modal Logic ----
    function openDeleteModal(joineeId, joineeName, status) {
        document.getElementById('delete-joinee-name').textContent = joineeName;
        document.getElementById('delete-error-banner').classList.add('d-none');
        document.getElementById('delete-error-banner').textContent = '';
        document.getElementById('delete-confirm-btn').dataset.joineeId = joineeId;
        document.getElementById('delete-btn-text').classList.remove('d-none');
        document.getElementById('delete-btn-spinner').classList.add('d-none');
        document.getElementById('delete-confirm-btn').disabled = false;
        // Show modal
        document.getElementById('delete-modal').classList.remove('d-none');
    }

    function closeDeleteModal() {
        document.getElementById('delete-modal').classList.add('d-none');
        document.getElementById('delete-btn-text').classList.remove('d-none');
        document.getElementById('delete-btn-spinner').classList.add('d-none');
        document.getElementById('delete-confirm-btn').disabled = false;
    }

    document.getElementById('delete-modal-close').addEventListener('click', closeDeleteModal);
    document.getElementById('delete-cancel-btn').addEventListener('click', closeDeleteModal);
    document.getElementById('delete-modal').addEventListener('click', function(e) {
        if (e.target === this) closeDeleteModal();
    });

    document.getElementById('delete-confirm-btn').addEventListener('click', async function () {
        const joineeId = this.dataset.joineeId;
        const token = localStorage.getItem('token');
        const baseUrl = getBaseUrl ? getBaseUrl() : (window.BASE_URL || '');

        // Show loading
        document.getElementById('delete-btn-text').classList.add('d-none');
        document.getElementById('delete-btn-spinner').classList.remove('d-none');
        this.disabled = true;

        try {
            const res = await fetch(`${baseUrl}/onboarding/joinees/${joineeId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
            });
            const data = await res.json();

            if (res.ok && data.success !== false) {
                closeDeleteModal();
                showToast('Joinee deleted successfully.', 'success');
                currentPage = 1;
                fetchJoinees();
                fetchStats();
            } else {
                const banner = document.getElementById('delete-error-banner');
                banner.textContent = data.message || data.error || 'Failed to delete joinee.';
                banner.classList.remove('d-none');
                document.getElementById('delete-btn-text').classList.remove('d-none');
                document.getElementById('delete-btn-spinner').classList.add('d-none');
                this.disabled = false;
            }
        } catch (err) {
            const banner = document.getElementById('delete-error-banner');
            banner.textContent = 'Network error. Please try again.';
            banner.classList.remove('d-none');
            document.getElementById('delete-btn-text').classList.remove('d-none');
            document.getElementById('delete-btn-spinner').classList.add('d-none');
            this.disabled = false;
        }
    });

    // Initial Load
    // Custom Modal Elements
    const btnCreateJoinee = document.getElementById('btnCreateJoinee');
    const customCreateJoineeModal = document.getElementById('customCreateJoineeModal');
    const btnCloseModal = document.getElementById('btnCloseModal');
    const btnCancelModal = document.getElementById('btnCancelModal');
    const btnDoneModal = document.getElementById('btnDoneModal');
    const modalFormPanel = document.getElementById('modalFormPanel');
    const modalSuccessPanel = document.getElementById('modalSuccessPanel');
    const createJoineeForm = document.getElementById('createJoineeForm');
    const modalAlert = document.getElementById('modalAlert');
    const btnSubmitJoinee = document.getElementById('btnSubmitJoinee');
    const submitSpinner = document.getElementById('submitSpinner');
    const btnSubmitText = document.getElementById('btnSubmitText');
    const btnTogglePassword = document.getElementById('btnTogglePassword');
    const joineePassword = document.getElementById('joineePassword');
    
    // Form Inputs
    const joineeFullName = document.getElementById('joineeFullName');
    const joineePhone = document.getElementById('joineePhone');
    const joineeEmail = document.getElementById('joineeEmail');
    const joineeDate = document.getElementById('joineeDate');
    const joineeRole = document.getElementById('joineeRole');
    const joineeDept = document.getElementById('joineeDept');
    
    // Error elements
    const errFullName = document.getElementById('errFullName');
    const errPhone = document.getElementById('errPhone');
    const errEmail = document.getElementById('errEmail');
    const errPassword = document.getElementById('errPassword');

    // Success elements
    const successDetails = document.getElementById('successDetails');
    const createdPersonId = document.getElementById('createdPersonId');
    const btnCopyPersonId = document.getElementById('btnCopyPersonId');

    // Password strength
    const strengthBar1 = document.getElementById('strengthBar1');
    const strengthBar2 = document.getElementById('strengthBar2');
    const strengthBar3 = document.getElementById('strengthBar3');
    const strengthText = document.getElementById('strengthText');

    const openModal = () => {
        createJoineeForm.reset();
        modalFormPanel.classList.remove('d-none');
        modalSuccessPanel.classList.add('d-none');
        modalAlert.classList.add('d-none');
        
        // Reset errors
        errFullName.classList.add('d-none');
        errPhone.classList.add('d-none');
        errEmail.classList.add('d-none');
        errPassword.classList.add('d-none');
        joineeFullName.classList.remove('is-invalid');
        joineePhone.classList.remove('is-invalid');
        joineeEmail.classList.remove('is-invalid');
        joineePassword.classList.remove('is-invalid');
        
        joineePassword.type = 'password';
        btnTogglePassword.innerHTML = '<i class="bi bi-eye"></i>';
        
        updatePasswordStrength('');
        
        customCreateJoineeModal.classList.remove('d-none');
    };

    const closeModal = () => {
        customCreateJoineeModal.classList.add('d-none');
    };

    btnCreateJoinee.addEventListener('click', openModal);
    btnCloseModal.addEventListener('click', closeModal);
    btnCancelModal.addEventListener('click', closeModal);
    
    // Close on click outside
    customCreateJoineeModal.addEventListener('click', (e) => {
        if (e.target === customCreateJoineeModal) {
            closeModal();
        }
    });

    // Password Toggle
    btnTogglePassword.addEventListener('click', () => {
        if (joineePassword.type === 'password') {
            joineePassword.type = 'text';
            btnTogglePassword.innerHTML = '<i class="bi bi-eye-slash"></i>';
        } else {
            joineePassword.type = 'password';
            btnTogglePassword.innerHTML = '<i class="bi bi-eye"></i>';
        }
    });

    // Password Strength
    const updatePasswordStrength = (val) => {
        strengthBar1.className = 'strength-bar';
        strengthBar2.className = 'strength-bar';
        strengthBar3.className = 'strength-bar';
        
        if (!val) {
            strengthText.textContent = 'Strength: Weak';
            return;
        }

        let score = 0;
        if (val.length > 7) score += 1;
        if (/[A-Z]/.test(val) && /[a-z]/.test(val)) score += 1;
        if (/[0-9]/.test(val) && /[^A-Za-z0-9]/.test(val)) score += 1;

        if (score === 0 || score === 1) {
            strengthBar1.classList.add('bg-danger');
            strengthText.textContent = 'Strength: Weak';
        } else if (score === 2) {
            strengthBar1.classList.add('bg-warning');
            strengthBar2.classList.add('bg-warning');
            strengthText.textContent = 'Strength: Medium';
        } else {
            strengthBar1.classList.add('bg-success');
            strengthBar2.classList.add('bg-success');
            strengthBar3.classList.add('bg-success');
            strengthText.textContent = 'Strength: Strong';
        }
    };

    joineePassword.addEventListener('input', (e) => updatePasswordStrength(e.target.value));

    // Submit Logic
    btnSubmitJoinee.addEventListener('click', async () => {
        // Validation
        let isValid = true;
        
        const fullName = joineeFullName.value.trim();
        if (fullName.length < 2) {
            errFullName.classList.remove('d-none');
            joineeFullName.classList.add('is-invalid');
            isValid = false;
        } else {
            errFullName.classList.add('d-none');
            joineeFullName.classList.remove('is-invalid');
        }

        const phone = joineePhone.value.trim();
        if (!phone) {
            errPhone.classList.remove('d-none');
            joineePhone.classList.add('is-invalid');
            isValid = false;
        } else {
            errPhone.classList.add('d-none');
            joineePhone.classList.remove('is-invalid');
        }

        const email = joineeEmail.value.trim();
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!email || !emailRegex.test(email)) {
            errEmail.classList.remove('d-none');
            joineeEmail.classList.add('is-invalid');
            isValid = false;
        } else {
            errEmail.classList.add('d-none');
            joineeEmail.classList.remove('is-invalid');
        }

        const pass = joineePassword.value;
        if (pass.length < 8) {
            errPassword.classList.remove('d-none');
            joineePassword.classList.add('is-invalid');
            isValid = false;
        } else {
            errPassword.classList.add('d-none');
            joineePassword.classList.remove('is-invalid');
        }

        if (!isValid) return;

        // Build Payload
        const payload = {
            full_name: fullName,
            name: fullName, // fallback for backend KeyError
            phone: phone,
            personal_email: email,
            email: email, // fallback for backend KeyError
            temp_password: pass,
            password: pass // fallback
        };
        
        if (joineeDate.value) {
            let dateStr = joineeDate.value;
            // Fallback for browsers returning MM/DD/YYYY from text inputs
            if (dateStr.includes('/')) {
                const parts = dateStr.split('/');
                if (parts.length === 3) {
                    dateStr = `${parts[2]}-${parts[0].padStart(2, '0')}-${parts[1].padStart(2, '0')}`;
                }
            }
            payload.joining_date = dateStr;
            payload.date_of_joining = dateStr; // fallback
        }
        
        if (joineeRole.value.trim()) {
            payload.assigned_role = joineeRole.value.trim();
            payload.role = joineeRole.value.trim(); // fallback
        }
        
        if (joineeDept.value.trim()) {
            payload.assigned_department = joineeDept.value.trim();
            payload.department = joineeDept.value.trim(); // fallback
        }

        // Submit
        btnSubmitJoinee.disabled = true;
        submitSpinner.classList.remove('d-none');
        btnSubmitText.textContent = 'Creating...';
        modalAlert.classList.add('d-none');

        try {
            const baseUrl = window.BASE_URL || localStorage.getItem('BASE_URL') || '';
            const url = baseUrl ? `${baseUrl}/onboarding/joinees` : '/onboarding/joinees';
            
            const response = await fetch(url, {
                method: 'POST',
                headers,
                body: JSON.stringify(payload)
            });

            if (response.status === 201) {
                const result = await response.json();
                const newId = result.person_id || 'PID-???';
                
                // Show success
                modalFormPanel.classList.add('d-none');
                modalSuccessPanel.classList.remove('d-none');
                
                successDetails.textContent = `${fullName} (${email})`;
                createdPersonId.textContent = newId;
            } else if (response.status === 409) {
                errEmail.textContent = 'This email is already registered.';
                errEmail.classList.remove('d-none');
                joineeEmail.classList.add('is-invalid');
            } else {
                const errData = await response.json().catch(() => ({}));
                modalAlert.textContent = errData.error || errData.message || 'Failed to create joinee.';
                modalAlert.classList.remove('d-none');
            }
        } catch (err) {
            console.error(err);
            modalAlert.textContent = 'A network error occurred.';
            modalAlert.classList.remove('d-none');
        } finally {
            btnSubmitJoinee.disabled = false;
            submitSpinner.classList.add('d-none');
            btnSubmitText.textContent = 'Create Joinee \u2192';
        }
    });

    btnCopyPersonId.addEventListener('click', () => {
        const idText = createdPersonId.textContent;
        navigator.clipboard.writeText(idText).then(() => {
            const icon = btnCopyPersonId.querySelector('i');
            icon.className = 'bi bi-check-lg text-success';
            setTimeout(() => {
                icon.className = 'bi bi-clipboard';
            }, 2000);
        });
    });

    btnDoneModal.addEventListener('click', () => {
        closeModal();
        fetchStats();
        fetchJoinees();
    });

    // Initial load
    fetchStats();
    fetchJoinees();
});
