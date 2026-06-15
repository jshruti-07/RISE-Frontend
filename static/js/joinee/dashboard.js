/**
 * static/js/joinee/dashboard.js
 * Joinee Onboarding Dashboard — Full vanilla JS
 */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // 1. AUTH GUARD
    // =========================================================
    const token = localStorage.getItem('token');
    if (!token) { window.location.href = '/login'; return; }

    let payload;
    try {
        const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
        payload = JSON.parse(atob(b64));
    } catch {
        window.location.href = '/login';
        return;
    }

    if (payload.role !== 'onboarding_candidate') {
        window.location.href = '/dashboard';
        return;
    }

    const BASE_URL = window.BASE_URL || '';
    const authHeaders = {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };

    // =========================================================
    // 2. ELEMENTS
    // =========================================================
    const pwGate       = document.getElementById('pwGate');
    const mainDash     = document.getElementById('mainDashboard');

    // =========================================================
    // 3. PROFILE FETCH & GATE LOGIC
    // =========================================================
    let profile = null;

    async function loadProfile() {
        try {
            const res = await fetch(`${BASE_URL}/auth/onboarding-profile`, { headers: authHeaders });
            if (!res.ok) { showFatalError('Failed to load your profile.'); return; }
            profile = await res.json();
        } catch {
            showFatalError('Network error loading your profile.');
            return;
        }

        // Update topbar name
        const nameEl = document.getElementById('topbarJoineeName');
        if (nameEl && profile.full_name) nameEl.textContent = profile.full_name;

        if (!profile.temp_password_changed) {
            pwGate.classList.remove('d-none');
        } else {
            mainDash.classList.remove('d-none');
            initMainDashboard();
        }
    }

    function showFatalError(msg) {
        document.body.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100vh;">
            <div style="text-align:center;"><p class="text-danger fw-bold">${msg}</p>
            <a href="/logout" class="btn btn-sm btn-outline-secondary">Logout</a></div></div>`;
    }

    // =========================================================
    // 4. CHANGE PASSWORD FLOW
    // =========================================================
    const changePasswordForm = document.getElementById('changePasswordForm');
    const pwAlert = document.getElementById('pwAlert');

    changePasswordForm && changePasswordForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const curr    = document.getElementById('currentPassword').value;
        const newPw   = document.getElementById('newPassword').value;
        const confirm = document.getElementById('confirmPassword').value;
        pwAlert.className = 'alert d-none mb-3';

        if (newPw !== confirm) {
            showPwAlert('Passwords do not match.', 'danger'); return;
        }
        if (newPw.length < 8) {
            showPwAlert('Password must be at least 8 characters.', 'danger'); return;
        }

        const btn = document.getElementById('btnChangePw');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving...';

        try {
            const res = await fetch(`${BASE_URL}/auth/change-password`, {
                method: 'POST',
                headers: authHeaders,
                body: JSON.stringify({ current_password: curr, new_password: newPw, confirm_password: confirm })
            });
            const data = await res.json();
            if (res.ok && (data.success !== false)) {
                if (data.token) localStorage.setItem('token', data.token);
                window.location.reload();
            } else {
                showPwAlert(data.error || data.message || 'Failed to change password.', 'danger');
            }
        } catch {
            showPwAlert('Network error. Please try again.', 'danger');
        } finally {
            btn.disabled = false;
            btn.innerHTML = 'Set Password & Continue';
        }
    });

    function showPwAlert(msg, type) {
        pwAlert.className = `alert alert-${type} mb-3`;
        pwAlert.textContent = msg;
    }

    // =========================================================
    // 5. MAIN DASHBOARD INIT
    // =========================================================
    function initMainDashboard() {
        renderDocumentCards();
        initYesNoConditionals();
        renderAcademicBlocks();
        renderEmploymentBlocks();
        renderReferenceRows();
        renderOnsiteRows();
        initSameAsCheckbox();
        initStepper();
        loadDeclaration();
        loadDocuments();
    }

    // =========================================================
    // 6. STEPPER
    // =========================================================
    let currentStep = 1;
    const totalSteps = 6;

    function initStepper() {
        document.querySelectorAll('.btn-nav-next').forEach(btn => {
            btn.addEventListener('click', async () => {
                const savingEl = document.getElementById(`autoSave${currentStep}`);
                if (savingEl) { savingEl.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Saving...'; }
                await autoSave();
                if (savingEl) { savingEl.innerHTML = '<i class="bi bi-check-circle text-success me-1"></i>Saved'; setTimeout(() => { savingEl.innerHTML = ''; }, 2000); }
                if (currentStep < totalSteps) goToStep(currentStep + 1);
            });
        });

        document.querySelectorAll('.btn-nav-prev').forEach(btn => {
            btn.addEventListener('click', () => {
                const target = parseInt(btn.dataset.target || currentStep - 1);
                if (target >= 1) goToStep(target);
            });
        });

        // Step 6: checkbox enables submit
        const chk = document.getElementById('authConfirmCheck');
        const submitBtn = document.getElementById('btnSubmitDeclaration');
        if (chk && submitBtn) {
            chk.addEventListener('change', () => { submitBtn.disabled = !chk.checked; });
            submitBtn.addEventListener('click', submitDeclaration);
        }
    }

    function goToStep(n) {
        document.querySelectorAll('.step-panel').forEach(p => p.classList.add('d-none'));
        document.getElementById(`step${n}`).classList.remove('d-none');

        document.querySelectorAll('.step-item').forEach(item => {
            const s = parseInt(item.dataset.step);
            item.classList.remove('active', 'completed');
            if (s < n) item.classList.add('completed');
            else if (s === n) item.classList.add('active');
        });

        currentStep = n;
        if (n === 6) buildReviewSummary();
    }

    // =========================================================
    // 7. DYNAMIC BLOCKS — Academic
    // =========================================================
    let academicCount = 1;
    const MAX_ACADEMIC = 3;

    function buildInstitutionBlock(idx) {
        const div = document.createElement('div');
        div.className = 'dynamic-block';
        div.dataset.idx = idx;
        div.innerHTML = `
            <div class="dynamic-block-header">
                <div class="dynamic-block-title">Institution ${idx}</div>
                ${idx > 1 ? `<button type="button" class="btn-remove-block" onclick="removeBlock(this, 'academic')"><i class="bi bi-trash me-1"></i>Remove</button>` : ''}
            </div>
            <div class="joinee-form-grid">
                <div><label class="form-label">Qualification</label><input type="text" class="form-control" name="ac_qual_${idx}" placeholder="B.Tech / MBA..."></div>
                <div><label class="form-label">Specialization</label><input type="text" class="form-control" name="ac_spec_${idx}" placeholder="Computer Science..."></div>
                <div><label class="form-label">College Name</label><input type="text" class="form-control" name="ac_college_${idx}"></div>
                <div><label class="form-label">Address</label><input type="text" class="form-control" name="ac_addr_${idx}"></div>
                <div><label class="form-label">University</label><input type="text" class="form-control" name="ac_univ_${idx}"></div>
                <div><label class="form-label">Period (From - To)</label><input type="text" class="form-control" name="ac_period_${idx}" placeholder="2016 - 2020"></div>
                <div class="full-width">
                    <label class="form-label">Program Type</label>
                    <div class="d-flex gap-3 mt-1">
                        <label class="d-flex align-items-center gap-2 fw-normal"><input type="radio" name="ac_prog_${idx}" value="Full Time"> Full Time</label>
                        <label class="d-flex align-items-center gap-2 fw-normal"><input type="radio" name="ac_prog_${idx}" value="Part Time"> Part Time</label>
                    </div>
                </div>
            </div>`;
        return div;
    }

    function renderAcademicBlocks() {
        const container = document.getElementById('academicBlocks');
        container.innerHTML = '';
        for (let i = 1; i <= academicCount; i++) {
            container.appendChild(buildInstitutionBlock(i));
        }
        updateAddBtn('btnAddInstitution', academicCount, MAX_ACADEMIC);
    }

    document.getElementById('btnAddInstitution') && document.getElementById('btnAddInstitution').addEventListener('click', () => {
        if (academicCount >= MAX_ACADEMIC) return;
        academicCount++;
        const container = document.getElementById('academicBlocks');
        container.appendChild(buildInstitutionBlock(academicCount));
        updateAddBtn('btnAddInstitution', academicCount, MAX_ACADEMIC);
    });

    // =========================================================
    // 8. DYNAMIC BLOCKS — Employment
    // =========================================================
    let employmentCount = 1;
    const MAX_EMPLOYMENT = 6;

    function buildEmploymentBlock(idx) {
        const div = document.createElement('div');
        div.className = 'dynamic-block';
        div.dataset.idx = idx;
        div.innerHTML = `
            <div class="dynamic-block-header">
                <div class="dynamic-block-title">Employment ${idx}${idx === 1 ? ' (Latest)' : ''}</div>
                ${idx > 1 ? `<button type="button" class="btn-remove-block" onclick="removeBlock(this, 'employment')"><i class="bi bi-trash me-1"></i>Remove</button>` : ''}
            </div>
            <div class="joinee-form-grid">
                <div><label class="form-label">Company Name</label><input type="text" class="form-control" name="emp_company_${idx}"></div>
                <div><label class="form-label">Employee ID</label><input type="text" class="form-control" name="emp_id_${idx}"></div>
                <div class="full-width"><label class="form-label">Address</label><input type="text" class="form-control" name="emp_addr_${idx}"></div>
                <div><label class="form-label">City</label><input type="text" class="form-control" name="emp_city_${idx}"></div>
                <div><label class="form-label">State</label><input type="text" class="form-control" name="emp_state_${idx}"></div>
                <div><label class="form-label">Date of Joining</label><input type="date" class="form-control" name="emp_doj_${idx}"></div>
                <div><label class="form-label">Last Working Day</label><input type="date" class="form-control" name="emp_lwd_${idx}"></div>
                <div><label class="form-label">Designation</label><input type="text" class="form-control" name="emp_desig_${idx}"></div>
                <div><label class="form-label">Remuneration</label><input type="text" class="form-control" name="emp_rem_${idx}" placeholder="e.g. 8 LPA"></div>
                <div><label class="form-label">Contact No. 1</label><input type="text" class="form-control" name="emp_contact1_${idx}"></div>
                <div><label class="form-label">Contact No. 2</label><input type="text" class="form-control" name="emp_contact2_${idx}"></div>
                <div><label class="form-label">Reported To (Name)</label><input type="text" class="form-control" name="emp_reported_name_${idx}"></div>
                <div><label class="form-label">Reported Person Designation</label><input type="text" class="form-control" name="emp_reported_desig_${idx}"></div>
                <div class="full-width"><label class="form-label">Reason for Leaving</label><textarea class="form-control" name="emp_reason_${idx}" rows="2"></textarea></div>
            </div>`;
        return div;
    }

    function renderEmploymentBlocks() {
        const container = document.getElementById('employmentBlocks');
        container.innerHTML = '';
        for (let i = 1; i <= employmentCount; i++) {
            container.appendChild(buildEmploymentBlock(i));
        }
        updateAddBtn('btnAddEmployment', employmentCount, MAX_EMPLOYMENT);
    }

    document.getElementById('btnAddEmployment') && document.getElementById('btnAddEmployment').addEventListener('click', () => {
        if (employmentCount >= MAX_EMPLOYMENT) return;
        employmentCount++;
        const container = document.getElementById('employmentBlocks');
        container.appendChild(buildEmploymentBlock(employmentCount));
        updateAddBtn('btnAddEmployment', employmentCount, MAX_EMPLOYMENT);
    });

    // =========================================================
    // 9. DYNAMIC BLOCKS — References
    // =========================================================
    let referenceCount = 3;
    const MAX_REFERENCES = 6;
    const MIN_REFERENCES = 3;

    function buildReferenceBlock(idx) {
        const div = document.createElement('div');
        div.className = 'dynamic-block';
        div.dataset.idx = idx;
        div.innerHTML = `
            <div class="dynamic-block-header">
                <div class="dynamic-block-title">Reference ${idx}</div>
                ${idx > MIN_REFERENCES ? `<button type="button" class="btn-remove-block" onclick="removeBlock(this, 'reference')"><i class="bi bi-trash me-1"></i>Remove</button>` : ''}
            </div>
            <div class="joinee-form-grid">
                <div><label class="form-label">Referral Name</label><input type="text" class="form-control" name="ref_name_${idx}"></div>
                <div><label class="form-label">Designation / Role</label><input type="text" class="form-control" name="ref_desig_${idx}"></div>
                <div><label class="form-label">Phone <span class="text-danger">*</span></label><input type="text" class="form-control" name="ref_phone_${idx}"></div>
                <div><label class="form-label">Email <span class="text-danger">*</span></label><input type="email" class="form-control" name="ref_email_${idx}"></div>
                <div><label class="form-label">Company Name (where you worked together)</label><input type="text" class="form-control" name="ref_company_${idx}"></div>
                <div><label class="form-label">Your Designation there</label><input type="text" class="form-control" name="ref_mydesig_${idx}"></div>
            </div>`;
        return div;
    }

    function renderReferenceRows() {
        const container = document.getElementById('referenceBlocks');
        container.innerHTML = '';
        for (let i = 1; i <= referenceCount; i++) {
            container.appendChild(buildReferenceBlock(i));
        }
        updateAddBtn('btnAddReference', referenceCount, MAX_REFERENCES);
    }

    document.getElementById('btnAddReference') && document.getElementById('btnAddReference').addEventListener('click', () => {
        if (referenceCount >= MAX_REFERENCES) return;
        referenceCount++;
        const container = document.getElementById('referenceBlocks');
        container.appendChild(buildReferenceBlock(referenceCount));
        updateAddBtn('btnAddReference', referenceCount, MAX_REFERENCES);
    });

    // =========================================================
    // 10. DYNAMIC ROWS — Onsite
    // =========================================================
    let onsiteRowCount = 0;
    const MAX_ONSITE = 7;

    function addOnsiteRow() {
        if (onsiteRowCount >= MAX_ONSITE) return;
        onsiteRowCount++;
        const idx = onsiteRowCount;
        const tbody = document.getElementById('onsiteTableBody');
        const tr = document.createElement('tr');
        tr.dataset.idx = idx;
        tr.innerHTML = `
            <td><input type="text" class="form-control" name="onsite_country_${idx}" placeholder="India"></td>
            <td><input type="text" class="form-control" name="onsite_visa_${idx}" placeholder="Work / Tourist"></td>
            <td><input type="text" class="form-control" name="onsite_duration_${idx}" placeholder="3 months"></td>
            <td><input type="text" class="form-control" name="onsite_purpose_${idx}" placeholder="Project work"></td>
            <td style="text-align:center;"><button type="button" class="btn-remove-block" onclick="removeOnsiteRow(this)"><i class="bi bi-trash"></i></button></td>`;
        tbody.appendChild(tr);
        updateAddBtn('btnAddOnsiteRow', onsiteRowCount, MAX_ONSITE);
    }

    function renderOnsiteRows() {
        // Start empty — user adds rows
        document.getElementById('btnAddOnsiteRow') && document.getElementById('btnAddOnsiteRow').addEventListener('click', addOnsiteRow);
    }

    window.removeOnsiteRow = function(btn) {
        btn.closest('tr').remove();
        onsiteRowCount = Math.max(0, onsiteRowCount - 1);
        // Re-index
        document.querySelectorAll('#onsiteTableBody tr').forEach((tr, i) => {
            tr.dataset.idx = i + 1;
            tr.querySelectorAll('input').forEach(inp => {
                const base = inp.name.replace(/_\d+$/, '');
                inp.name = `${base}_${i + 1}`;
            });
        });
        onsiteRowCount = document.querySelectorAll('#onsiteTableBody tr').length;
        updateAddBtn('btnAddOnsiteRow', onsiteRowCount, MAX_ONSITE);
    };

    // =========================================================
    // 11. GENERIC REMOVE BLOCK
    // =========================================================
    window.removeBlock = function(btn, type) {
        const block = btn.closest('.dynamic-block');
        const container = block.parentElement;
        block.remove();
        // Rebuild remaining
        const remaining = Array.from(container.querySelectorAll('.dynamic-block'));
        if (type === 'academic') {
            academicCount = remaining.length;
            renderAcademicBlocks();
        } else if (type === 'employment') {
            employmentCount = remaining.length;
            renderEmploymentBlocks();
        } else if (type === 'reference') {
            referenceCount = remaining.length;
            renderReferenceRows();
        }
    };

    function updateAddBtn(btnId, current, max) {
        const btn = document.getElementById(btnId);
        if (!btn) return;
        btn.disabled = current >= max;
        btn.style.opacity = current >= max ? '0.4' : '1';
    }

    // =========================================================
    // 12. SAME AS PERMANENT CHECKBOX
    // =========================================================
    function initSameAsCheckbox() {
        const chk = document.getElementById('sameAsPermanent');
        if (!chk) return;
        chk.addEventListener('change', () => {
            const copy = (fromId, toId) => { document.getElementById(toId).value = document.getElementById(fromId).value; };
            if (chk.checked) {
                copy('perm_address', 'curr_address');
                copy('perm_landmark', 'curr_landmark');
                copy('perm_landline', 'curr_landline');
                copy('perm_mobile', 'curr_mobile');
                copy('perm_period', 'curr_period');
                copy('perm_nature', 'curr_nature');
                // Mirror future changes
                const permIds = ['perm_address','perm_landmark','perm_landline','perm_mobile','perm_period','perm_nature'];
                const currIds = ['curr_address','curr_landmark','curr_landline','curr_mobile','curr_period','curr_nature'];
                permIds.forEach((pid, i) => {
                    const el = document.getElementById(pid);
                    el._mirrorListener = () => { if (chk.checked) document.getElementById(currIds[i]).value = el.value; };
                    el.addEventListener('input', el._mirrorListener);
                });
            } else {
                // Remove mirror listeners
                ['perm_address','perm_landmark','perm_landline','perm_mobile','perm_period','perm_nature'].forEach(pid => {
                    const el = document.getElementById(pid);
                    if (el._mirrorListener) { el.removeEventListener('input', el._mirrorListener); }
                });
            }
        });
    }

    // =========================================================
    // 13. YES/NO CONDITIONALS
    // =========================================================
    function initYesNoConditionals() {
        const pairs = [
            { radios: 'od_bond',    cond: 'cond_bond' },
            { radios: 'od_court',   cond: 'cond_court' },
            { radios: 'od_related', cond: 'cond_related' }
        ];
        pairs.forEach(({ radios, cond }) => {
            document.querySelectorAll(`[name="${radios}"]`).forEach(r => {
                r.addEventListener('change', () => {
                    const condEl = document.getElementById(cond);
                    if (r.value === 'yes') {
                        condEl.style.display = 'block';
                    } else {
                        condEl.style.display = 'none';
                    }
                });
            });
        });
    }

    // =========================================================
    // 14. COLLECT FORM DATA
    // =========================================================
    function collectFormData() {
        const getVal = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
        const getRadio = name => { const el = document.querySelector(`[name="${name}"]:checked`); return el ? el.value : ''; };

        const academic = [];
        for (let i = 1; i <= academicCount; i++) {
            academic.push({
                qualification: getNamedVal(`ac_qual_${i}`),
                specialization: getNamedVal(`ac_spec_${i}`),
                college_name: getNamedVal(`ac_college_${i}`),
                address: getNamedVal(`ac_addr_${i}`),
                university: getNamedVal(`ac_univ_${i}`),
                period: getNamedVal(`ac_period_${i}`),
                program: getRadio(`ac_prog_${i}`)
            });
        }

        const employment = [];
        for (let i = 1; i <= employmentCount; i++) {
            employment.push({
                company_name: getNamedVal(`emp_company_${i}`),
                employee_id: getNamedVal(`emp_id_${i}`),
                address: getNamedVal(`emp_addr_${i}`),
                city: getNamedVal(`emp_city_${i}`),
                state: getNamedVal(`emp_state_${i}`),
                date_of_joining: getNamedVal(`emp_doj_${i}`),
                last_working_day: getNamedVal(`emp_lwd_${i}`),
                designation: getNamedVal(`emp_desig_${i}`),
                remuneration: getNamedVal(`emp_rem_${i}`),
                contact1: getNamedVal(`emp_contact1_${i}`),
                contact2: getNamedVal(`emp_contact2_${i}`),
                reported_to: getNamedVal(`emp_reported_name_${i}`),
                reported_designation: getNamedVal(`emp_reported_desig_${i}`),
                reason_for_leaving: getNamedVal(`emp_reason_${i}`)
            });
        }

        const references = [];
        for (let i = 1; i <= referenceCount; i++) {
            references.push({
                // Nested keys for frontend
                name: getNamedVal(`ref_name_${i}`),
                designation: getNamedVal(`ref_desig_${i}`),
                phone: getNamedVal(`ref_phone_${i}`),
                email: getNamedVal(`ref_email_${i}`),
                company_name: getNamedVal(`ref_company_${i}`),
                my_designation: getNamedVal(`ref_mydesig_${i}`),
                // Flat keys for backend HR API
                ref_name: getNamedVal(`ref_name_${i}`),
                ref_designation: getNamedVal(`ref_desig_${i}`),
                ref_phone: getNamedVal(`ref_phone_${i}`),
                ref_email: getNamedVal(`ref_email_${i}`),
                ref_company_name: getNamedVal(`ref_company_${i}`),
                candidate_designation: getNamedVal(`ref_mydesig_${i}`)
            });
        }

        const onsite = [];
        document.querySelectorAll('#onsiteTableBody tr').forEach((tr, i) => {
            onsite.push({
                country: getNamedVal(`onsite_country_${i + 1}`),
                visa_type: getNamedVal(`onsite_visa_${i + 1}`),
                duration: getNamedVal(`onsite_duration_${i + 1}`),
                purpose: getNamedVal(`onsite_purpose_${i + 1}`)
            });
        });

        const nestedData = {
            personal_info: {
                full_name: getVal('pi_full_name'),
                contact: getVal('pi_contact'),
                email: getVal('pi_email'),
                father_name: getVal('pi_father_name'),
                gender: getRadio('pi_gender'),
                actual_dob: getVal('pi_actual_dob'),
                cert_dob: getVal('pi_cert_dob')
            },
            address: {
                permanent: {
                    address: getVal('perm_address'),
                    landmark: getVal('perm_landmark'),
                    landline: getVal('perm_landline'),
                    mobile: getVal('perm_mobile'),
                    period: getVal('perm_period'),
                    nature: getVal('perm_nature')
                },
                current: {
                    address: getVal('curr_address'),
                    landmark: getVal('curr_landmark'),
                    landline: getVal('curr_landline'),
                    mobile: getVal('curr_mobile'),
                    period: getVal('curr_period'),
                    nature: getVal('curr_nature')
                }
            },
            id_proof: {
                pan: getVal('id_pan'),
                aadhar: getVal('id_aadhar'),
                passport_name: getVal('id_passport_name'),
                passport_place: getVal('id_passport_place'),
                passport_issue: getVal('id_passport_issue'),
                passport_expiry: getVal('id_passport_expiry'),
                others: getVal('id_others')
            },
            academic,
            employment,
            references,
            other_details: {
                bond: getRadio('od_bond'),
                bond_detail: getVal('od_bond_detail'),
                court: getRadio('od_court'),
                court_detail: getVal('od_court_detail'),
                related: getRadio('od_related'),
                related_detail: getVal('od_related_detail')
            },
            onsite,
            authorization: {
                name: getVal('auth_name'),
                date: getVal('auth_date'),
                place: getVal('auth_place')
            }
        };

        const flatData = {
            full_name: getVal('pi_full_name'),
            contact_no: getVal('pi_contact'),
            email_id: getVal('pi_email'),
            father_name: getVal('pi_father_name'),
            gender: getRadio('pi_gender'),
            actual_dob: getVal('pi_actual_dob'),
            certificate_dob: getVal('pi_cert_dob'),
            
            permanent_address: getVal('perm_address'),
            permanent_landmark: getVal('perm_landmark'),
            permanent_landline: getVal('perm_landline'),
            permanent_mobile: getVal('perm_mobile'),
            permanent_period_of_stay: getVal('perm_period'),
            permanent_nature_of_residence: getVal('perm_nature'),
            
            current_address: getVal('curr_address'),
            current_landmark: getVal('curr_landmark'),
            current_landline: getVal('curr_landline'),
            current_mobile: getVal('curr_mobile'),
            current_period_of_stay: getVal('curr_period'),
            current_nature_of_residence: getVal('curr_nature'),
            
            pan_number: getVal('id_pan'),
            aadhar_number: getVal('id_aadhar'),
            passport_name: getVal('id_passport_name'),
            passport_place_of_issue: getVal('id_passport_place'),
            passport_issue_date: getVal('id_passport_issue'),
            passport_expiry_date: getVal('id_passport_expiry'),
            
            has_criminal_record: getRadio('od_court'),
            has_criminal_record_details: getVal('od_court_detail'),
            has_severe_disease: getRadio('od_bond'),
            has_severe_disease_details: getVal('od_bond_detail'),
            knows_company_employee: getRadio('od_related'),
            knows_company_employee_details: getVal('od_related_detail'),

            declaration_full_name: getVal('auth_name'),
            declaration_date: getVal('auth_date'),
            declaration_place: getVal('auth_place'),
            
            education: academic // backend calls it 'education' instead of 'academic'
        };

        return { ...nestedData, ...flatData };
    }

    function getNamedVal(name) {
        const el = document.querySelector(`[name="${name}"]`);
        return el ? el.value.trim() : '';
    }

    // =========================================================
    // 15. AUTO SAVE
    // =========================================================
    async function autoSave() {
        try {
            await fetch(`${BASE_URL}/onboarding/declaration`, {
                method: 'POST',
                headers: authHeaders,
                body: JSON.stringify(collectFormData())
            });
        } catch (e) {
            console.warn('Auto-save failed:', e);
        }
    }

    // =========================================================
    // 16. LOAD DECLARATION DATA
    // =========================================================
    async function loadDeclaration() {
        try {
            const res = await fetch(`${BASE_URL}/onboarding/declaration`, { headers: authHeaders });
            if (!res.ok) return;
            const data = await res.json();
            populateDeclaration(data);

            const status = (data.status || '').toUpperCase();
            handleDeclarationStatus(status, data.hr_notes);
        } catch (e) {
            console.warn('Declaration load failed:', e);
        }
    }

    function populateDeclaration(data) {
        const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
        const setRadio = (name, val) => {
            if (!val) return;
            const el = document.querySelector(`[name="${name}"][value="${val}"]`);
            if (el) { el.checked = true; el.dispatchEvent(new Event('change')); }
        };

        const pi = data.personal_info || {};
        setVal('pi_full_name', pi.full_name);
        setVal('pi_contact', pi.contact);
        setVal('pi_email', pi.email);
        setVal('pi_father_name', pi.father_name);
        setRadio('pi_gender', pi.gender);
        setVal('pi_actual_dob', pi.actual_dob);
        setVal('pi_cert_dob', pi.cert_dob);

        const addr = data.address || {};
        const perm = addr.permanent || {};
        setVal('perm_address', perm.address); setVal('perm_landmark', perm.landmark);
        setVal('perm_landline', perm.landline); setVal('perm_mobile', perm.mobile);
        setVal('perm_period', perm.period); setVal('perm_nature', perm.nature);
        const curr = addr.current || {};
        setVal('curr_address', curr.address); setVal('curr_landmark', curr.landmark);
        setVal('curr_landline', curr.landline); setVal('curr_mobile', curr.mobile);
        setVal('curr_period', curr.period); setVal('curr_nature', curr.nature);

        const id = data.id_proof || {};
        setVal('id_pan', id.pan); setVal('id_aadhar', id.aadhar);
        setVal('id_passport_name', id.passport_name); setVal('id_passport_place', id.passport_place);
        setVal('id_passport_issue', id.passport_issue); setVal('id_passport_expiry', id.passport_expiry);
        setVal('id_others', id.others);

        if (data.academic && data.academic.length > 0) {
            academicCount = data.academic.length;
            renderAcademicBlocks();
            data.academic.forEach((ac, i) => {
                const s = (name) => { const el = document.querySelector(`[name="${name}"]`); if (el) el.value = ac[name.split('_').slice(1,-1).join('_')] || ''; };
                document.querySelector(`[name="ac_qual_${i+1}"]`).value = ac.qualification || '';
                document.querySelector(`[name="ac_spec_${i+1}"]`).value = ac.specialization || '';
                document.querySelector(`[name="ac_college_${i+1}"]`).value = ac.college_name || '';
                document.querySelector(`[name="ac_addr_${i+1}"]`).value = ac.address || '';
                document.querySelector(`[name="ac_univ_${i+1}"]`).value = ac.university || '';
                document.querySelector(`[name="ac_period_${i+1}"]`).value = ac.period || '';
                setRadio(`ac_prog_${i+1}`, ac.program);
            });
        }

        if (data.employment && data.employment.length > 0) {
            employmentCount = data.employment.length;
            renderEmploymentBlocks();
            data.employment.forEach((emp, i) => {
                const fields = ['company','id','addr','city','state','desig','rem','contact1','contact2','reported_name','reported_desig','reason'];
                const keys   = ['company_name','employee_id','address','city','state','designation','remuneration','contact1','contact2','reported_to','reported_designation','reason_for_leaving'];
                keys.forEach((key, fi) => {
                    const el = document.querySelector(`[name="emp_${fields[fi]}_${i+1}"]`);
                    if (el) el.value = emp[key] || '';
                });
                const dojEl = document.querySelector(`[name="emp_doj_${i+1}"]`);
                if (dojEl) dojEl.value = emp.date_of_joining || '';
                const lwdEl = document.querySelector(`[name="emp_lwd_${i+1}"]`);
                if (lwdEl) lwdEl.value = emp.last_working_day || '';
            });
        }

        if (data.references && data.references.length >= 3) {
            referenceCount = data.references.length;
            renderReferenceRows();
            data.references.forEach((ref, i) => {
                ['name','desig','phone','email','company','mydesig'].forEach((f, fi) => {
                    const keys = ['name','designation','phone','email','company_name','my_designation'];
                    const el = document.querySelector(`[name="ref_${f}_${i+1}"]`);
                    if (el) el.value = ref[keys[fi]] || '';
                });
            });
        }

        const od = data.other_details || {};
        setRadio('od_bond', od.bond || 'no');
        setVal('od_bond_detail', od.bond_detail);
        setRadio('od_court', od.court || 'no');
        setVal('od_court_detail', od.court_detail);
        setRadio('od_related', od.related || 'no');
        setVal('od_related_detail', od.related_detail);

        if (data.onsite && data.onsite.length > 0) {
            data.onsite.forEach(() => addOnsiteRow());
            data.onsite.forEach((row, i) => {
                ['country','visa_type','duration','purpose'].forEach(f => {
                    const el = document.querySelector(`[name="onsite_${f}_${i+1}"]`);
                    if (el) el.value = row[f] || '';
                });
            });
        }

        const auth = data.authorization || {};
        setVal('auth_name', auth.name);
        setVal('auth_date', auth.date);
        setVal('auth_place', auth.place);
    }

    function handleDeclarationStatus(status, hrNotes) {
        const badge = document.getElementById('declarationStatusBadge');
        const form  = document.getElementById('declarationForm');

        if (status === 'SUBMITTED' || status === 'APPROVED') {
            let cls = status === 'APPROVED' ? 'status-approved' : 'status-submitted';
            let icon = status === 'APPROVED' ? 'bi-check-circle-fill' : 'bi-send-check';
            badge.innerHTML = `<span class="joinee-status-badge ${cls}"><i class="bi ${icon}"></i> ${status.charAt(0) + status.slice(1).toLowerCase()}</span>`;
            badge.classList.remove('d-none');
            form.classList.add('readonly-mode');
            document.getElementById('declarationSubmitBanner').classList.remove('d-none');
        } else if (status === 'CHANGES_REQUESTED') {
            const banner = document.getElementById('changesRequestedBanner');
            document.getElementById('hrNotesText').textContent = hrNotes || '';
            banner.classList.remove('d-none');
            badge.innerHTML = `<span class="joinee-status-badge status-changes"><i class="bi bi-pencil-square"></i> Changes Requested</span>`;
            badge.classList.remove('d-none');
        }
    }

    // =========================================================
    // 17. SUBMIT DECLARATION
    // =========================================================
    async function submitDeclaration() {
        const btn = document.getElementById('btnSubmitDeclaration');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Submitting...';

        await autoSave();

        try {
            const res = await fetch(`${BASE_URL}/onboarding/declaration/submit`, {
                method: 'POST',
                headers: authHeaders,
                body: JSON.stringify(collectFormData())
            });

            if (res.ok || res.status === 200 || res.status === 201) {
                document.getElementById('declarationSubmitBanner').classList.remove('d-none');
                document.getElementById('declarationForm').classList.add('readonly-mode');
                const badge = document.getElementById('declarationStatusBadge');
                badge.innerHTML = `<span class="joinee-status-badge status-submitted"><i class="bi bi-send-check"></i> Submitted</span>`;
                badge.classList.remove('d-none');
            } else {
                const err = await res.json().catch(() => ({}));
                alert(err.error || err.message || 'Failed to submit. Please try again.');
                btn.disabled = false;
                btn.innerHTML = '<i class="bi bi-send-check me-1"></i> Submit Declaration';
            }
        } catch {
            alert('Network error. Please try again.');
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-send-check me-1"></i> Submit Declaration';
        }
    }

    // =========================================================
    // 18. REVIEW SUMMARY (Step 6)
    // =========================================================
    function buildReviewSummary() {
        const data = collectFormData();
        const container = document.getElementById('reviewSummary');
        container.innerHTML = '';

        const section = (title, items) => {
            const div = document.createElement('div');
            div.className = 'review-section';
            const grid = items.map(([label, val]) => `
                <div class="review-item">
                    <label>${label}</label>
                    <p>${val || '<em class="text-muted">Not provided</em>'}</p>
                </div>`).join('');
            div.innerHTML = `<div class="review-section-title">${title}</div><div class="review-grid">${grid}</div>`;
            container.appendChild(div);
        };

        const pi = data.personal_info;
        section('Personal Information', [
            ['Full Name', pi.full_name], ['Contact', pi.contact],
            ['Email', pi.email], ["Father's Name", pi.father_name],
            ['Gender', pi.gender], ['Actual DOB', pi.actual_dob], ['Certificate DOB', pi.cert_dob]
        ]);

        const perm = data.address.permanent;
        section('Permanent Address', [
            ['Address', perm.address], ['Landmark', perm.landmark],
            ['Landline', perm.landline], ['Mobile', perm.mobile],
            ['Period', perm.period], ['Nature', perm.nature]
        ]);

        const cur = data.address.current;
        section('Current Address', [
            ['Address', cur.address], ['Landmark', cur.landmark],
            ['Landline', cur.landline], ['Mobile', cur.mobile],
            ['Period', cur.period], ['Nature', cur.nature]
        ]);

        const id = data.id_proof;
        section('ID Proof', [
            ['PAN No.', id.pan], ['Aadhar No.', id.aadhar],
            ['Passport Name', id.passport_name], ['Passport Place', id.passport_place],
            ['Passport Issue', id.passport_issue], ['Passport Expiry', id.passport_expiry]
        ]);

        data.academic.forEach((ac, i) => {
            section(`Academic — Institution ${i + 1}`, [
                ['Qualification', ac.qualification], ['Specialization', ac.specialization],
                ['College', ac.college_name], ['University', ac.university],
                ['Period', ac.period], ['Program', ac.program]
            ]);
        });

        data.employment.forEach((emp, i) => {
            section(`Employment ${i + 1}${i === 0 ? ' (Latest)' : ''}`, [
                ['Company', emp.company_name], ['Employee ID', emp.employee_id],
                ['Designation', emp.designation], ['Remuneration', emp.remuneration],
                ['Joining Date', emp.date_of_joining], ['Last Working Day', emp.last_working_day],
                ['Reported To', emp.reported_to]
            ]);
        });

        const od = data.other_details;
        section('Other Details', [
            ['Service Bond?', od.bond], ['Court Conviction?', od.court],
            ['Related to Employee?', od.related]
        ]);

        if (data.onsite.length > 0) {
            const onsiteItems = data.onsite.map((r, i) => [
                `Onsite ${i + 1}`, `${r.country} | ${r.visa_type} | ${r.duration} | ${r.purpose}`
            ]);
            section('Onsite Details', onsiteItems);
        }
    }

    // =========================================================
    // 19. DOCUMENT SLOTS
    // =========================================================
    const DOC_SLOTS = [
        { key: 'AADHAR',             label: 'Aadhar Card',                      required: true,  multiple: false },
        { key: 'PAN',                label: 'PAN Card',                         required: true,  multiple: false },
        { key: 'DEGREE_CERTIFICATE', label: 'Academic Certificates',            required: true,  multiple: true  },
        { key: 'OFFER_LETTER',       label: 'Offer Letter (Latest Employer)',   required: true,  multiple: false },
        { key: 'EXPERIENCE_LETTER',  label: 'Relieving Letter / Exp. Cert.',    required: true,  multiple: false },
        { key: 'BANK_PASSBOOK',      label: 'Bank Passbook / Cancelled Cheque', required: true,  multiple: false },
        { key: 'PHOTO',              label: 'Passport Photo',                   required: true,  multiple: false },
        { key: 'PASSPORT',           label: 'Passport Copy (Visa Pages)',       required: false, multiple: false },
        { key: 'OTHER',              label: 'Other Documents (Pay Slips, etc)', required: false, multiple: true  }
    ];

    // Tracks upload state per slot
    const docState = {};
    DOC_SLOTS.forEach(slot => { docState[slot.key] = null; });

    function renderDocumentCards() {
        const grid = document.getElementById('docGrid');
        grid.innerHTML = '';
        DOC_SLOTS.forEach(slot => {
            const card = document.createElement('div');
            card.className = 'doc-card';
            card.id = `docCard_${slot.key}`;
            grid.appendChild(card);
            renderSlotCard(slot, docState[slot.key]);
        });
    }

    function renderSlotCard(slot, state) {
        const card = document.getElementById(`docCard_${slot.key}`);
        if (!card) return;

        const badgeCls = slot.required ? 'badge-required' : 'badge-optional';
        const badgeLabel = slot.required ? 'Required' : 'Optional';
        const multiLabel = slot.multiple ? '<span class="text-muted" style="font-size:0.7rem"> (multiple)</span>' : '';

        let bodyHtml = '';

        if (!state) {
            // Not uploaded
            bodyHtml = `
                <label class="doc-upload-area" for="fileInput_${slot.key}">
                    <i class="bi bi-cloud-upload"></i>
                    <span>Click to Choose File${slot.multiple ? 's' : ''}</span>
                </label>
                <input type="file" id="fileInput_${slot.key}" class="d-none"
                    accept="image/jpeg,image/png,image/webp,application/pdf"
                    ${slot.multiple ? 'multiple' : ''}
                    onchange="handleFileSelect(event, '${slot.key}')">`;
        } else if (state.status === 'PENDING') {
            bodyHtml = `
                <div class="doc-file-info">
                    <i class="bi bi-file-earmark-check"></i>
                    <span>${state.filename}</span>
                    <span class="doc-badge badge-pending ms-auto">Pending Review</span>
                </div>
                <button class="btn btn-sm btn-outline-danger mt-2 w-100" onclick="removeDocument('${slot.key}', '${state.doc_id}')">
                    <i class="bi bi-trash me-1"></i>Remove
                </button>`;
        } else if (state.status === 'APPROVED') {
            bodyHtml = `
                <div class="doc-file-info">
                    <i class="bi bi-file-earmark-check text-success"></i>
                    <span>${state.filename}</span>
                    <span class="doc-badge badge-approved ms-auto">Approved ✓</span>
                </div>`;
        } else if (state.status === 'REJECTED') {
            bodyHtml = `
                <div class="doc-file-info">
                    <i class="bi bi-file-earmark-x text-danger"></i>
                    <span>${state.filename}</span>
                    <span class="doc-badge badge-rejected ms-auto">Rejected</span>
                </div>
                ${state.rejection_reason ? `<p class="doc-rejection-reason mt-1"><i class="bi bi-exclamation-circle me-1"></i>${state.rejection_reason}</p>` : ''}
                <label class="btn btn-sm btn-outline-primary mt-2 w-100" for="fileInput_reup_${slot.key}">
                    <i class="bi bi-arrow-repeat me-1"></i>Re-upload
                </label>
                <input type="file" id="fileInput_reup_${slot.key}" class="d-none"
                    accept="image/jpeg,image/png,image/webp,application/pdf"
                    onchange="handleFileSelect(event, '${slot.key}')">`;
        } else if (state.status === 'UPLOADING') {
            bodyHtml = `
                <div class="doc-file-info">
                    <span class="spinner-border spinner-border-sm text-primary me-2"></span>
                    <span class="text-muted">Uploading ${state.filename}...</span>
                </div>`;
        }

        card.innerHTML = `
            <div class="doc-card-header">
                <div class="doc-name">${slot.label}${multiLabel}</div>
                <span class="doc-badge ${badgeCls}">${badgeLabel}</span>
            </div>
            ${bodyHtml}`;
    }

    window.handleFileSelect = async function(event, slotKey) {
        const files = event.target.files;
        if (!files || files.length === 0) return;
        const slot = DOC_SLOTS.find(s => s.key === slotKey);

        for (const file of files) {
            docState[slotKey] = { status: 'UPLOADING', filename: file.name };
            renderSlotCard(slot, docState[slotKey]);

            const formData = new FormData();
            formData.append('file', file);
            formData.append('document_type', slotKey);
            formData.append('document_label', slot.label || slotKey);

            try {
                const res = await fetch(`${BASE_URL}/onboarding/documents/upload`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` },
                    body: formData
                });
                const data = await res.json();
                if (res.ok && (data.success !== false)) {
                    docState[slotKey] = {
                        status: 'PENDING',
                        filename: file.name,
                        doc_id: data.document_id || data.id || null
                    };
                } else {
                    docState[slotKey] = null;
                    alert(data.error || data.message || 'Upload failed.');
                }
            } catch {
                docState[slotKey] = null;
                alert('Upload failed. Network error.');
            }
            renderSlotCard(slot, docState[slotKey]);
        }
    };

    window.removeDocument = async function(slotKey, docId) {
        const slot = DOC_SLOTS.find(s => s.key === slotKey);
        if (!confirm('Remove this document?')) return;
        try {
            if (docId) {
                await fetch(`${BASE_URL}/onboarding/documents/${docId}`, {
                    method: 'DELETE',
                    headers: authHeaders
                });
            }
        } catch { /* ignore */ }
        docState[slotKey] = null;
        renderSlotCard(slot, null);
    };

    async function loadDocuments() {
        try {
            const res = await fetch(`${BASE_URL}/onboarding/documents`, { headers: authHeaders });
            if (!res.ok) return;
            const data = await res.json();
            const docs = data.documents || data || [];
            docs.forEach(doc => {
                const key = doc.document_type || doc.type;
                if (docState.hasOwnProperty(key)) {
                    docState[key] = {
                        status: (doc.verification_status || 'PENDING').toUpperCase(),
                        filename: doc.filename || doc.file_name || 'Uploaded file',
                        doc_id: doc.id,
                        rejection_reason: doc.rejection_reason || ''
                    };
                }
            });
            DOC_SLOTS.forEach(slot => renderSlotCard(slot, docState[slot.key]));
        } catch (e) {
            console.warn('Documents load failed:', e);
        }
    }

    // =========================================================
    // START
    // =========================================================
    loadProfile();
});
