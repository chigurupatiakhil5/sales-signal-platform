"""
Seeds 50 realistic fake deals into HubSpot (varied stages, contact activity)
and, because HubSpot's own createdate/lastmodifieddate fields aren't
writable, seeds a matching plausible stage-history directly into Postgres so
"days in stage" and the velocity average have real numbers to work with the
moment the dashboard opens - no need to wait days for real syncs to build
that history up.

Run:  python seed.py
Then: start the backend and hit POST /sync once to generate AI signals.
"""

import os
import random
import sys
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

from faker import Faker

from database import Deal, DealSnapshot, get_session, init_db, utcnow
from hubspot_client import HubSpotClient

fake = Faker()

# This portal's actual "Deals pipeline" stage IDs (see backend/main.py for
# how these were fetched via GET /crm/v3/pipelines/deals).
STAGE_SEQUENCE = [
    "4226950866",  # Visitor Engaged
    "4226950867",  # Lead Captured
    "4226950868",  # Lead Nurtured
    "4226950869",  # Demo Delivered
    "4226950870",  # In Negotiation
    "4226950871",  # Deal Won
]
# Weighted so most seeded deals sit mid-pipeline, where the dashboard is most useful to look at
STAGE_WEIGHTS = [0.22, 0.24, 0.20, 0.16, 0.12, 0.06]

DEAL_TYPES = ["Enterprise Plan", "Growth Plan", "Starter Plan", "Annual Renewal", "Platform Upgrade", "Team Expansion"]

NOTE_BODIES = [
    "Call with champion - discussed timeline.",
    "Sent updated pricing proposal.",
    "Demo follow-up email sent.",
    "Check-in call, no major updates.",
    "Met with decision maker.",
    "Answered procurement questions over email.",
]

NUM_DEALS = 50


def random_stage() -> str:
    return random.choices(STAGE_SEQUENCE, weights=STAGE_WEIGHTS, k=1)[0]


def build_stage_history(current_stage: str) -> list[tuple[str, int, int | None]]:
    """
    Returns [(stage, entered_days_ago, left_days_ago_or_None), ...] - a
    plausible path through the pipeline ending at current_stage, with
    varied, realistic dwell times per stage. left_days_ago is None for the
    final (current) stage, since the deal is still there.
    """
    end_index = STAGE_SEQUENCE.index(current_stage)
    path = STAGE_SEQUENCE[: end_index + 1]

    # Built backward from "now" so the *current* stage always gets a short,
    # recent dwell (1-6 days) regardless of how many stages came before it -
    # building forward from a random pipeline-start point let a deal whose
    # current stage was also the first stage inherit that whole random
    # offset directly as its "days in stage", instead of a realistic value.
    history: list[tuple[str, int, int | None]] = []
    days_ago_at_stage_end = 0  # "now", relative to the current/last stage

    for i in range(len(path) - 1, -1, -1):
        stage = path[i]
        is_current = i == len(path) - 1
        dwell = random.randint(1, 6) if is_current else random.randint(2, 12)
        entered_days_ago = days_ago_at_stage_end + dwell
        left_days_ago = None if is_current else days_ago_at_stage_end
        history.append((stage, entered_days_ago, left_days_ago))
        days_ago_at_stage_end = entered_days_ago

    history.reverse()  # chronological order: earliest stage first
    return history


def activity_offsets() -> list[int]:
    """Days-ago offsets for simulated Notes, varied by an engagement tier."""
    tier = random.choices(["high", "medium", "low", "none"], weights=[0.35, 0.30, 0.20, 0.15], k=1)[0]
    if tier == "high":
        return [random.randint(0, 3) for _ in range(random.randint(2, 4))]
    if tier == "medium":
        return [random.randint(5, 14) for _ in range(random.randint(1, 2))]
    if tier == "low":
        return [random.randint(20, 40)]
    return []


def seed_snapshots(session, deal_id: str, amount: float, last_contact, history: list[tuple[str, int, int | None]], now) -> None:
    """Lays down snapshot rows every ~3 days across each stage's run, so
    get_avg_days_in_stage() has multiple real samples per stage to average."""
    for stage_name, entered_days_ago, left_days_ago in history:
        span_end_days_ago = left_days_ago if left_days_ago is not None else 0
        step_days = max((entered_days_ago - span_end_days_ago) // 3, 1)

        day_cursor = entered_days_ago
        while day_cursor > span_end_days_ago:
            session.add(
                DealSnapshot(
                    deal_id=deal_id,
                    stage=stage_name,
                    amount=amount,
                    last_contact_date=last_contact,
                    snapshot_at=now - timedelta(days=day_cursor),
                )
            )
            day_cursor -= step_days

        session.add(
            DealSnapshot(
                deal_id=deal_id,
                stage=stage_name,
                amount=amount,
                last_contact_date=last_contact,
                snapshot_at=now - timedelta(days=span_end_days_ago),
            )
        )


def main() -> None:
    hubspot = HubSpotClient()
    init_db()
    session = get_session()
    now = utcnow()

    print(f"Seeding {NUM_DEALS} deals into HubSpot...\n")

    for i in range(1, NUM_DEALS + 1):
        company = fake.company().replace(",", "")
        deal_name = f"{company} - {random.choice(DEAL_TYPES)}"
        stage = random_stage()
        amount = round(random.uniform(5_000, 150_000), -2)

        deal_id = hubspot.create_deal(deal_name=deal_name, stage=stage, amount=amount)

        offsets = activity_offsets()
        for offset in offsets:
            hubspot.create_note(deal_id=deal_id, body=random.choice(NOTE_BODIES), timestamp=now - timedelta(days=offset))
        last_contact = now - timedelta(days=min(offsets)) if offsets else None

        history = build_stage_history(stage)
        stage_entered_at = now - timedelta(days=history[-1][1])
        created_date = now - timedelta(days=history[0][1])

        session.add(
            Deal(
                id=deal_id,
                deal_name=deal_name,
                stage=stage,
                pipeline="default",
                amount=amount,
                created_date=created_date,
                hs_last_modified_date=now,
                last_contact_date=last_contact,
                stage_entered_at=stage_entered_at,
                last_synced_at=now,
            )
        )
        session.flush()

        seed_snapshots(session, deal_id, amount, last_contact, history, now)

        contact_label = f"{min(offsets)}d ago" if offsets else "none"
        print(f"  [{i}/{NUM_DEALS}] {deal_name} -> {stage} (last contact: {contact_label})")

    session.commit()
    session.close()

    print("\nDone. 50 deals are live in HubSpot with seeded history in Postgres.")
    print("Start the backend, then POST /sync once to generate AI signals for every deal.")


if __name__ == "__main__":
    main()
