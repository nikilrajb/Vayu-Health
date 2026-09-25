# Field evaluation protocol

The planner sample uses hypothetical costs/effects. The synthetic outcome CSV is preview-only. Never remove its synthetic marker to save it as measured evidence.

1. Identify the real facility, responsible operator, authorised action and independent reviewer. Record approval, coordinates, work order, permits, action timing and operating constraints. The software does not authorise industrial shutdowns.
2. Establish source contribution using an emissions inventory, equipment records, production rate, distance and weather. City PM values do not identify a responsible factory. PM10 includes PM2.5 only for comparable co-located measurements; do not subtract readings from different stations to infer source contributions.
3. Use calibrated co-located PM2.5/PM10 monitors at intervention and comparable untreated reference sites. Preserve instrument IDs, calibration records, original exports, units, weather, completeness and confounding source observations.
4. Pre-register action timing, comparison windows, primary metric and exclusions. This evaluator requires at least 24 continuous matched hourly records per site in each period. Longer repeated matched days and expert review are needed for credible inference; the minimum is an input rule, not statistical proof.
5. Assign, acknowledge, complete with evidence references, then request separate reviewer verification. An authenticated account identifies who reviewed; it does not establish accreditation or truth.
6. Fill measurement-template.csv: period before/after, site intervention/reference, timezone-aware timestamp on an hourly UTC boundary, PM in micrograms per cubic metre. Use actual observations, never model-filled gaps or zero placeholders.
7. Preview before saving. Unadjusted reduction = (before-after)/before for station-hours at screening index >=151. Reference-adjusted change = ((after-before)intervention-(after-before)reference)/hours*100 percentage points. Negative adjusted change means relative improvement. A zero baseline has no defined percentage.
8. Review weather, production and other sources. Replicated controlled comparisons are needed before attributing improvement to the intervention. This descriptive comparison alone does not demonstrate personal exposure reduction or physically validate an effect.
9. Regulatory compliance requires the relevant authority to identify applicable permits, limits, methods and reporting requirements and accept verified evidence. Workflow completion is a separate operational measure.

Evidence note template: Work order [real ID], completed [time], equipment [ID], original measurements [file reference], calibration [record ID], observations [details]. Replace every placeholder with real evidence.

Health guidance: https://www.airnow.gov/publications/air-quality-index/air-quality-guide-for-particle-pollution/
The software uses hourly US EPA PM screening thresholds, not official daily AQI, NowCast or India's CPCB AQI.
