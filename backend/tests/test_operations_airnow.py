from types import SimpleNamespace
import pandas as pd
import pytest
from app.catalog import CITIES
from app.data.airnow import parse_rows
from app import operations
from app.planning import optimize
from app.ml.independent import forecast_pollutant
import numpy as np


def test_airnow_never_uses_aqi_or_nowcast_as_raw_concentration():
    now=pd.Timestamp.now(tz="UTC")
    row={"Latitude":19.076,"Longitude":72.8777,"UTC":now.isoformat(),"Parameter":"PM2.5","Unit":"UG/M3","Value":150,"AQI":180,"RawConcentration":12,"IntlAQSCode":"test"}
    rows=[row,{**row,"RawConcentration":None},{**row,"RawConcentration":-999}, {**row,"RawConcentration":1,"UTC":(now-pd.Timedelta(days=2)).isoformat()}]
    stations,history=parse_rows(rows,CITIES['mumbai'],now)
    assert len(stations)==1
    assert stations[0]['readings']['pm25']['value']==12
    assert list(history.values())[0].tolist()==[12]
    assert parse_rows([{**row,"RawConcentration":None}],CITIES['mumbai'],now)==([], {})


def test_durable_alert_workflow_and_audit(monkeypatch,tmp_path):
    monkeypatch.setattr(operations,'get_settings',lambda:SimpleNamespace(processed_dir=tmp_path))
    stamp=pd.Timestamp.now(tz='UTC')+pd.Timedelta(hours=1)
    snapshot={'mode':'live','quality':'regional_model','forecast':[{'aqi':160,'timestamp':stamp}]}
    operations.record_check('mumbai',snapshot)
    operations.record_check('mumbai',snapshot)
    alerts=operations.read_ledger()['alerts']; assert len(alerts)==1
    event=alerts[0]['id']
    with pytest.raises(ValueError): operations.transition(event,'resolved','Operator','Evidence')
    operations.transition(event,'acknowledged','Operator','Reviewed forecast')
    operations.transition(event,'resolved','Operator','Local advisory reviewed; logged evidence reference ABC')
    assert operations.read_ledger()['counts']=={'resolved':1}
    with operations.database() as db:
        assert db.execute('SELECT COUNT(*) FROM events').fetchone()[0]==2


def test_optimizer_respects_budget_and_active_hours():
    rows=[{'aqi':170,'pm25':80,'pm10':100,'horizon_h':h} for h in range(1,25)]
    options=[{'name':'A','cost':5,'pm25_reduction_pct':50,'pm10_reduction_pct':0,'start_hour':1,'end_hour':12},
             {'name':'B','cost':10,'pm25_reduction_pct':50,'pm10_reduction_pct':0,'start_hour':1,'end_hour':24}]
    result=optimize(rows,options,5)
    assert result['selected'][0]['name']=='A'
    assert result['cost']==5 and result['scenario_peak_hours']==12
    assert optimize(rows,options,0)['selected']==[]


def test_assignment_requires_evidence_review_and_tracks_denominator(monkeypatch,tmp_path):
    monkeypatch.setattr(operations,'get_settings',lambda:SimpleNamespace(processed_dir=tmp_path))
    due=(pd.Timestamp.now(tz='UTC')+pd.Timedelta(hours=2)).isoformat()
    task=operations.assign_task('mumbai','Test facility','Inspect filter','Operator',due)
    operations.transition_task(task,'acknowledged','Operator','Accepted responsibility')
    operations.transition_task(task,'completed','Operator','Maintenance record ABC attached in site log')
    with pytest.raises(ValueError): operations.transition_task(task,'verified','Operator','Self verification is invalid')
    operations.transition_task(task,'verified','Reviewer','Site log ABC checked independently')
    ledger=operations.read_ledger()
    assert ledger['tasks'][0]['status']=='verified'
    assert ledger['compliance']['rate_pct'] is None  # No assignments due yet.
    with operations.database() as db:
        assert db.execute('SELECT COUNT(*) FROM events').fetchone()[0]==4


def test_independent_weather_features_are_used():
    end=pd.Timestamp.now(tz='UTC').floor('h')
    idx=pd.date_range(end=end,periods=1080,freq='h'); t=np.arange(1080)
    series=pd.Series(30+12*np.sin(t*2*np.pi/24),index=idx)
    weather=pd.DataFrame({k:20+np.sin(t/24) for k in ['temperature_c','humidity_pct','wind_speed_ms','wind_direction_deg','pressure_hpa']},index=idx)
    result=forecast_pollutant(series,end,weather)
    assert result['metrics'] is not None
    assert result['method']=='Independent station + weather Extra Trees'
