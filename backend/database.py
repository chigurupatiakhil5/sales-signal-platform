"""
Postgres access layer (Neon). Three tables:

- deals: latest known state of each HubSpot deal
- deal_snapshots: one row per deal per sync, forever - this history is what
  lets us measure velocity (how long deals actually spend in each stage)
- deal_signals: one row per deal per sync holding Claude's classification

`stage_entered_at` on `deals` is the mechanism that makes "days in current
stage" meaningful: it only moves forward when a sync observes the deal's
stage actually changing, not on every sync.
"""

import os
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, Numeric, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Deal(Base):
    __tablename__ = "deals"

    id = Column(String, primary_key=True)  # HubSpot deal ID
    deal_name = Column(String, nullable=False)
    stage = Column(String, nullable=False)
    pipeline = Column(String, nullable=True)
    amount = Column(Numeric, nullable=True)
    created_date = Column(DateTime(timezone=True), nullable=True)
    hs_last_modified_date = Column(DateTime(timezone=True), nullable=True)
    last_contact_date = Column(DateTime(timezone=True), nullable=True)
    stage_entered_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    last_synced_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)


class DealSnapshot(Base):
    __tablename__ = "deal_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deal_id = Column(String, ForeignKey("deals.id"), nullable=False, index=True)
    stage = Column(String, nullable=False)
    amount = Column(Numeric, nullable=True)
    last_contact_date = Column(DateTime(timezone=True), nullable=True)
    snapshot_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


class DealSignal(Base):
    __tablename__ = "deal_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deal_id = Column(String, ForeignKey("deals.id"), nullable=False, index=True)
    signal = Column(String, nullable=False)  # at_risk | stalling | on_track
    reason = Column(String, nullable=False)
    days_in_stage = Column(Integer, nullable=False)
    days_since_contact = Column(Integer, nullable=True)
    avg_days_in_stage = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return SessionLocal()


def get_avg_days_in_stage(
    session: Session,
    stage: str,
    exclude_deal_id: str | None = None,
    fallback: float = 5.0,
) -> float:
    """
    Walks every deal's snapshot history in time order and measures how long
    deals actually stayed in `stage` before moving to a different stage.
    Only *completed* stays are counted, so a deal that just arrived in the
    stage doesn't drag the average toward zero. Falls back to a flat default
    when there isn't enough history yet (e.g. right after the first sync).
    """
    query = session.query(DealSnapshot).order_by(DealSnapshot.deal_id, DealSnapshot.snapshot_at)
    if exclude_deal_id:
        query = query.filter(DealSnapshot.deal_id != exclude_deal_id)
    snapshots = query.all()

    durations: list[float] = []
    current_deal_id: str | None = None
    run_stage: str | None = None
    run_start: datetime | None = None

    for snap in snapshots:
        if snap.deal_id != current_deal_id:
            # New deal's history starts. The previous deal's final run was
            # never observed ending, so it's intentionally left uncounted.
            current_deal_id = snap.deal_id
            run_stage = snap.stage
            run_start = snap.snapshot_at
            continue
        if snap.stage != run_stage:
            if run_stage == stage and run_start is not None:
                durations.append((snap.snapshot_at - run_start).total_seconds() / 86400)
            run_stage = snap.stage
            run_start = snap.snapshot_at

    if not durations:
        return fallback
    return sum(durations) / len(durations)
