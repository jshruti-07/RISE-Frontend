
import sys
import os
sys.path.append(os.getcwd())
from app import create_app
from flask import session

app = create_app()
app.config['TESTING'] = True
app.config['DEBUG'] = True
app.config['PROPAGATE_EXCEPTIONS'] = True

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['role'] = 'hr'
        sess['employee_name'] = 'H_Saurabh'
        sess['token'] = 'fake-token'
    
    print("Testing /projects GET with full traceback...")
    try:
        response = client.get('/projects')
        print(f"Status: {response.status_code}")
        if response.status_code == 500:
            print("ERROR: 500 detected. Traceback should follow if propagated.")
        else:
            # print(response.data.decode('utf-8')[:500])
            print("Successfully rendered (first 100 chars):", response.data.decode('utf-8')[:100])
    except Exception as e:
        print(f"Crashed with exception: {e}")
        import traceback
        traceback.print_exc()
