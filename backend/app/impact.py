"""Descriptive paired-site evaluation. It does not establish causation."""
import csv
import io
import math
from datetime import datetime, timezone
from app.aqi import aqi_from_pm


def evaluate_csv(content):
    groups = {(period,site): {} for period in ['before','after'] for site in ['intervention','reference']}
    reader=csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
    required={'period','site','timestamp','pm25_ugm3','pm10_ugm3'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('CSV requires period,site,timestamp,pm25_ugm3,pm10_ugm3 columns.')
    for row in reader:
        if any(row.get(k) is None for k in required):
            raise ValueError('Each CSV row must contain all required fields.')
        key=(row['period'].strip(),row['site'].strip())
        if key not in groups:
            raise ValueError('Period must be before/after; site must be intervention/reference.')
        try:
            stamp=datetime.fromisoformat(row['timestamp'].replace('Z','+00:00'))
            if stamp.tzinfo is None:
                raise ValueError()
            stamp=stamp.astimezone(timezone.utc)
            a,b=float(row['pm25_ugm3']),float(row['pm10_ugm3'])
            if not all(math.isfinite(v) and v>=0 for v in [a,b]) or stamp.minute or stamp.second or stamp.microsecond:
                raise ValueError()
        except (ValueError,TypeError):
            raise ValueError('Use timezone-aware hourly timestamps and finite nonnegative concentrations.') from None
        if stamp in groups[key]:
            raise ValueError('Duplicate site/hour in CSV.')
        groups[key][stamp]=aqi_from_pm(a,b)[0]>=151
    n=len(groups['before','intervention'])
    if n<24 or any(len(g)!=n for g in groups.values()):
        raise ValueError('Provide equal windows with at least 24 measured hours in each period/site.')
    for period in ['before','after']:
        times=sorted(groups[period,'intervention'])
        if set(times)!=set(groups[period,'reference']):
            raise ValueError('Intervention and reference timestamps must align within each period.')
        if any((b-a).total_seconds()!=3600 for a,b in zip(times,times[1:])):
            raise ValueError('Use continuous hourly windows; missing hours cannot count as clean air.')
    if max(groups['before','intervention'])>=min(groups['after','intervention']):
        raise ValueError('Before window must precede after window.')
    counts={f'{p}_{s}':sum(values.values()) for (p,s),values in groups.items()}
    before,after=counts['before_intervention'],counts['after_intervention']
    return {'hours_per_window':n,'high_risk_hours':counts,
            'dataset_kind': 'synthetic' if 'dataset_kind' in (reader.fieldnames or []) and 'synthetic' in content.lower() else 'operator_supplied_unverified',
            'observed_reduction_pct':round(100*(before-after)/before,2) if before else None,
            'control_adjusted_change_percentage_points':round(100*((after-before)-(counts['after_reference']-counts['before_reference']))/n,2),
            'note':'Counts measured station hours with hourly PM screening index >=151, not personal exposure. Negative adjusted change means improvement relative to the reference. This descriptive comparison does not control all confounding or prove causation. Input measurements and units require independent verification.'}
