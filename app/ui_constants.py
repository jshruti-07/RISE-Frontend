# Centralized Branding and Terminology Configuration
# Use this file to manage all UI labels globally.

UI_LABELS = {
    "EMPLOYEE": "Team Member",
    "EMPLOYEES": "Team Members",
    "TEAM": "Team",
    "EMPLOYEE_DIRECTORY": "Team Directory",
    "TOTAL_EMPLOYEES": "Total Team Members",
    "EMPLOYEE_NAME": "Team Member Name",
    "EMPLOYEE_ID": "Team Member ID",
    "EMPLOYEE_DETAILS": "Team Member Details",
    "EMPLOYEE_PROFILE": "Team Member Profile",
    "EMPLOYEE_MANAGEMENT": "Team Management",
    "ADD_EMPLOYEE": "Add Team Member",
    "EDIT_EMPLOYEE": "Edit Team Member",
    "VIEW_EMPLOYEE": "View Team Member",
    "NEW_EMPLOYEE": "New Team Member",
    "EMPLOYEE_RECORDS": "Team Member Records",
    "TEAM_PENDING_TIMESHEETS": "Team Pending Timesheets",
    "TEAM_LEAVES": "Team Leaves",
    "AVAILABLE_EMPLOYEES": "Available Team Members",
    "SELECT_TEAM_MEMBERS": "Select Team Members",
    "ASSIGN_TEAM_MEMBERS": "Assign Team Members",
    "EMPLOYEE_ADDED_SUCCESS": "Team member added successfully",
    "EMPLOYEE_UPDATED_SUCCESS": "Team member updated successfully",
    "EMPLOYEE_DELETED_SUCCESS": "Team member deleted successfully",
    "CONFIRM_DELETE_EMPLOYEE": "Are you sure you want to delete this team member?",
    "BANK_DETAILS_VIEW_ONLY": "Bank details are currently view-only.",
}

# Feature Flags and Global UI Configuration
UI_CONFIG = {
    "BANK_DETAILS_READ_ONLY": True,  # Set to False to enable editing
}

def get_ui_labels():
    return UI_LABELS
