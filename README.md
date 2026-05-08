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
│   run.py — port 5002 │ ───────> │    port 5001 (remote)    │
│                      │          │                          │
│  • Blueprint Modular │          │  • REST API endpoints    │
│  • Session mgmt      │          │  • MySQL database        │
│  • Proxy routes       │          │  • JWT authentication    │
│  • .env config        │          │  • File uploads          │
└──────────────────────┘          └──────────────────────────┘
```

The **frontend** is a modular Flask application using the **Application Factory** pattern. It handles rendering, session management, and role-based access control across several logical Blueprints. It **proxies** all data operations to a **separate backend API** via HTTP requests.

---

## Tech Stack

| Layer           | Technology                                              |
|-----------------|--------------------------------------------------------|
| **Frontend**    | Flask (Blueprints), Jinja2, HTML5, CSS3, JavaScript     |
| **Backend API** | Flask (separate server), Flask Blueprints               |
| **Config**      | `python-dotenv` (.env file support)                     |
| **Database**    | MySQL (Backend), `projects.json` (Local fallback)       |
| **Auth**        | JWT (JSON Web Tokens)                                   |

---

## Project Structure

```
Altzor3/
├── run.py                    # Main entry point (starts the app)
├── app/                      # Main application package
│   ├── __init__.py           # Application factory & Blueprint registration
│   ├── utils.py              # Shared decorators, helpers, and config
│   └── routes/               # Modular route definitions (Blueprints)
│       ├── auth.py           # Login, Logout, Password management
│       ├── dashboard.py      # Main dashboard logic
│       ├── employees.py      # Employee management
│       ├── projects.py       # Project tracking
│       ├── work_management.py # Timesheets, Leaves, Attendance
│       ├── admin.py          # Helpdesk, Reimbursements, Assets, Policies
│       └── user.py           # Profile and Bank verification
├── .env                      # Environment variables (Secret keys, API URLs)
├── projects.json             # Local project data store
├── helpdesk_messages.json    # Local storage for ticket messaging
├── app.log                   # Application logs
├── templates/                # Jinja2 templates (updated for Blueprints)
├── static/                   # Global CSS, JS, and Images
└── uploads/                  # Uploaded files directory
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
   pip install flask requests python-dotenv
   ```

### Configuration

Create a `.env` file in the root directory (copy from `.env.example` if available) and configure your environment variables:

```ini
# .env
SECRET_KEY=your_secure_random_string
BACKEND_URL=http://<BACKEND_IP>:5001
```

### Running the Application

```bash
python run.py
```

The application will start on **http://localhost:5002**.

---

## 📱 Mobile & Tablet Access

To access the Altzor HR system from any device (Mobile, Tablet, Laptop) on your local network:

1. **Find your Local IP Address**:
   - **Windows**: Open Command Prompt and type `ipconfig`. Look for "IPv4 Address" (e.g., `192.168.1.5`).
   - **Mac/Linux**: Open Terminal and type `ifconfig` or `ip addr`.

2. **Configure .env**:
   Ensure your `.env` file uses your actual IP instead of `localhost` for the backend so your mobile device can reach it:
   ```ini
   BACKEND_URL=http://192.168.1.5:5001
   ```

3. **Open Browser on Device**:
   Connect your device to the same Wi-Fi network and enter the following in your mobile browser:
   ```
   http://192.168.1.5:5002
   ```

4. **Responsive UI**:
   The interface is optimized for all screen sizes. On mobile, the sidebar collapses into a slide-out menu to maximize screen space.

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
