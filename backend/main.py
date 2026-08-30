"""
FastAPI app for the Sales Signal Intelligence Platform.

POST /sync   - pulls every deal from HubSpot, upserts it, records a
               snapshot for velocity history, and runs Claude classification
GET  /deals  - current deals with their latest signal, for the pipeline board
GET  /summary - counts for the top summary bar
GET  /stages  - pipeline stage list, in order, for the Kanban columns
"""

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai_engine import classify_deal
from database import Deal, DealSignal, DealSnapshot, get_avg_days_in_stage, get_session, init_db, utcnow
from hubspot_client import HubSpotClient

# These are this HubSpot portal's actual "Deals pipeline" stage IDs (fetched
# live via GET /crm/v3/pipelines/deals) - HubSpot assigns numeric internal
# IDs per-portal for the default pipeline rather than the classic named ones
# (appointmentscheduled, etc). If you're pointing this at a different
# portal, re-fetch that endpoint and update this map to match.
STAGE_LABELS = {
    "4226950866": "Visitor Engaged",
    "4226950867": "Lead Captured",
    "4226950868": "Lead Nurtured",
    "4226950869": "Demo Delivered",
    "4226950870": "In Negotiation",
    "4226950871": "Deal Won",
    "4226950872": "Deal Lost",
}
STAGE_ORDER = list(STAGE_LABELS.keys())


def stage_label(stage_id: str | None) -> str:
    return STAGE_LABELS.get(stage_id, stage_id or "Unknown Stage")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sales Signal Intelligence API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/stages")
def stages():
    return [{"id": stage_id, "label": label} for stage_id, label in STAGE_LABELS.items()]


@app.post("/sync")
def sync():
    hubspot = HubSpotClient()
    try:
        hs_deals = hubspot.get_deals()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HubSpot sync failed: {exc}") from exc

    session = get_session()
    now = utcnow()
    created = updated = signals_generated = 0

    try:
        for hs_deal in hs_deals:
            try:
                last_contact = hubspot.get_last_contact_date(hs_deal["id"])
            except Exception:
                last_contact = None  # an activity lookup failure shouldn't block the whole sync

            existing = session.get(Deal, hs_deal["id"])
            if existing is None:
                deal = Deal(
                    id=hs_deal["id"],
                    deal_name=hs_deal["deal_name"],
                    stage=hs_deal["stage"],
                    pipeline=hs_deal["pipeline"],
                    amount=hs_deal["amount"],
                    created_date=hs_deal["created_date"],
                    hs_last_modified_date=hs_deal["hs_last_modified_date"],
                    last_contact_date=last_contact,
                    stage_entered_at=now,
                    last_synced_at=now,
                )
                session.add(deal)
                created += 1
            else:
                deal = existing
                if deal.stage != hs_deal["stage"]:
                    deal.stage_entered_at = now  # stage changed since last sync - restart the clock
                deal.deal_name = hs_deal["deal_name"]
                deal.stage = hs_deal["stage"]
                deal.pipeline = hs_deal["pipeline"]
                deal.amount = hs_deal["amount"]
                deal.hs_last_modified_date = hs_deal["hs_last_modified_date"]
                deal.last_contact_date = last_contact
                deal.last_synced_at = now
                updated += 1

            session.add(
                DealSnapshot(
                    deal_id=deal.id,
                    stage=deal.stage,
                    amount=deal.amount,
                    last_contact_date=deal.last_contact_date,
                    snapshot_at=now,
                )
            )
            session.flush()

            days_in_stage = max((now - deal.stage_entered_at).days, 0)
            days_since_contact = (now - last_contact).days if last_contact else None
            avg_days = get_avg_days_in_stage(session, deal.stage, exclude_deal_id=deal.id)

            result = classify_deal(
                deal_name=deal.deal_name,
                stage_label=stage_label(deal.stage),
                days_in_stage=days_in_stage,
                days_since_contact=days_since_contact,
                avg_days_in_stage=avg_days,
                amount=float(deal.amount) if deal.amount is not None else None,
            )

            session.add(
                DealSignal(
                    deal_id=deal.id,
                    signal=result["signal"],
                    reason=result["reason"],
                    days_in_stage=days_in_stage,
                    days_since_contact=days_since_contact,
                    avg_days_in_stage=avg_days,
                    created_at=now,
                )
            )
            signals_generated += 1
            time.sleep(0.05)  # stay comfortably under HubSpot's burst rate limit

        session.commit()
    finally:
        session.close()

    return {
        "synced_deals": len(hs_deals),
        "created": created,
        "updated": updated,
        "signals_generated": signals_generated,
        "synced_at": now.isoformat(),
    }


@app.get("/deals")
def list_deals():
    session = get_session()
    try:
        now = utcnow()
        deals = session.query(Deal).all()
        response = []

        for deal in deals:
            latest_signal = (
                session.query(DealSignal)
                .filter(DealSignal.deal_id == deal.id)
                .order_by(DealSignal.created_at.desc())
                .first()
            )
            response.append(
                {
                    "id": deal.id,
                    "deal_name": deal.deal_name,
                    "stage": deal.stage,
                    "stage_label": stage_label(deal.stage),
                    "amount": float(deal.amount) if deal.amount is not None else None,
                    "days_in_stage": max((now - deal.stage_entered_at).days, 0),
                    "days_since_contact": (now - deal.last_contact_date).days if deal.last_contact_date else None,
                    "signal": latest_signal.signal if latest_signal else None,
                    "reason": latest_signal.reason if latest_signal else None,
                }
            )

        response.sort(key=lambda d: STAGE_ORDER.index(d["stage"]) if d["stage"] in STAGE_ORDER else len(STAGE_ORDER))
        return response
    finally:
        session.close()


@app.get("/summary")
def summary():
    session = get_session()
    try:
        deals = session.query(Deal).all()
        counts = {"at_risk": 0, "stalling": 0, "on_track": 0, "unclassified": 0}
        last_synced_at = None

        for deal in deals:
            latest_signal = (
                session.query(DealSignal)
                .filter(DealSignal.deal_id == deal.id)
                .order_by(DealSignal.created_at.desc())
                .first()
            )
            counts[latest_signal.signal if latest_signal else "unclassified"] += 1
            if last_synced_at is None or deal.last_synced_at > last_synced_at:
                last_synced_at = deal.last_synced_at

        return {
            "total_deals": len(deals),
            "at_risk": counts["at_risk"],
            "stalling": counts["stalling"],
            "on_track": counts["on_track"],
            "unclassified": counts["unclassified"],
            "last_synced_at": last_synced_at.isoformat() if last_synced_at else None,
        }
    finally:
        session.close()
