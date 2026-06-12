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
                console.warn('Failed to fetch stats:', await response.text());
            }
        } catch (err) {
            console.error('Error fetching stats:', err);
        }
    };

    // Fetch Joinees
    const fetchJoinees = async () => {
        toggleLoading(true);
        try {
            const baseUrl = window.BASE_URL || localStorage.getItem('BASE_URL') || '';
            const url = new URL(baseUrl ? `${baseUrl}/onboarding/joinees` : '/onboarding/joinees', window.location.origin);
            url.searchParams.append('page', currentPage);
            url.searchParams.append('per_page', perPage);
            if (currentStatus) {
                url.searchParams.append('status', currentStatus);
            }

            const response = await fetch(url.toString(), { headers });
            if (!response.ok) {
                throw new Error('Failed to load joinees data');
            }

            const data = await response.json();
            const joinees = data.joinees || [];
            totalItems = data.total || 0;
            
            renderTable(joinees);
            updatePagination();
            
        } catch (err) {
            console.error(err);
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
                    <td colspan="5" class="text-center py-4 text-muted">
                        No joinees found matching the criteria.
                    </td>
                </tr>
            `;
            return;
        }

        joinees.forEach((joinee, index) => {
            const tr = document.createElement('tr');
            
            // Name column
            const name = joinee.name || 'Unknown Name';
            const email = joinee.email || 'No email provided';
            const initials = getInitials(name);
            const colorClass = `bg-color-${(index % 4) + 1}`;
            
            // Role
            const role = joinee.role || 'New Hire';
            const dept = joinee.department || 'General';
            
            // Dates
            const joinDate = formatDate(joinee.joining_date);
            
            // Status
            const statusInfo = getStatusBadgeInfo(joinee.status);
            
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
                    <button class="btn btn-sm btn-light text-primary" data-joinee-id="${joinee.id}" title="Edit / View">
                        <i class="bi bi-pencil-square"></i>
                    </button>
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

    // Initial Load
    fetchStats();
    fetchJoinees();
});
