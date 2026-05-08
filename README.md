# Altzor — HR Management System

A full-featured Human Resource Management System built with **Flask**, designed around a two-tier architecture where a frontend Flask application proxies requests to a separate backend API server. The system supports role-based access for **HR**, **Managers**, and **Employees**, covering core HR workflows including employee onboarding, leave management, timesheets, project tracking, payslips, attendance, and more.

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
  - [Bank Details](#bank-details)
  - [Policies](#policies)
  - [Notifications](#notifications)
  - [Profile](#profile)
- [API Proxy Routes](#api-proxy-routes)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| Module               | Capabilities                                                                                 |
|----------------------|----------------------------------------------------------------------------------------------|
| **Authentication**   | Login, JWT-based sessions, Forgot/Reset Password, first-login password enforcement           |
| **Dashboard**        | Stats (Employees, Tickets, Claims), Birthdays, Holidays, Pending Agreements, Active Projects |
| **Employees**        | Add / edit / delete employees, role-prefix naming (`H_`, `M_`, `T_`), document uploads       |
| **Leaves**           | Apply for leave (Full/Half day), leave balance tracking, manager/HR approval workflow        |
| **Timesheets**       | Daily & Weekly submissions, manager review, calendar view with holidays & missing markers    |
| **Projects**         | HR creates projects, assigns managers; managers manage teams; employee project view          |
| **Help Desk**        | Ticketing system, priority/status management, internal resolution messaging                 |
| **Assets & Devices** | Digital device agreements, electronic signatures, asset tracking                             |
| **Reimbursements**   | Claim submission with receipt upload, multi-stage approval, payment tracking                |
| **Attendance**       | Custom date-range filtering, metrics dashboard (Office, WFH, Overtime, Late Logins)          |
| **Payslips**         | View monthly payslips                                                                        |
| **Bank Details**     | Employees submit bank info, status-driven HR verification workflow                           |
| **Policies**         | Company policies with category filters, HR management                                        |
| **Profile**          | Personal info, document upload progress (PAN, Aadhaar, etc.), leave balance summary          |

---

## Architecture

```
┌──────────────────────┐          ┌──────────────────────────┐
│   Frontend (Flask)   │  HTTP    │    Backend API Server     │
│   app.py — port 5002 │ ───────> │    port 5001 (remote)    │
│                      │          │                          │
│  • Jinja2 templates  │          │  • REST API endpoints    │
│  • Session mgmt      │          │  • MySQL database        │
│  • Proxy routes       │          │  • JWT authentication    │
│  • Static assets      │          │  • File uploads          │
└──────────────────────┘          └──────────────────────────┘
```

The **frontend** Flask server (`app.py`) handles rendering, session management, and role-based access control. It **proxies** all data operations to a **separate backend API** via HTTP requests. The backend manages the database (MySQL), JWT authentication, and file storage.

---

## Tech Stack

| Layer           | Technology                                              |
|-----------------|--------------------------------------------------------|
| **Frontend**    | Flask, Jinja2 templates, HTML5, CSS3, JavaScript        |
| **Backend API** | Flask (separate server), Flask Blueprints               |
| **Database**    | MySQL                                                   |
| **Auth**        | JWT (JSON Web Tokens)                                   |
| **Styling**     | Custom CSS (`static/css/style.css`)                    |
| **Data Format** | JSON (API communication), `projects.json` (local store) |

---

## Project Structure

```
Altzor3/
├── app.py                    # Main Flask application (frontend server)
├── app_calendar_endpoint.py  # Calendar API logic
├── projects.json             # Local project data store
├── helpdesk_messages.json    # Local storage for ticket messaging
├── app.log                   # Application logs
│
├── templates/
│   ├── base.html             # Base layout with sidebar navigation
│   ├── login.html            # Login page
│   ├── forgot_password.html  # Forgot password form
│   ├── reset_password.html   # Reset password form
│   ├── dashboard.html        # Main dashboard with stats & alerts
│   ├── profile.html          # Employee profile & document progress
│   ├── all_employees.html    # Employee list (HR/Manager view)
│   ├── leaves.html           # Leave records list
│   ├── add_leave.html        # Apply for leave form (Full/Half day)
│   ├── timesheets.html       # Timesheet list & calendar view
│   ├── add_timesheet.html    # Daily timesheet submission
│   ├── add_weekly_timesheet.html # Weekly timesheet submission
│   ├── projects.html         # Project list
│   ├── helpdesk.html         # Help Desk ticketing interface
│   ├── assets.html           # Asset tracking (HR)
│   ├── agreement.html        # Digital device agreement & signature
│   ├── reimbursement.html    # Reimbursement claim & approval
│   ├── attendance.html       # Advanced attendance tracking
│   ├── payslips.html         # Payslip records
│   ├── policies.html         # Company policies
│   ├── bank_admin.html       # Bank detail verification (HR)
│   └── change_password.html  # Password change page
│
├── static/
│   ├── css/
│   │   └── style.css         # Global stylesheet
│   ├── images/               # Logos and avatars
│   └── videos/               # Video assets
│
└── uploads/                  # Uploaded files directory (receipts, docs)
```

---

## Getting Started

### Prerequisites

- **Python 3.8+**
- **pip** (Python package manager)
- Access to the **backend API server** (running on a separate machine or port)

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
   pip install flask requests
   ```

### Configuration

Edit the `BASE_URL` variable in `app.py` to point to your backend API server:

```python
# app.py
BASE_URL = "http://<BACKEND_IP>:5001"
```

### Running the Application

```bash
python app.py
```

The application will start on **http://localhost:5002**.

---

## User Roles & Permissions

| Role         | Prefix | Key Permissions                                                    |
|--------------|--------|--------------------------------------------------------------------|
| **HR**       | `H_`   | Full access — manage employees, projects, verify info, assets, helpdesk |
| **Manager**  | `M_`   | Manage teams, approve/reject timesheets, leaves, and reimbursements |
| **Employee** | `T_`   | Submit timesheets/leaves, view profile, raise tickets, sign agreements |

---

## Modules

### Authentication
- **Login / Logout** — JWT-based authentication.
- **Password Management** — Forgot/Reset workflow and first-login enforcement.

### Dashboard
- **Stats Overview** — Dynamic cards for Employees, Tickets, and Reimbursements.
- **Alert Center** — Pending device agreements and missing timesheet notifications.
- **Calendar Snippets** — Upcoming birthdays and holidays.

### Help Desk
- **Ticketing** — Employees can raise tickets with priority levels.
- **Resolution** — HR can assign tickets, update status, and communicate via internal message threads.

### Assets & Devices
- **Inventory** — Tracking of company assets (Laptops, etc.) issued to employees.
- **E-Agreements** — Digital signature-based device usage agreements.

### Reimbursements
- **Claims** — Submit reimbursement requests with receipt attachments.
- **Workflow** — Managed approval process with payment status tracking.

### Attendance
- **Advanced Tracking** — Date-range filtering for detailed attendance logs.
- **Metrics** — Automated calculation of Average Hours, Overtime, and Late Logins.

### Leave Management
- **Flexibility** — Support for Full-day and Half-day leaves.
- **Balance Tracking** — Detailed breakdown of Sick, Casual, and Earned leaves.

### Timesheet Management
- **Daily/Weekly** — Flexible submission options for project-based time logging.
- **Calendar Integration** — Visual tracking of holidays and missing entries.

---

## API Proxy Routes

The frontend acts as a proxy for the backend API. Key API routes exposed:

| Frontend Route                          | Backend Route                       | Method | Description                    |
|-----------------------------------------|-------------------------------------|--------|--------------------------------|
| `/api/helpdesk/`                        | `/helpdesk/`                        | GET    | List tickets                   |
| `/api/reimbursements`                   | `/reimbursements/`                  | POST   | Submit claim                   |
| `/api/leaves/calendar`                  | `/leaves/calendar`                  | GET    | Fetch leave calendar           |
| `/api/timesheets/calendar`              | `/timesheets/calendar`              | GET    | Fetch timesheet calendar        |
| `/api/notifications`                    | `/notifications/`                   | GET    | Fetch notifications            |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Open a Pull Request

---

## License

This project is proprietary. All rights reserved.
