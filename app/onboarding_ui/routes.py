from flask import render_template, redirect, url_for
from app.utils import role_required
from app.onboarding_ui import onboarding_bp


@onboarding_bp.route('/')
@role_required(['hr', 'admin'])
def dashboard():
    from app.utils import BASE_URL
    from flask import session
    return render_template('onboarding/dashboard.html', BASE_URL=BASE_URL, token=session.get('token'))


@onboarding_bp.route('/joinee-dashboard')
def joinee_dashboard():
    from flask import session
    from app.utils import BASE_URL
    if 'token' not in session:
        return redirect(url_for('auth.login'))
    role = str(session.get('role', '')).lower().strip()
    if role != 'onboarding_candidate':
        return redirect(url_for('dashboard.dashboard'))
    return render_template(
        'joinee/dashboard.html',
        BASE_URL=BASE_URL,
        token=session.get('token'),
        joinee_name=session.get('full_name') or session.get('display_name') or session.get('employee_name', 'New Joinee')
    )


@onboarding_bp.route('/documents/<int:document_id>/view')
def view_document(document_id):
    from flask import session, Response, abort
    from app.utils import BASE_URL
    import requests

    token = session.get('token')
    if not token:
        return redirect(url_for('auth.login'))

    try:
        # Securely proxy the document request to the backend API
        resp = requests.get(
            f"{BASE_URL}/onboarding/documents/{document_id}/file",
            headers={"Authorization": f"Bearer {token}"},
            stream=True,
            timeout=10
        )
        if resp.status_code != 200:
            return abort(resp.status_code)

        def generate():
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
                    
        # Forward relevant headers so the browser knows the file type and name
        headers = {k: v for k, v in resp.headers.items() if k.lower() in ['content-type', 'content-disposition', 'content-length']}
        return Response(generate(), headers=headers)
        
    except requests.RequestException as e:
        return f"Error connecting to backend: {str(e)}", 502
    except Exception as e:
        return f"Error retrieving document: {str(e)}", 500