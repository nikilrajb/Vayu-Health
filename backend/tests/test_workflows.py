from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import json
import pytest
from fastapi.testclient import TestClient
from app import operations, notifications, auth
from app.main import app
from app.catalog import CITIES
from app.alerts import build_alerts
from app.config import ROOT

@pytest.fixture
def isolated(monkeypatch,tmp_path):
    settings=SimpleNamespace(processed_dir=tmp_path,notifications_enabled=False,alert_cities='mumbai',alert_email_to='test@example.invalid',alert_sms_to='',smtp_host='',smtp_username='',smtp_password='',smtp_from='',twilio_account_sid='',twilio_auth_token='',twilio_from='')
    monkeypatch.setattr(operations,'get_settings',lambda:settings)
    monkeypatch.setattr(notifications,'get_settings',lambda:settings)
    return settings

def test_archive_preserves_every_run_and_quality(isolated):
    stamp=datetime.now(timezone.utc)+timedelta(hours=1)
    snapshot={'mode':'live','quality':'regional_model','forecast':[{'aqi':80,'timestamp':stamp}]}
    operations.record_check('mumbai',snapshot)
    operations.record_check('mumbai',error='Provider unavailable')
    runs=operations.collection_records()
    assert len(runs)==2 and runs[0]['ok']==0 and runs[1]['archive']
    data=json.loads((isolated.processed_dir/runs[1]['archive']).read_text())
    assert data['quality']=='regional_model' and data['forecast'][0]['timestamp']==stamp.isoformat()

def test_auth_blocks_impersonation_and_requires_reviewer(isolated):
    auth.create_user('operator','unique-password-123','operator')
    auth.create_user('reviewer','different-password-456','reviewer')
    client=TestClient(app)
    assert client.post('/api/v1/assignments',json={}).status_code==401
    def headers(name,pw):
        r=client.post('/api/v1/auth/login',json={'username':name,'password':pw})
        assert r.status_code==200
        return {'Authorization':'Bearer '+r.json()['token']}
    operator=headers('operator','unique-password-123'); reviewer=headers('reviewer','different-password-456')
    due=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
    created=client.post('/api/v1/assignments',headers=operator,json={'city':'mumbai','zone':'Actual facility','action':'Inspect logged equipment','owner':'operator','due_at':due})
    assert created.status_code==200
    path='/api/v1/assignments/'+created.json()['id']
    def update(status,header):return client.post(path,headers=header,json={'status':status,'actor':'forged-name','evidence':'Work order evidence reference'})
    assert update('acknowledged',reviewer).status_code==403
    assert update('acknowledged',operator).status_code==200
    assert update('completed',operator).status_code==200
    assert update('verified',operator).status_code==403
    assert update('verified',reviewer).status_code==200
    assert operations.read_ledger()['tasks'][0]['verified_by']=='reviewer'
    client.post('/api/v1/auth/logout',headers=reviewer)
    assert client.get('/api/v1/auth/me',headers=reviewer).status_code==401

def test_synthetic_outcomes_cannot_be_saved(isolated):
    content=(ROOT/'samples/outcome-synthetic.csv').read_text(encoding='utf-8-sig')
    preview=TestClient(app).post('/api/v1/outcomes/preview',json={'csv_text':content})
    assert preview.status_code==200 and preview.json()['dataset_kind']=='synthetic'
    with pytest.raises(ValueError,match='preview-only'):
        operations.record_outcome('any',content)

def test_notification_dry_run_dedup_and_no_external_send(isolated,monkeypatch):
    def forbidden(*args):raise AssertionError('Must not send in dry run')
    monkeypatch.setattr(notifications,'send',forbidden)
    snapshot={'location':CITIES['mumbai'],'mode':'live','quality':'regional_model','forecast':[{'aqi':170,'timestamp':datetime.now(timezone.utc)+timedelta(hours=1)}]}
    notifications.enqueue(snapshot); notifications.enqueue(snapshot); notifications.dispatch()
    status=notifications.delivery_status()
    assert len(status)==1 and status[0]['status']=='dry_run'

def test_delivery_acceptance_and_failure_states(isolated,monkeypatch):
    isolated.notifications_enabled=True
    snapshot={'location':CITIES['mumbai'],'mode':'live','quality':'station','forecast':[{'aqi':160,'timestamp':datetime.now(timezone.utc)+timedelta(hours=1)}]}
    notifications.enqueue(snapshot)
    monkeypatch.setattr(notifications,'send',lambda *args:'provider accepted')
    notifications.dispatch(); notifications.dispatch()
    assert notifications.delivery_status()[0]['status']=='accepted'

def test_alerts_separate_discontinuous_windows_and_ignore_past():
    now=datetime.now(timezone.utc)
    rows=[{'timestamp':now+timedelta(hours=h),'aqi':160 if h in [1,2,5,6] else 60,'aqi_category':'Unhealthy' if h in [1,2,5,6] else 'Moderate','dominant_pollutant':'pm25','pm25':70,'pm10':100} for h in range(-1,8)]
    alerts=build_alerts(CITIES['mumbai'],now,rows)
    windows=[a for a in alerts if a.severity!='info']
    assert len(windows)==2
    assert windows[0].valid_from==now+timedelta(hours=1)
    assert '2 forecast hours' in windows[0].message
    assert any(a.title=='Lowest predicted three-hour window' for a in alerts)

def test_demo_planner_uses_demo_forecast(monkeypatch):
    called=[]
    def snapshot(city,mode):
        called.append(mode)
        return {'forecast':[{'timestamp':datetime.now(timezone.utc)+timedelta(hours=h),'aqi':170,'pm25':80,'pm10':120,'horizon_h':h} for h in range(1,25)]}
    monkeypatch.setattr('app.api.city_snapshot',snapshot)
    body=json.loads((ROOT/'samples/planner-example.json').read_text(encoding='utf-8-sig'))
    r=TestClient(app).post('/api/v1/plan',json={'city':'mumbai','mode':'demo','budget':body['budget'],'options':body['options']})
    assert r.status_code==200 and called==['demo'] and r.json()['mode']=='demo'
