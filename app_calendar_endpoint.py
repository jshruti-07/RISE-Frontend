# This file contains the calendar API endpoint code
# Add this to app.py after the add_weekly_timesheet function

@app.route('/api/timesheets/calendar')
@role_required(['employee', 'hr', 'manager'])
def api_timesheets_calendar():
    from datetime import datetime
    from calendar import monthrange
    
    year = int(request.args.get('year', datetime.now().year))
    month = int(request.args.get('month', datetime.now().month))
    
    current_user = session.get('employee_name')
    user_role = session.get('role')
    
    # Fetch timesheets
    timesheets = []
    try:
        res = requests.get(f"{BASE_URL}/timesheets", headers=get_headers())
        if res.status_code == 200:
            data = res.json()
            all_timesheets = data.get("timesheets", [])
            if user_role == 'employee':
                timesheets = [t for t in all_timesheets if t.get('employee_name') == current_user]
            else:
                timesheets = all_timesheets
    except Exception as e:
        print("ERROR fetching timesheets:", e)
    
    # Fetch holidays
    holidays = []
    try:
        holiday_res = requests.get(f"{BASE_URL}/holidays?year={year}", headers=get_headers())
        if holiday_res.status_code == 200:
            holidays = holiday_res.json().get("holidays", [])
    except Exception as e:
        print("ERROR fetching holidays:", e)
    
    # Fetch approved leaves
    leaves = []
    try:
        leave_res = requests.get(f"{BASE_URL}/leaves", headers=get_headers())
        if leave_res.status_code == 200:
            all_leaves = leave_res.json().get("leaves", [])
            if user_role == 'employee':
                leaves = [l for l in all_leaves if l.get('employee_name') == current_user and l.get('status') == 'approved']
            else:
                leaves = [l for l in all_leaves if l.get('status') == 'approved']
    except Exception as e:
        print("ERROR fetching leaves:", e)
    
    # Build calendar data
    days = {}
    first_day, last_day = monthrange(year, month)
    for day in range(1, last_day + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        day_of_week = date_obj.weekday()
        
        status = 'missing'
        label = 'Missing Entry'
        hours = 0
        holiday_info = None
        
        if day_of_week >= 5:
            status = 'weekend'
            label = 'Weekend'
        
        for holiday in holidays:
            holiday_date = str(holiday.get("date", ""))
            if holiday_date.startswith(date_str):
                status = 'holiday'
                label = 'Holiday'
                holiday_info = holiday
                break
        
        for leave in leaves:
            try:
                start_date = datetime.strptime(leave.get('start_date'), "%Y-%m-%d")
                end_date = datetime.strptime(leave.get('end_date'), "%Y-%m-%d")
                if start_date <= date_obj <= end_date:
                    status = 'leave'
                    label = 'Approved Leave'
                    break
            except:
                continue
        
        if status not in ['weekend', 'holiday', 'leave']:
            for ts in timesheets:
                if ts.get('start_date', '').startswith(date_str):
                    status = 'completed'
                    label = 'Completed'
                    hours = ts.get('hours', 0)
                    break
        
        if date_obj > datetime.now():
            status = 'future'
            label = 'Future'
        
        days[date_str] = {
            'status': status,
            'label': label,
            'hours': hours,
            'holiday': holiday_info
        }
    
    return jsonify({
        'success': True,
        'days': days
    })
