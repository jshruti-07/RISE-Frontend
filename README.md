# Altzor — HR Management System

A full-featured Human Resource Management System built with **Flask**, designed around a two-tier architecture where a frontend Flask application proxies requests to a separate backend API server. The system supports role-based access for **HR**, **Managers**, **Employees**, and **Onboarding Candidates**, covering core HR workflows including employee onboarding, leave management, timesheets, project tracking, payslips, attendance, reimbursements, help desk, assets, policies, announcements, and more.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Running the Application](#running-the-application)
- [Mobile & Tablet Access](#mobile--tablet-access)
- [User Roles & Permissions](#user-roles--permissions)
- [Modules](#modules)
  - [Authentication](#authentication)
  - [Dashboard](#dashboard)
  - [Employee Management](#employee-management)
  - [Leave Management](#leave-management)
  - [Timesheet Management](#timesheet-management)
  - [Project Management](#project-management)
  - [Help Desk](#help-desk)
  - [Assets & Devices](#assets--devices)
  - [Reimbursements](#reimbursements)
  - [Attendance](#attendance)
  - [Payslips](#payslips)
  - [Bank Details](#bank-details)
  - [Policies](#policies)
  - [Announcements](#announcements)
  - [Notifications](#notifications)
  - [Profile](#profile)
- [API Proxy Routes](#api-proxy-routes)
- [UI Branding & Constants](#ui-branding--constants)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| Module               | Capabilities                                                                                                            |
|----------------------|-------------------------------------------------------------------------------------------------------------------------|
| **Authentication**   | Login, JWT-based sessions, Forgot/Reset Password, first-login password enforcement                                      |
| **Dashboard**        | Role-aware stats (Employees, Timesheets, Leaves), Birthdays (today + upcoming 7-day), Holidays, Announcements, Pending Agreements, Team Leaves, Pending Timesheets |
| **Employees**        | Add / edit / delete employees, role-prefix naming (`H_`, `M_`, `T_`), document uploads, photo upload/update             |
| **Leaves**           | Apply for leave (Full/Half day), leave balance tracking, manager/HR approval workflow, calendar API                     |
| **Timesheets**       | Daily & weekly submissions, manager review, calendar view with holidays, Excel/CSV export, HR Missing Timesheets report |
| **Projects**         | HR creates projects, assigns managers; managers manage teams & view project details; employee project view               |
| **Help Desk**        | Ticketing system with priority/status management, HR assignment, internal resolution messaging                           |
| **Assets & Devices** | Digital device inventory, assignment tracking, e-agreements with electronic signatures, image upload                     |
| **Reimbursements**   | Claim submission with receipt upload, multi-stage approval (Manager → HR), payment tracking, history                    |
| **Attendance**       | Custom date-range filtering, metrics dashboard (Office, WFH, Overtime, Late Logins, Half-Days), role-aware view          |
| **Payslips**         | View monthly payslips per employee                                                                                       |
| **Bank Details**     | Employees submit bank info; HR verification workflow (Approve/Reject)                                                   |
| **Policies**         | Company policies with category filters; HR can add/edit policies                                                        |
| **Announcements**    | HR posts announcements with optional attachments; dashboard widget shows active announcements                            |
| **Notifications**    | System-wide notification feed for all roles                                                                              |
| **Profile**          | Personal info, profile photo upload, document upload progress (PAN, Aadhaar, etc.), leave balance summary               |
| **Onboarding**       | HR onboarding dashboard, joinee onboarding dashboard, document proxy for onboarding files                                |

---

## Architecture

```
┌──────────────────────┐          ┌──────────────────────────┐
│   Frontend (Flask)   │  HTTP    │    Backend API Server     │
│   run.py — port 5002 │ ───────> │    port 5001 (remote)    │
│                      │          │                          │
│  • Blueprint Modular │          │  • REST API endpoints    │
│  • Session mgmt      │          │  • MySQL database        │
│  • Proxy routes      │          │  • JWT authentication    │
│  • .env config       │          │  • File uploads          │
│  • ui_constants.py   │          │  • Attendance, Leaves    │
│  • Context Processor │          │  • Timesheets, Devices   │
└──────────────────────┘          └──────────────────────────┘
```

The **frontend** is a modular Flask application using the **Application Factory** pattern (`create_app()`). It handles rendering, session management, and role-based access control across logical Blueprints. It **proxies** all data operations to a **separate backend API** via HTTP requests using JWT tokens.

A global **context processor** (`inject_user`) automatically injects `current_user`, `role`, `sidebar_photo_url`, `labels` (from `ui_constants.py`), and `config` into every template, so all pages have access to the logged-in user's context without explicit passing.

---

## Tech Stack

| Layer           | Technology                                                       |
|-----------------|------------------------------------------------------------------|
| **Frontend**    | Flask (Blueprints + App Factory), Jinja2, HTML5, CSS3, JavaScript |
| **Backend API** | Flask (separate server) — proxied via HTTP                       |
| **Config**      | `python-dotenv` (`.env` file)                                    |
| **Database**    | MySQL (Backend), `projects.json` (local project store)           |
| **Auth**        | JWT (JSON Web Tokens) stored in Flask session                    |
| **File Export** | `pandas` + `openpyxl` for Excel; CSV fallback (no extra deps)    |
| **Optional**    | `pandas` for timesheet export (gracefully degraded if missing)   |

---

## Project Structure

```

Altzor3/
├── run.py                        # Main entry point — starts app on port 5002
├── app/                          # Main application package
│   ├── __init__.py               # Application factory (create_app), Blueprint registration, context processor
│   ├── utils.py                  # Shared helpers: BASE_URL, get_headers, role_required, token_required,
│   │                             #   fetch_leave_balance_helper (with dynamic fallback calculation)
│   ├── api_helpers.py            # API response normalizers: prefix stripping, name matching, person/project data parsing
│   ├── ui_constants.py           # Centralized branding: UI_LABELS, UI_CONFIG (injected globally via context processor)
│   ├── onboarding_ui/            # Onboarding module routes and templates
│   │   ├── __init__.py           # Onboarding Blueprint registration
│   │   └── routes.py             # Onboarding dashboard (HR) and joinee dashboard routes
│   └── routes/                   # Modular route definitions (Flask Blueprints)
│       ├── auth.py               # Login, Logout, Forgot/Reset Password, Change Password, onboarding candidate redirect
│       ├── dashboard.py          # Role-aware dashboard: stats, birthdays, holidays, announcements,
│       │                         #   team leaves, pending timesheets, pending agreements
│       ├── employees.py          # Employee CRUD: add, edit, delete, view all employees
│       ├── projects.py           # HR project creation/management, manager project views, project details
│       ├── work_management.py    # Timesheets (list, add daily/weekly, export, missing), Leaves (list, add, approve/reject, calendar,
│       │                         #   balance), Attendance (date-range view, metrics), Leave Balance API
│       ├── admin.py              # Help Desk, Reimbursements (full CRUD + approval workflow),
│       │                         #   Assets/Devices (CRUD, assign, image, history), Policies,
│       │                         #   Bank Details verification, Announcements (CRUD + attachments)
│       ├── user.py               # Profile view, Photo upload, Payslips, Bank Verification (HR),
│       │                         #   File proxy (serve backend uploads), API: /api/my-photo
│       └── main.py               # Notifications page
├── .env                          # Environment variables: SECRET_KEY, BACKEND_URL
├── projects.json                 # Local project/manager/team data store (used by dashboard & timesheets)
├── helpdesk_messages.json        # Local storage for help desk ticket messaging
├── app.log                       # Application log file
├── app_backup.py                 # Legacy monolithic app (kept for reference)
├── app_calendar_endpoint.py      # Standalone calendar endpoint helper
├── templates/                    # Jinja2 HTML templates (all pages)
│   ├── base.html                 # Base layout: sidebar, navbar, back button, responsive design
│   ├── login.html                # Login page (AI-native design)
│   ├── dashboard.html            # Main dashboard
│   ├── timesheets.html           # Timesheet list + calendar + filters + export
│   ├── add_timesheet.html        # Add daily timesheet
│   ├── add_weekly_timesheet.html # Add weekly timesheet
│   ├── edit_timesheet.html       # Edit timesheet entry
│   ├── hr_missing_timesheets.html# HR Missing Timesheets view
│   ├── leaves.html               # Leave list + balance summary
│   ├── add_leave.html            # Apply for leave (full/half day)
│   ├── attendance.html           # Attendance view with metrics
│   ├── projects.html             # HR project management
│   ├── manager_projects.html     # Manager's project view
│   ├── project_details.html      # Detailed project view with team
│   ├── create_project.html       # Create new project
│   ├── all_employees.html        # Employee directory
│   ├── add_employee.html         # Add new employee
│   ├── edit_employee.html        # Edit employee
│   ├── helpdesk.html             # Help desk ticketing
│   ├── reimbursement.html        # Reimbursement claims
│   ├── assets.html               # Asset/device management
│   ├── agreement.html            # Device e-agreement signing
│   ├── policies.html             # Company policies
│   ├── payslips.html             # Payslip view
│   ├── profile.html              # Employee profile & document uploads
│   ├── bank_admin.html           # Bank details verification (HR)
│   ├── notifications.html        # Notifications feed
│   ├── change_password.html      # Change password
│   ├── forgot_password.html      # Forgot password
│   ├── reset_password.html       # Reset password
│   ├── onboarding/               # Onboarding module templates
│   │   └── dashboard.html        # HR onboarding dashboard
│   └── joinee/                   # Onboarding candidate templates
│       ├── base.html             # Joinee base layout
│       └── dashboard.html        # Joinee onboarding dashboard
├── static/                       # Global CSS, JS, and images
│   └── css/
│       └── style.css             # Application styles
└── uploads/                      # Uploaded files (proxied from backend)
```

---

## Getting Started

### Prerequisites

- **Python 3.8+**
- **pip** (Python package manager)
- Access to the **backend API server** (running at the address set in `.env`)
- *(Optional)* `pandas` + `openpyxl` for Excel timesheet export

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Altzor3
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install flask requests python-dotenv
   # Optional: for Excel timesheet export
   pip install pandas openpyxl
   ```

### Configuration

Create a `.env` file in the root directory with the following variables:

```ini
# .env
SECRET_KEY=your_secure_random_string
BACKEND_URL=http://<BACKEND_IP>:5001
```

> **Note:** The `BACKEND_URL` must be reachable from the machine running the frontend. For local network access from mobile/tablet devices, use your machine's local IP address (e.g., `http://192.168.1.5:5001`).

### Running the Application

```bash
python run.py
```

The application will start on **http://0.0.0.0:5002** (accessible as `http://localhost:5002` locally).

---

## 📱 Mobile & Tablet Access

To access the Altzor HR system from any device (Mobile, Tablet, Laptop) on your local network:

1. **Find your Local IP Address**:
   - **Windows**: Open Command Prompt → `ipconfig` → Look for "IPv4 Address" (e.g., `192.168.1.5`).
   - **Mac/Linux**: Open Terminal → `ifconfig` or `ip addr`.

2. **Configure `.env`**:
   Use your actual LAN IP so backend is reachable from all devices:
   ```ini
   BACKEND_URL=http://192.168.1.5:5001
   ```

3. **Open Browser on Device**:
   Connect your device to the same Wi-Fi and navigate to:
   ```
   http://192.168.1.5:5002
   ```

4. **Responsive UI**:
   The interface is optimized for all screen sizes. On mobile, the sidebar collapses into a slide-out drawer to maximize screen space.

---

## User Roles & Permissions

| Role                 | Prefix | Key Permissions                                                                          |
|----------------------|--------|------------------------------------------------------------------------------------------|
| **HR**               | `H_`   | Full access — manage employees, projects, verify bank info, manage assets, helpdesk, policies, announcements, onboarding dashboard |
| **Manager**          | `M_`   | Manage teams, approve/reject timesheets & leaves, view reimbursements, access project details |
| **Employee**         | `T_`   | Submit timesheets/leaves, view own profile & attendance, raise helpdesk tickets, sign agreements, submit reimbursement claims |
| **Onboarding Candidate** | — | Access joinee onboarding dashboard, view and complete onboarding documents |

> Role is enforced on every route via the `@role_required([...])` decorator in `app/utils.py`. API/AJAX calls receive JSON `403` responses instead of redirects.

---

## Modules

### Authentication
- **Login / Logout** — JWT token stored in session; session cleared on logout.
- **Password Management** — Forgot password → email OTP → reset. First-login enforcement (redirect to change password).
- **Change Password** — Available to all logged-in users.
- **Onboarding Candidate Redirect** — Logged-in onboarding candidates are automatically redirected to joinee dashboard.

### Onboarding
- **HR Onboarding Dashboard** — Accessible to HR/Admin at `/onboarding/` to manage onboarding process.
- **Joinee Dashboard** — Accessible to onboarding candidates at `/onboarding/joinee-dashboard` to complete onboarding tasks.
- **Document Proxy** — Securely proxies onboarding document files from backend API at `/onboarding/documents/<id>/view`.

### Dashboard
- **Role-Aware Stats** — Cards for total employees, pending timesheets (current month), and pending leaves.
- **Birthdays** — Today's birthdays + upcoming birthdays in the next 7 days (with employee photos).
- **Holidays** — Upcoming company holidays for the year.
- **Announcements Widget** — Latest active announcements from HR.
- **Team Leaves** (HR/Manager) — Pending and approved leave requests for team members.
- **Team Pending Timesheets** (HR/Manager) — Timesheets awaiting review.
- **Pending Agreements** (Employee) — Device agreements requiring signature.
- **Missing Timesheet Alert** (Employee) — Flags if today's timesheet entry is missing.

### Employee Management
- **CRUD** — Add, edit, and delete employees with role assignment.
- **Role Naming** — Employees prefixed with `H_` (HR), `M_` (Manager), `T_` (Team/Employee).
- **Document & Photo Uploads** — Profile photos and documents proxied securely through the frontend to the backend.
- **Employee Directory** — Searchable list of all employees.

### Leave Management
- **Apply for Leave** — Full-day or Half-day (AM/PM) with leave type selection (Casual / Sick / Earned).
- **Leave Balance** — Detailed breakdown per type (Casual: 12, Sick: 10, Earned: 8); dynamic fallback calculation if API unavailable.
- **Approval Workflow** — Manager / HR approve or reject; status visible in list view.
- **Calendar API** — `/api/leaves/calendar` for frontend calendar integration.
- **Leave Balance API** — `/api/leaves/balance` endpoint with multi-tier fallback logic.

### Timesheet Management
- **Submit Timesheets** — Daily and weekly timesheet submission with project, task, hours, and description.
- **HR Missing Timesheets** — Track and report employees who have not submitted timesheets for a given date range.
- **Role-Based Visibility** — Employees see own; managers see their project team's; HR/Admin see all.
- **Approve / Reject** — Manager & HR can approve or reject timesheets with optional rejection reason.
- **Calendar Integration** — Visual calendar view marking submitted, missing, and holiday dates.
- **Export** — Download timesheets as `.xlsx` (Excel) with auto-column widths; falls back to `.csv` if `pandas`/`openpyxl` not installed.
- **Day Detail API** — `/api/timesheets/day` for per-day breakdown.

### Project Management
- **HR** — Create, assign, and manage projects; assign managers and team members.
- **Manager** — View assigned projects, manage team members, view project details and progress.
- **Employee** — View projects they are assigned to.
- **Local Store** — `projects.json` used for quick project-manager and team-member lookups across timesheets and dashboard.

### Help Desk
- **Raise Tickets** — Employees create tickets with title, description, and priority level.
- **Management** — HR can assign tickets to team members, update status, and communicate via internal message threads.
- **All Roles** — Employees, managers, and HR can all view and interact with the ticketing system.

### Assets & Devices
- **Inventory** — Track company devices (laptops, etc.) with serial numbers, specs, and purchase info.
- **Assignment** — Assign devices to employees with history tracking.
- **Image Upload** — Upload device images to the backend.
- **E-Agreements** — Digital signature-based device usage agreements; employees can sign from their dashboard.
- **Acceptance Status** — Track whether assigned employee has accepted the device agreement.

### Reimbursements
- **Claims** — Submit reimbursement requests with category, amount, date, and receipt file upload.
- **Multi-Stage Approval** — Manager approval → HR approval → Payment marking.
- **History** — View full approval/rejection history per claim.
- **Receipt Download** — Proxy endpoint to securely serve receipt files.
- **Role Filtering** — Each role sees only relevant claims (own / team / all).

### Attendance
- **Custom Date Range** — Filter attendance logs by any `from_date` to `to_date`.
- **Auto-Default** — Defaults to the current calendar month if no range specified.
- **Metrics Dashboard** — Office days, WFH, Half-days, Absent, Overtime, Late Logins.
- **Summary Stats** — Working days, weekends, holidays, leave balance, average hours.
- **Role-Aware** — Employees see only their own data; managers and HR can view any employee.

### Payslips
- **View Payslips** — Monthly payslips fetched from the backend reports API.
- **Role Access** — Available to all roles (each user sees their own data).

### Bank Details
- **Employee Submission** — Employees submit bank account information via their profile.
- **HR Verification** — HR reviews submissions and approves or rejects them via `bank_admin.html`.
- **Status Tracking** — Pending / Approved / Rejected states.

### Policies
- **View Policies** — Company policies fetched from backend, filterable by category.
- **HR Management** — HR can add and edit policies inline.
- **Category Filters** — Dynamically generated category list from existing policies.

### Announcements
- **HR Posts** — HR can create announcements with title, content, and optional file attachment.
- **Dashboard Widget** — Active announcements surface on the main dashboard for all roles.
- **CRUD** — HR can edit and delete announcements; all roles can view.
- **Attachment Proxy** — `/api/announcements/<id>/attachment` streams attachment files from the backend.

### Notifications
- **Feed** — System-wide notification list available to all logged-in users.
- **Route** — `/notifications` renders `notifications.html`.

### Profile
- **Personal Info** — View employee details pulled from the backend.
- **Photo Upload** — Upload and update profile photo (validates identity against session).
- **Leave Balance Summary** — Remaining, used, and breakdown by type (Casual / Sick / Earned).
- **Bank Details** — View submitted bank info directly from the profile page.
- **Document Progress** — Track upload completion for key documents (PAN, Aadhaar, etc.).

---

## API Proxy Routes

The frontend acts as a transparent proxy for the backend API. Key proxy routes:

| Frontend Route                                    | Method(s)          | Blueprint  | Description                                      |
|---------------------------------------------------|--------------------|------------|--------------------------------------------------|
| `/api/helpdesk/`                                  | GET, POST          | admin      | List / create helpdesk tickets                   |
| `/api/helpdesk/<id>/status`                       | PATCH              | admin      | Update ticket status (HR only)                   |
| `/api/helpdesk/<id>/assign`                       | PATCH              | admin      | Assign ticket (HR only)                          |
| `/api/reimbursements`                             | GET, POST          | admin      | List / submit reimbursement claims               |
| `/api/reimbursements/<id>`                        | GET, DELETE        | admin      | Get / delete a specific claim                    |
| `/api/reimbursements/<id>/approve`                | PATCH              | admin      | Approve a claim                                  |
| `/api/reimbursements/<id>/reject`                 | PATCH              | admin      | Reject a claim                                   |
| `/api/reimbursements/<id>/pay`                    | PATCH              | admin      | Mark claim as paid (admin only)                  |
| `/api/reimbursements/<id>/receipt`                | GET                | admin      | Download receipt file                            |
| `/api/assets`                                     | GET, POST          | admin      | List / create assets (HR only)                   |
| `/api/assets/<id>`                                | GET, DELETE        | admin      | Get / delete an asset                            |
| `/api/assets/<id>/history`                        | GET                | admin      | Asset assignment history                         |
| `/api/assets/<id>/assign`                         | POST               | admin      | Assign asset to employee                         |
| `/api/assets/<id>/acceptance-status`              | GET                | admin      | Check employee acceptance                        |
| `/api/policies/<id>`                              | PUT                | admin      | Update a policy (HR only)                        |
| `/api/announcements`                              | GET, POST          | admin      | List / create announcements                      |
| `/api/announcements/dashboard`                    | GET                | admin      | Fetch active announcements for dashboard widget  |
| `/api/announcements/<id>`                         | GET, PUT, DELETE   | admin      | CRUD on a specific announcement                  |
| `/api/announcements/<id>/attachment`              | GET                | admin      | Download announcement attachment                 |
| `/api/leaves/calendar`                            | GET                | work       | Leave calendar data by month/year                |
| `/api/leaves/balance`                             | GET                | work       | Leave balance for an employee                    |
| `/api/timesheets/calendar`                        | GET                | work       | Timesheet calendar data by month/year            |
| `/api/timesheets/day`                             | GET                | work       | Timesheet details for a specific day             |
| `/manager/timesheets/pending`                     | GET                | work       | Fetch timesheets pending manager review          |
| `/manager/timesheets/approve`                     | POST               | work       | Approve a timesheet                              |
| `/manager/timesheets/reject`                      | POST               | work       | Reject a timesheet with reason                   |
| `/timesheets/export`                              | GET                | work       | Export timesheets as Excel (.xlsx) or CSV        |
| `/hr-missing-timesheets`                          | GET                | work       | HR Missing Timesheets report                     |
| `/add-weekly-timesheet`                           | GET                | work       | Render Add Weekly Timesheet page                 |
| `/update-leave/<id>/<status>`                     | PUT                | work       | Update leave approval status                     |
| `/bank-details/<id>/<action>`                     | PATCH              | admin      | Approve or reject bank details (HR only)         |
| `/api/my-photo`                                   | GET                | user       | Fetch the logged-in user's profile photo URL     |
| `/uploads/<path:filename>`                        | GET                | user       | Stream backend-hosted uploaded files             |
| `/upload-photo`                                   | POST               | user       | Upload / update profile photo                    |
| `/notifications`                                  | GET                | main       | Notifications feed page                          |
| `/onboarding/`                                    | GET                | onboarding | HR onboarding dashboard (HR/Admin only)          |
| `/onboarding/joinee-dashboard`                    | GET                | onboarding | Joinee onboarding dashboard (onboarding candidate only) |
| `/onboarding/documents/<int:document_id>/view`    | GET                | onboarding | Proxy for onboarding document file from backend  |

---

## UI Branding & Constants

All user-facing labels (e.g., "Employee" → "Team Member") are centralized in `app/ui_constants.py`:

```python
# app/ui_constants.py
UI_LABELS = {
    "EMPLOYEE": "Team Member",
    "EMPLOYEES": "Team Members",
    "ADD_EMPLOYEE": "Add Team Member",
    ...
}

UI_CONFIG = {
    "BANK_DETAILS_READ_ONLY": True,  # Set False to enable bank detail editing
}
```

These are automatically injected into **every template** via the global context processor in `app/__init__.py` as `labels` and `config`, so no manual passing is required in route handlers.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Open a Pull Request

---

## License

This project is proprietary. All rights reserved.
