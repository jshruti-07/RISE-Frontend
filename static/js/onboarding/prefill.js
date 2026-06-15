document.addEventListener('DOMContentLoaded', () => {
    const prefillInput = document.getElementById('prefill-joinee-id');
    const prefillBtn = document.getElementById('prefill-fetch-btn');
    const prefillSpinner = document.getElementById('prefill-spinner');
    const successBanner = document.getElementById('prefill-success-banner');
    const warningBanner = document.getElementById('prefill-warning-banner');
    const errorBanner = document.getElementById('prefill-error-banner');

    // Helper: Form Inputs
    const inputName = document.querySelector('input[name="name"]');
    const inputPhone = document.querySelector('input[name="phone"]');
    const inputEmail = document.querySelector('input[name="email"]');
    const inputDateOfJoining = document.querySelector('input[name="date_of_joining"]');
    const selectRole = document.querySelector('select[name="role"]');
    const selectDepartment = document.querySelector('select[name="department"]');
    const selectDesignation = document.querySelector('select[name="designation"]');

    // Helper: Auth Header
    const getHeaders = () => {
        const token = localStorage.getItem('token');
        return {
            'Authorization': token ? `Bearer ${token}` : '',
            'Content-Type': 'application/json'
        };
    };

    // Helper: Base URL
    const getBaseUrl = () => window.BASE_URL || localStorage.getItem('BASE_URL') || '';

    const fetchDetails = async (joineeId) => {
        if (!joineeId) return;

        // Reset UI
        prefillSpinner.classList.remove('d-none');
        prefillBtn.disabled = true;
        successBanner.classList.add('d-none');
        warningBanner.classList.add('d-none');
        errorBanner.classList.add('d-none');
        errorBanner.textContent = '';

        try {
            const res = await fetch(`${getBaseUrl()}/onboarding/joinees/${joineeId}/prefill`, {
                method: 'GET',
                headers: getHeaders()
            });

            if (res.status === 404) {
                errorBanner.textContent = 'No joinee found with this ID.';
                errorBanner.classList.remove('d-none');
                return;
            }

            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                errorBanner.textContent = data.message || data.error || 'Failed to fetch details.';
                errorBanner.classList.remove('d-none');
                return;
            }

            const data = await res.json();
            const joinee = data.joinee || data.data || data;

            // Map fields
            if (inputName && joinee.full_name) inputName.value = joinee.full_name;
            if (inputPhone && joinee.phone) inputPhone.value = joinee.phone;
            
            const activeEmail = joinee.active_login_email || joinee.company_email || joinee.personal_email;
            if (inputEmail && activeEmail) inputEmail.value = activeEmail;
            
            // Format date for <input type="date"> which requires YYYY-MM-DD
            if (inputDateOfJoining && joinee.joining_date) {
                try {
                    const d = new Date(joinee.joining_date);
                    if (!isNaN(d)) {
                        inputDateOfJoining.value = d.toISOString().split('T')[0];
                    }
                } catch (e) {}
            }

            // Map Selects (try to match value or text)
            const setSelectVal = (selectElem, val) => {
                if (!selectElem || !val) return;
                const vUpper = String(val).toUpperCase();
                for (let i = 0; i < selectElem.options.length; i++) {
                    const opt = selectElem.options[i];
                    if (opt.value.toUpperCase() === vUpper || opt.text.toUpperCase() === vUpper) {
                        selectElem.selectedIndex = i;
                        break;
                    }
                }
            };

            setSelectVal(selectRole, joinee.assigned_role);
            setSelectVal(selectDepartment, joinee.assigned_department);
            setSelectVal(selectDesignation, joinee.assigned_designation || joinee.assigned_role);

            // Banners
            successBanner.classList.remove('d-none');
            const status = (joinee.onboarding_status || '').toUpperCase();
            if (status !== 'VERIFIED') {
                warningBanner.classList.remove('d-none');
            }

        } catch (err) {
            console.error('Prefill error:', err);
            errorBanner.textContent = 'Network error. Please try again.';
            errorBanner.classList.remove('d-none');
        } finally {
            prefillSpinner.classList.add('d-none');
            prefillBtn.disabled = false;
        }
    };

    // Auto-fetch if ID in URL
    const params = new URLSearchParams(window.location.search);
    const idParam = params.get('prefill_joinee_id');
    if (idParam) {
        if (prefillInput) prefillInput.value = idParam;
        fetchDetails(idParam);
    }

    if (prefillBtn && prefillInput) {
        prefillBtn.addEventListener('click', () => {
            const val = prefillInput.value.trim();
            if (val) fetchDetails(val);
        });
        
        prefillInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const val = prefillInput.value.trim();
                if (val) fetchDetails(val);
            }
        });
    }
});
