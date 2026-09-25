import pandas as pd
import pytest
from app.impact import evaluate_csv


def sample():
    lines=['period,site,timestamp,pm25_ugm3,pm10_ugm3']
    for period,date in [('before','2026-09-01'),('after','2026-09-03')]:
        for site in ['intervention','reference']:
            for stamp in pd.date_range(date,periods=24,freq='h',tz='UTC'):
                value=20 if period=='after' and site=='intervention' else 80
                lines.append(f'{period},{site},{stamp.isoformat()},{value},100')
    return '\n'.join(lines)


def test_controlled_hour_comparison():
    result=evaluate_csv(sample())
    assert result['observed_reduction_pct']==100
    assert result['control_adjusted_change_percentage_points']==-100
    assert result['high_risk_hours']['before_intervention']==24


def test_missing_hours_and_naive_time_are_rejected():
    with pytest.raises(ValueError):evaluate_csv('\n'.join(sample().splitlines()[:-1]))
    with pytest.raises(ValueError):evaluate_csv(sample().replace('+00:00',''))


def test_zero_baseline_is_not_fake_improvement():
    result=evaluate_csv(sample().replace(',80,100',',20,100'))
    assert result['observed_reduction_pct'] is None
