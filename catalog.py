"""Shared data view for localhost and the published static dashboard."""
import json
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

REPORTS = Path(__file__).resolve().parent / "reports"


def catalog(reports=REPORTS, now=None):
    from archive_store import build_catalog
    base = Path(reports).resolve().parent
    data = build_catalog(base, now=now)
    audit_file = base / "data/availability.json"
    plans_file = base / "data/application_plans.json"
    audit = json.loads(audit_file.read_text()) if audit_file.exists() else {}
    plans = json.loads(plans_file.read_text()) if plans_file.exists() else {}
    records = audit.get("records", {})
    for card in data["projects"]:
        uid = card["id"]
        card["publishedAt"] = None
        value = (card.get("published") or "").replace(",", "").strip()
        if value:
            try:
                first = datetime.fromisoformat(card["firstSeen"].replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Kyiv"))
                day, clock = value.split()
                explicit = len(day.split(".")) == 3
                pub = datetime.strptime((day if explicit else day + "." + str(first.year)) + " " + clock, "%d.%m.%Y %H:%M").replace(tzinfo=first.tzinfo)
                if not explicit and pub > first + timedelta(days=1):
                    pub = pub.replace(year=pub.year - 1)
                card["publishedAt"] = pub.isoformat()
            except (KeyError, ValueError, TypeError):
                pass
        card["availability"] = records.get(uid)
        card["applicationPlan"] = plans.get("projects", {}).get(uid)
        card["reviewNote"] = plans.get("reviews", {}).get(uid)
    data["reviewUntil"] = plans.get("until")
    data["reviewBudget"] = plans.get("budget")
    data["reviewReport"] = plans.get("report")
    data["reviewStarted"] = audit.get("started")
    return data

