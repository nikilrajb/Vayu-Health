from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Depends
from app.auth import identity, login
from app.catalog import CITIES
from app.config import get_settings
from app.data.openaq import DataUnavailable
from app.services import city_snapshot, history, list_locations
from pydantic import BaseModel, Field, field_validator
from app.operations import read_ledger, transition, assign_task, transition_task, record_outcome
from datetime import datetime, timezone
from app.planning import optimize
from fastapi.responses import FileResponse
from app.operations import collection_records

router = APIRouter(prefix="/api/v1")


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


@router.post("/auth/login")
def sign_in(body: Credentials):
    result = login(body.username, body.password)
    if result is None:
        raise HTTPException(401, "Invalid credentials or too many attempts. After five failures, wait 15 minutes.")
    return result


@router.get("/auth/me")
def signed_in(user=Depends(identity)):
    return user


@router.post("/auth/logout")
def sign_out(user=Depends(identity)):
    from app.operations import database
    with database() as db:
        db.execute("DELETE FROM sessions WHERE username=?", (user["username"],))
    return {"status": "signed out"}


@router.get("/collections")
def collections():
    return {"storage": "data/processed/collections/<city>/<timestamp>.json", "runs": collection_records()}


@router.get("/collections/{run_id}/download")
def collection_download(run_id: int):
    from app.operations import database
    with database() as db:
        row = db.execute("SELECT archive FROM collection_runs WHERE id=?", (run_id,)).fetchone()
    if row is None or not row["archive"]:
        raise HTTPException(404, "No successful archive for this run")
    path = get_settings().processed_dir / row["archive"]
    if not path.is_file():
        raise HTTPException(404, "Archive file is missing")
    return FileResponse(path, media_type="application/json", filename=path.name)


class PlanOption(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    cost: float = Field(ge=0, le=100000000, allow_inf_nan=False)
    pm25_reduction_pct: float = Field(ge=0, le=80, allow_inf_nan=False)
    pm10_reduction_pct: float = Field(ge=0, le=80, allow_inf_nan=False)
    start_hour: int = Field(ge=1, le=24)
    end_hour: int = Field(ge=1, le=24)


class PlanRequest(BaseModel):
    city: str
    mode: Literal["live", "demo"] = "live"
    budget: float = Field(ge=0, le=100000000, allow_inf_nan=False)
    options: list[PlanOption] = Field(min_length=1, max_length=12)


@router.post("/plan")
def plan(body: PlanRequest):
    check_city(body.city)
    if any(o.start_hour > o.end_hour for o in body.options):
        raise HTTPException(422, "Action start must precede its end")
    try:
        snapshot = city_snapshot(body.city, body.mode)
    except DataUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    result = optimize(snapshot["forecast"], [o.model_dump() for o in body.options], body.budget)
    result.update(mode=body.mode, forecast_start=snapshot["forecast"][0]["timestamp"], forecast_end=snapshot["forecast"][-1]["timestamp"])
    return result


class AlertUpdate(BaseModel):
    status: Literal["acknowledged", "resolved"]
    owner: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=5, max_length=2000)

    @field_validator("owner", "note")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Enter a nonblank value")
        return value.strip()


class Assignment(BaseModel):
    city: str
    zone: str = Field(min_length=2, max_length=200)
    action: str = Field(min_length=5, max_length=2000)
    owner: str = Field(min_length=1, max_length=100)
    due_at: datetime


class TaskUpdate(BaseModel):
    status: Literal["acknowledged", "completed", "verified"]
    actor: str = Field(min_length=1, max_length=100)
    evidence: str = Field(min_length=5, max_length=2000)


class OutcomeInput(BaseModel):
    task_id: str
    csv_text: str = Field(min_length=20,max_length=200000)


class PreviewInput(BaseModel):
    csv_text: str = Field(min_length=20,max_length=200000)


@router.post("/outcomes/preview")
def preview_outcome(body: PreviewInput):
    from app.impact import evaluate_csv
    try:
        return evaluate_csv(body.csv_text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


@router.get("/samples/{filename}")
def sample_file(filename: str):
    from app.config import ROOT
    if filename not in {"planner-example.json", "outcome-synthetic.csv", "measurement-template.csv", "FIELD_PROTOCOL.md"}:
        raise HTTPException(404, "Unknown sample")
    return FileResponse(ROOT / "samples" / filename, filename=filename)


@router.post("/outcomes")
def outcome(body: OutcomeInput, user=Depends(identity)):
    try:
        return record_outcome(body.task_id,body.csv_text)
    except KeyError:
        raise HTTPException(404,"Assignment not found") from None
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None


@router.post("/assignments")
def create_assignment(body: Assignment, user=Depends(identity)):
    check_city(body.city)
    if not all(v.strip() for v in [body.zone,body.action,body.owner]) or body.due_at.tzinfo is None:
        raise HTTPException(422, "Enter real assignment details and a timezone-aware deadline.")
    due = body.due_at.astimezone(timezone.utc)
    if due <= datetime.now(timezone.utc):
        raise HTTPException(422, "Deadline must be in the future.")
    from app.operations import database
    with database() as db:
        owner = db.execute("SELECT username FROM users WHERE username=? AND role='operator'", (body.owner.strip().lower(),)).fetchone()
    if owner is None:
        raise HTTPException(422, "Assign to an existing operator account username.")
    body.owner = owner["username"]
    return {"id": assign_task(body.city,body.zone.strip(),body.action.strip(),body.owner.strip(),due.isoformat())}


@router.post("/assignments/{task_id}")
def update_assignment(task_id: str, body: TaskUpdate, user=Depends(identity)):
    from app.operations import database
    with database() as db:
        task = db.execute("SELECT owner FROM tasks WHERE id=?", (task_id,)).fetchone()
    if task is None:
        raise HTTPException(404, "Assignment not found")
    if body.status == "verified" and user["role"] != "reviewer":
        raise HTTPException(403, "An authenticated reviewer must verify evidence.")
    if body.status != "verified" and user["username"] != task["owner"]:
        raise HTTPException(403, "Only the assigned operator can acknowledge or complete this action.")
    body.actor = user["username"]
    if not body.actor.strip() or len(body.evidence.strip()) < 5:
        raise HTTPException(422, "Enter an actor and meaningful evidence note.")
    try:
        transition_task(task_id,body.status,body.actor.strip(),body.evidence.strip())
    except KeyError:
        raise HTTPException(404, "Assignment not found") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return {"status": body.status}


@router.get("/operations")
def operations():
    return read_ledger()


@router.post("/operations/{event_id:path}")
def update_operation(event_id: str, update: AlertUpdate, user=Depends(identity)):
    update.owner = user["username"]
    try:
        transition(event_id, update.status, update.owner, update.note)
    except KeyError:
        raise HTTPException(404, "Alert not found") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return {"status": update.status}


@router.get("/status")
def status():
    return {
        "openaq_configured": bool(get_settings().openaq_api_key),
        "airnow_configured": bool(get_settings().airnow_api_key),
        "live_provider": "OpenAQ v3",
        "regional_fallback": "CAMS Global via Open-Meteo (model estimates)",
        "weather_provider": "Open-Meteo",
        "cache_seconds": 600,
    }


@router.get("/notifications")
def notifications():
    from app.notifications import delivery_status
    settings = get_settings()
    return {"enabled": settings.notifications_enabled,
            "email_recipient_configured": bool(settings.alert_email_to),
            "sms_recipient_configured": bool(settings.alert_sms_to),
            "smtp_configured": all([settings.smtp_host,settings.smtp_username,settings.smtp_password,settings.smtp_from]),
            "sms_configured": all([settings.twilio_account_sid,settings.twilio_auth_token,settings.twilio_from]),
            "deliveries": delivery_status()}


@router.get("/locations")
def locations():
    return list_locations()


def check_city(city_id):
    if city_id not in CITIES:
        raise HTTPException(404, "Unknown city")


@router.get("/forecast/{city_id}")
def forecast(city_id: str, mode: Literal["live", "demo"] = "live"):
    check_city(city_id)
    try:
        return city_snapshot(city_id, mode)
    except DataUnavailable as exc:
        if exc.stations is not None:
            raise HTTPException(503, {"message": str(exc), "stations": exc.stations, "connected": True}) from None
        raise HTTPException(503, str(exc)) from None


@router.get("/history/{city_id}")
def city_history(
    city_id: str,
    hours: int = Query(72, ge=24, le=720),
    mode: Literal["live", "demo"] = "live",
):
    check_city(city_id)
    try:
        frame = history(city_id, hours, mode).copy()
        frame["timestamp"] = frame.timestamp.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "city_id": city_id,
            "mode": mode,
            "points": frame.replace({float("nan"): None}).to_dict(orient="records"),
        }
    except DataUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
