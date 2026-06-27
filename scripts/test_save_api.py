import os
import json

# Run in development so app allows sqlite fallback
os.environ['FLASK_ENV'] = 'development'
os.environ['SECRET_KEY'] = 'test-secret'
# Ensure admin session default is available
os.environ.pop('ADMIN_PASSWORD_HASH', None)
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.admin.auth import ADMIN_SESSION_KEY

app = create_app()
app.testing = True

with app.test_client() as client:
    # Simulate admin session
    with client.session_transaction() as sess:
        sess[ADMIN_SESSION_KEY] = True

    payload = {
        "rows": [
            {
                "id": -1,
                "consignment_number": "TEST123",
                "status": "In Transit",
                "pickup_pincode": "560001",
                "drop_pincode": "560002",
                "pickup_address": "1 Test St",
                "drop_address": "2 Test Ave",
                "pickup_tag": "TAG1",
                "drop_tag": "TAG2",
                "pickup_date": "01-01-2026",
                "drop_date": "05-01-2026",
                "eta": "05-01-2026",
            }
        ],
        "deleted_ids": []
    }

    resp = client.post('/admin/consignments/save', data=json.dumps(payload), content_type='application/json')
    print('Status:', resp.status_code)
    try:
        print('JSON:', resp.get_json())
    except Exception:
        print('Text:', resp.get_data(as_text=True))
