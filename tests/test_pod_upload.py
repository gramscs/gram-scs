import os
import base64
from io import BytesIO

import pytest


def setup_env_for_app(tmp_path):
    # Minimal env setup required by app
    os.environ['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'test-secret')
    from werkzeug.security import generate_password_hash
    os.environ['ADMIN_PASSWORD_HASH'] = generate_password_hash(os.environ.get('ADMIN_PASSWORD', 'admin-pass'))
    os.environ['FLASK_ENV'] = 'development'


def test_pod_upload_and_delete(tmp_path):
    setup_env_for_app(tmp_path)

    # Import app factory after env set
    from app import create_app
    from app.models import db, Consignment

    app = create_app()
    # isolate instance path to tmp
    app.instance_path = str(tmp_path / 'instance')
    os.makedirs(app.instance_path, exist_ok=True)

    client = app.test_client()

    with app.app_context():
        # ensure a fresh schema for test (drop any previous sqlite test.db)
        try:
            db.drop_all()
        except Exception:
            pass
        db.create_all()
        c = Consignment(consignment_number='TEST-CN-1', status='In Transit')
        db.session.add(c)
        db.session.commit()
        cid = c.id

    # Authenticate session as admin
    from app.admin.auth import ADMIN_SESSION_KEY
    with client.session_transaction() as sess:
        sess[ADMIN_SESSION_KEY] = True

    # Upload POD
    data = {
        'file': (BytesIO(b'pod-data-bytes'), 'pod.jpg')
    }
    resp = client.post(f'/admin/consignments/{cid}/pod', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    j = resp.get_json()
    assert j and j.get('success') is True

    # Check that GET serves the file (local fallback path)
    get_resp = client.get(f'/admin/consignments/{cid}/pod')
    assert get_resp.status_code == 200
    assert get_resp.data == b'pod-data-bytes'

    # Delete POD
    del_resp = client.delete(f'/admin/consignments/{cid}/pod')
    assert del_resp.status_code == 200
    j2 = del_resp.get_json()
    assert j2 and j2.get('success') is True

    # Confirm DB field cleared
    with app.app_context():
        row = db.session.get(Consignment, cid)
        assert row.pod_image in (None, '')


def test_staged_pod_upload_saves_with_row(tmp_path):
    setup_env_for_app(tmp_path)

    from app import create_app
    from app.models import db, Consignment

    app = create_app()
    app.instance_path = str(tmp_path / 'instance')
    os.makedirs(app.instance_path, exist_ok=True)

    client = app.test_client()

    with app.app_context():
        try:
            db.drop_all()
        except Exception:
            pass
        db.create_all()

    from app.admin.auth import ADMIN_SESSION_KEY
    with client.session_transaction() as sess:
        sess[ADMIN_SESSION_KEY] = True

    pod_bytes = b'fake-image-bytes'
    pod_data_url = 'data:image/jpeg;base64,' + base64.b64encode(pod_bytes).decode('ascii')

    payload = {
        'rows': [
            {
                'id': None,
                'consignment_number': 'STAGEDCN1',
                'status': 'In Transit',
                'pickup_pincode': '',
                'pickup_address': '',
                'pickup_tag': '',
                'pickup_date': '',
                'drop_pincode': '',
                'drop_address': '',
                'drop_tag': '',
                'drop_date': '',
                'eta': '',
                'pod_file_name': 'pod.jpg',
                'pod_file_type': 'image/jpeg',
                'pod_file_data': pod_data_url,
            }
        ],
        'deleted_ids': [],
    }

    resp = client.post('/admin/consignments/save', json=payload)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body and body.get('success') is True

    with app.app_context():
        row = Consignment.query.filter_by(consignment_number='STAGEDCN1').first()
        assert row is not None
        assert row.pod_image
        pod_path = os.path.join(app.instance_path, 'uploads', row.pod_image)
        assert os.path.exists(pod_path)
        with open(pod_path, 'rb') as file_handle:
            assert file_handle.read() == pod_bytes


class FakeSupabaseBucket:
    def __init__(self, store, bucket_name):
        self.store = store
        self.bucket_name = bucket_name

    def upload(self, object_path, file_obj, options=None):
        if hasattr(file_obj, "read"):
            content = file_obj.read()
        else:
            content = file_obj
        if isinstance(content, bytearray):
            content = bytes(content)
        self.store[(self.bucket_name, object_path)] = content
        return {"path": object_path}

    def download(self, object_path):
        return self.store[(self.bucket_name, object_path)]

    def remove(self, object_paths):
        for object_path in object_paths:
            self.store.pop((self.bucket_name, object_path), None)
        return []


class FakeSupabaseStorage:
    def __init__(self, store):
        self.store = store

    def from_(self, bucket_name):
        return FakeSupabaseBucket(self.store, bucket_name)


class FakeSupabaseClient:
    def __init__(self):
        self.store = {}
        self.storage = FakeSupabaseStorage(self.store)


class BytesOnlySupabaseBucket:
    def __init__(self, store, bucket_name):
        self.store = store
        self.bucket_name = bucket_name

    def upload(self, object_path, file_obj, options=None):
        assert isinstance(file_obj, (bytes, bytearray))
        self.store[(self.bucket_name, object_path)] = bytes(file_obj)
        return {"path": object_path}


class BytesOnlySupabaseStorage:
    def __init__(self, store):
        self.store = store

    def from_(self, bucket_name):
        return BytesOnlySupabaseBucket(self.store, bucket_name)


class BytesOnlySupabaseClient:
    def __init__(self):
        self.store = {}
        self.storage = BytesOnlySupabaseStorage(self.store)


def test_store_pod_bytes_uploads_raw_bytes_to_supabase(monkeypatch):
    import app.admin.consignment_controller as controller

    fake_supabase = BytesOnlySupabaseClient()
    monkeypatch.setattr(controller, '_get_supabase_client', lambda: fake_supabase)

    result = controller._store_pod_bytes('pod.jpg', b'raw-bytes', 'image/jpeg')

    assert result == 'supabase:pod-uploads/consignments/pod.jpg'
    assert fake_supabase.store[('pod-uploads', 'consignments/pod.jpg')] == b'raw-bytes'


def test_supabase_pod_upload_serves_permanent_app_endpoint_without_signed_url(tmp_path, monkeypatch):
    setup_env_for_app(tmp_path)

    from app import create_app
    from app.models import db, Consignment
    import app.admin.consignment_controller as controller

    fake_supabase = FakeSupabaseClient()
    monkeypatch.setattr(controller, '_get_supabase_client', lambda: fake_supabase)
    monkeypatch.setenv('SUPABASE_BUCKET', 'pod-uploads')

    app = create_app()
    app.instance_path = str(tmp_path / 'instance')
    os.makedirs(app.instance_path, exist_ok=True)

    client = app.test_client()

    with app.app_context():
        try:
            db.drop_all()
        except Exception:
            pass
        db.create_all()
        c = Consignment(consignment_number='SUPACN1', status='In Transit')
        db.session.add(c)
        db.session.commit()
        cid = c.id

    from app.admin.auth import ADMIN_SESSION_KEY
    with client.session_transaction() as sess:
        sess[ADMIN_SESSION_KEY] = True

    resp = client.post(
        f'/admin/consignments/{cid}/pod',
        data={'file': (BytesIO(b'supabase-pod-bytes'), 'pod.jpg')},
        content_type='multipart/form-data',
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body and body.get('success') is True
    assert body['pod_image'].startswith('supabase:pod-uploads/')

    with app.app_context():
        row = Consignment.query.get(cid)
        assert row.pod_image == body['pod_image']

    get_resp = client.get(f'/admin/consignments/{cid}/pod')
    assert get_resp.status_code == 200
    assert get_resp.data == b'supabase-pod-bytes'
    assert get_resp.location is None


def test_save_rejects_external_pod_url(tmp_path):
    setup_env_for_app(tmp_path)

    from app import create_app
    from app.models import db

    app = create_app()
    app.instance_path = str(tmp_path / 'instance')
    os.makedirs(app.instance_path, exist_ok=True)

    client = app.test_client()

    with app.app_context():
        try:
            db.drop_all()
        except Exception:
            pass
        db.create_all()

    from app.admin.auth import ADMIN_SESSION_KEY
    with client.session_transaction() as sess:
        sess[ADMIN_SESSION_KEY] = True

    payload = {
        'rows': [
            {
                'id': None,
                'consignment_number': 'URLPOD001',
                'status': 'In Transit',
                'pickup_pincode': '',
                'pickup_address': '',
                'pickup_tag': '',
                'pickup_date': '',
                'drop_pincode': '',
                'drop_address': '',
                'drop_tag': '',
                'drop_date': '',
                'eta': '',
                'pod_image': 'https://example.com/signed-or-temporary-url.jpg',
            }
        ],
        'deleted_ids': [],
    }

    resp = client.post('/admin/consignments/save', json=payload)
    assert resp.status_code == 400
    body = resp.get_json()
    assert body and body.get('success') is False
    assert isinstance(body.get('errors'), list)
    assert any(error.get('field') == 'pod_image' for error in body.get('errors'))


def test_track_pod_streams_supabase_file_without_signed_url(tmp_path, monkeypatch):
    setup_env_for_app(tmp_path)

    from app import create_app
    from app.models import db, Consignment
    import app.admin.consignment_controller as controller

    fake_supabase = FakeSupabaseClient()
    fake_supabase.store[('pod-uploads', '42/pod.jpg')] = b'track-supabase-pod-bytes'
    monkeypatch.setattr(controller, '_get_supabase_client', lambda: fake_supabase)

    app = create_app()
    app.instance_path = str(tmp_path / 'instance')
    os.makedirs(app.instance_path, exist_ok=True)

    client = app.test_client()

    with app.app_context():
        try:
            db.drop_all()
        except Exception:
            pass
        db.create_all()
        db.session.add(Consignment(
            consignment_number='TRKCN1',
            status='Delivered',
            pod_image='supabase:pod-uploads/42/pod.jpg',
        ))
        db.session.commit()

    get_resp = client.get('/track/pod/TRKCN1')
    assert get_resp.status_code == 200
    assert get_resp.data == b'track-supabase-pod-bytes'
    assert get_resp.location is None
    assert 'attachment' in get_resp.headers.get('Content-Disposition', '')
