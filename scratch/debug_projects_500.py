
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from app import create_app
from flask import session

app = create_app()
app.config['TESTING'] = True
app.config['SECRET_KEY'] = 'dev'

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['role'] = 'hr'
        sess['employee_name'] = 'H_Saurabh'
        sess['token'] = 'fake-token'
    
    print("Testing /projects GET...")
    try:
        response = client.get('/projects')
        print(f"Status: {response.status_code}")
        if response.status_code == 500:
            print("ERROR: 500 Internal Server Error detected!")
            # We can't easily get the traceback here unless we catch it in the app
        else:
            print("Successfully accessed /projects")
    except Exception as e:
        print(f"Crashed with exception: {e}")
        import traceback
        traceback.print_exc()
