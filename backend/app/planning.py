"""Budget-constrained scenario optimizer; effectiveness is an operator assumption."""
from app.aqi import aqi_from_pm


def optimize(rows, options, budget):
    baseline = sum(r["aqi"] >= 151 for r in rows)
    best = None
    for mask in range(1 << len(options)):
        chosen = [o for i,o in enumerate(options) if mask & (1 << i)]
        cost = sum(o["cost"] for o in chosen)
        if cost > budget:
            continue
        risks = []
        for row in rows:
            a,b = row["pm25"],row["pm10"]
            for option in chosen:
                if option["start_hour"] <= row["horizon_h"] <= option["end_hour"]:
                    a *= 1-option["pm25_reduction_pct"]/100
                    b *= 1-option["pm10_reduction_pct"]/100
            risks.append(aqi_from_pm(a,b)[0])
        hours = sum(r >= 151 for r in risks)
        score = (hours, sum(risks), cost, len(chosen))
        if best is None or score < best[0]:
            best = (score, chosen, risks)
    score, selected, risks = best
    return {"selected": selected, "cost": score[2], "baseline_peak_hours": baseline,
            "scenario_peak_hours": score[0], "scenario_risk": risks,
            "scenario_reduction_pct": round(100*(baseline-score[0])/baseline,1) if baseline else None,
            "note": "Optimizes forecast hours with screening index >=151, then summed risk, under the entered budget. Effects combine multiplicatively and are unvalidated operator assumptions. This is not measured exposure reduction or a causal industrial emissions model."}
