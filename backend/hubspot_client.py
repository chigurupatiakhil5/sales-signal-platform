"""
Thin wrapper around HubSpot's CRM v3/v4 REST API.

Auth: HUBSPOT_API_KEY must be a Private App access token (Settings ->
Integrations -> Private Apps in HubSpot), sent as a Bearer token. The legacy
hapikey query-param auth is deprecated and not supported here.

Required Private App scopes:
  crm.objects.deals.read, crm.objects.deals.write,
  crm.objects.notes.read, crm.objects.notes.write
"""

import os
from datetime import datetime, timezone

import requests

HUBSPOT_BASE_URL = "https://api.hubapi.com"
DEALS_ENDPOINT = f"{HUBSPOT_BASE_URL}/crm/v3/objects/deals"
NOTES_ENDPOINT = f"{HUBSPOT_BASE_URL}/crm/v3/objects/notes"

DEAL_PROPERTIES = ["dealname", "dealstage", "amount", "pipeline", "createdate", "hs_lastmodifieddate"]


def _parse_hs_datetime(value) -> datetime | None:
    """HubSpot returns either an epoch-millis string or an ISO 8601 string
    depending on the endpoint - handle both."""
    if not value:
        return None
    try:
        text = str(value)
        if text.isdigit():
            return datetime.fromtimestamp(int(text) / 1000, tz=timezone.utc)
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class HubSpotClient:
    def __init__(self, access_token: str | None = None):
        self.access_token = access_token or os.environ["HUBSPOT_API_KEY"]
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }
        )

    def get_deals(self) -> list[dict]:
        """Fetches every deal in the account, following pagination."""
        deals: list[dict] = []
        url: str | None = DEALS_ENDPOINT
        params: dict | None = {"limit": 100, "properties": ",".join(DEAL_PROPERTIES)}

        while url:
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", []):
                deals.append(self._normalize_deal(item))

            next_page = data.get("paging", {}).get("next")
            url = next_page.get("link") if next_page else None
            params = None  # the "next" link already carries its own query string

        return deals

    def _normalize_deal(self, item: dict) -> dict:
        props = item.get("properties", {})
        amount_raw = props.get("amount")
        return {
            "id": item["id"],
            "deal_name": props.get("dealname") or "Unnamed Deal",
            "stage": props.get("dealstage"),
            "pipeline": props.get("pipeline"),
            "amount": float(amount_raw) if amount_raw not in (None, "") else None,
            "created_date": _parse_hs_datetime(props.get("createdate")),
            "hs_last_modified_date": _parse_hs_datetime(props.get("hs_lastmodifieddate")),
        }

    def get_last_contact_date(self, deal_id: str) -> datetime | None:
        """
        Looks up every Note associated with a deal and returns the most
        recent one's timestamp, used as a proxy for "last contact activity".
        """
        url = f"{HUBSPOT_BASE_URL}/crm/v4/objects/deals/{deal_id}/associations/notes"
        resp = self.session.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()

        note_ids = [row["toObjectId"] for row in resp.json().get("results", [])]
        if not note_ids:
            return None

        batch_resp = self.session.post(
            f"{NOTES_ENDPOINT}/batch/read",
            json={"properties": ["hs_timestamp"], "inputs": [{"id": nid} for nid in note_ids]},
        )
        batch_resp.raise_for_status()

        timestamps = [
            ts
            for row in batch_resp.json().get("results", [])
            if (ts := _parse_hs_datetime(row.get("properties", {}).get("hs_timestamp")))
        ]
        return max(timestamps) if timestamps else None

    def create_deal(self, deal_name: str, stage: str, amount: float, pipeline: str = "default") -> str:
        resp = self.session.post(
            DEALS_ENDPOINT,
            json={
                "properties": {
                    "dealname": deal_name,
                    "dealstage": stage,
                    "amount": str(amount),
                    "pipeline": pipeline,
                }
            },
        )
        resp.raise_for_status()
        return resp.json()["id"]

    def create_note(self, deal_id: str, body: str, timestamp: datetime) -> str:
        """Creates a Note and associates it with the deal, using `timestamp`
        as the note's logged time - this is how seed.py simulates varied,
        backdated contact activity."""
        note_resp = self.session.post(
            NOTES_ENDPOINT,
            json={
                "properties": {
                    "hs_note_body": body,
                    "hs_timestamp": int(timestamp.timestamp() * 1000),
                }
            },
        )
        note_resp.raise_for_status()
        note_id = note_resp.json()["id"]

        # The "default association" shortcut only exists on v4, not v3.
        assoc_resp = self.session.put(
            f"{HUBSPOT_BASE_URL}/crm/v4/objects/notes/{note_id}/associations/default/deals/{deal_id}"
        )
        assoc_resp.raise_for_status()

        return note_id
