#!/usr/bin/env python3
"""Snapshot the whole Leadbeheer database (companies, contacts, tags) to an
.xlsx file shaped exactly like the app's own import/export template -- a
backup that's also re-importable through "Importeren" if it's ever needed,
not just a read-only export.

Run on a schedule by .github/workflows/daily-backup.yml (see that file for
the one-time secrets setup). Can also be run locally:

    pip install pandas openpyxl requests
    export SUPABASE_URL=https://xxxx.supabase.co
    export SUPABASE_SERVICE_ROLE_KEY=...   # Project Settings > API > service_role
    python export_database_snapshot.py [output.xlsx]

The service_role key is required, not the anon key used in auth.js --
anon-with-no-session only has Postgres's `anon` role, which this app's RLS
policies (`to authenticated`) don't grant read access to, and a backup
needs every row regardless of who's "logged in" (nobody is, here).
service_role bypasses RLS entirely. Keep it out of the app/browser and out
of this repo -- it only ever belongs in this script's environment and in
GitHub's encrypted Actions secrets.
"""

import os
import sys
from pathlib import Path

import requests

from _common import TEMPLATE_COLUMNS, clear_output, write_output

PAGE_SIZE = 1000

# Stored value -> the name shown in the app (keep in step with STAGES in
# index.html). Backups made before the rename say Nieuw / Gecontacteerd /
# Gekwalificeerd / Gewonnen for the first four; the app still reads those.
STAGE_LABELS = {
    "nieuw": "In progress",
    "gecontacteerd": "Meeting geboekt",
    "gekwalificeerd": "Deal",
    "verloren": "Verloren",
    "gewonnen": "Discontinued",
}


def fetch_all(base_url, headers, table, order=None):
    """PostgREST returns at most PAGE_SIZE rows per call -- keep paging with
    offset until a page comes back short, the same way Marktmonitor's own
    JS fetchAll() does for the tenders table."""
    rows = []
    offset = 0
    while True:
        params = {"select": "*", "limit": PAGE_SIZE, "offset": offset}
        if order:
            params["order"] = order
        res = requests.get(f"{base_url}/rest/v1/{table}", headers=headers, params=params, timeout=60)
        res.raise_for_status()
        page = res.json()
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def fetch_notes(base_url, headers):
    """The notes table only exists once supabase/schema.sql has been re-run
    after notes were added; until then PostgREST answers 404 -- that's "no
    notes yet", not a reason to fail the whole nightly backup."""
    try:
        return fetch_all(base_url, headers, "notes")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            print("No notes table yet (run supabase/schema.sql) -- backing up without notes.")
            return []
        raise


def format_note_time(iso):
    """'2026-11-06T13:40:12.3+00:00' -> '06-11-2026 14:40' in Dutch local time,
    the same way the app shows it."""
    from datetime import datetime, timezone
    when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    try:
        from zoneinfo import ZoneInfo
        when = when.astimezone(ZoneInfo("Europe/Amsterdam"))
    except Exception:
        when = when.astimezone(timezone.utc)
    return when.strftime("%d-%m-%Y %H:%M")


def notes_text(legacy, notes):
    """The sheet has one text cell per notes column, so dated notes go after
    any imported text, oldest first, as "[dd-mm-yyyy hh:mm Name] text" --
    the same shape the app's own export writes."""
    parts = [legacy] if legacy else []
    for n in sorted(notes, key=lambda n: n["created_at"]):
        parts.append(f"[{format_note_time(n['created_at'])} {n.get('author_name') or '?'}] {n['body']}")
    return "\n\n".join(parts)


def build_rows(companies, contacts, tags, company_tags, notes=()):
    notes_by_company, notes_by_contact = {}, {}
    for n in notes:
        if n.get("company_id"):
            notes_by_company.setdefault(n["company_id"], []).append(n)
        elif n.get("contact_id"):
            notes_by_contact.setdefault(n["contact_id"], []).append(n)

    tag_name_by_id = {t["id"]: t["name"] for t in tags}
    tag_names_by_company = {}
    for ct in company_tags:
        tag_names_by_company.setdefault(ct["company_id"], []).append(tag_name_by_id.get(ct["tag_id"]))

    contacts_by_company = {}
    for p in contacts:
        contacts_by_company.setdefault(p["company_id"], []).append(p)

    rows = []
    for company in companies:
        stage = company.get("stage") or ""
        base = {
            "Company": company.get("name") or "",
            "Company LinkedIn": company.get("linkedin") or "",
            "Fase": STAGE_LABELS.get(stage, stage),
            "Bedrijfsnotities": notes_text(company.get("notes") or "", notes_by_company.get(company["id"], [])),
            "Tags": ", ".join(sorted(filter(None, tag_names_by_company.get(company["id"], [])))),
            "Engagement Level": company.get("engagement_level") or "",
            "Organic Impressions": company.get("organic_impressions"),
            "Organic Engagements": company.get("organic_engagements"),
            "Paid Impressions": company.get("paid_impressions"),
            "Paid Clicks": company.get("paid_clicks"),
            "Paid Engagements": company.get("paid_engagements"),
            "Paid Video Views": company.get("paid_video_views"),
            "Paid Conversions": company.get("paid_conversions"),
            "Paid Leads": company.get("paid_leads"),
            "Paid Qualified Leads": company.get("paid_qualified_leads"),
            "Cost Per Qualified Lead": company.get("cost_per_qualified_lead"),
            "Domain": company.get("domain") or "",
            "Address": company.get("address") or "",
            "Company Size": company.get("company_size") or "",
            "Annual Revenue": company.get("annual_revenue") or "",
            "Industry": company.get("industry") or "",
            "Country": company.get("country") or "",
            "Solution": company.get("solution") or "",
            "Report Date": company.get("report_date") or "",
            "Previous SuperScore": company.get("previous_superscore"),
            "SuperScore": company.get("superscore"),
            "SuperScore % Change": company.get("superscore_change"),
            "Sub-solution": company.get("sub_solution") or "",
            "Installed Technology": company.get("installed_technology") or "",
            "Topics": company.get("topics") or "",
            "Vendors": company.get("vendors") or "",
        }

        company_contacts = contacts_by_company.get(company["id"], [])
        if not company_contacts:
            rows.append(dict(base))
            continue
        for p in company_contacts:
            row = dict(base)
            row.update({
                "First Name": p.get("first_name") or "",
                "Last Name": p.get("last_name") or "",
                "Job Title": p.get("job_title") or "",
                "Gender": p.get("gender") or "",
                "Email": p.get("email") or "",
                "Email 2": p.get("email2") or "",
                "Mobile Phone": p.get("mobile_phone") or "",
                "Work Phone": p.get("work_phone") or "",
                "Beller": p.get("beller") or "",
                "Vervolg": p.get("vervolg") or "",
                "Vervolgdatum": p.get("follow_up_date") or "",
                "Notities": notes_text(p.get("notities") or "", notes_by_contact.get(p["id"], [])),
                "Belaantekeningen": p.get("belaantekeningen") or "",
                "Mogelijk interessante hook": p.get("hook") or "",
            })
            rows.append(row)
    return rows


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        raise SystemExit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first (see this script's docstring).")

    if len(sys.argv) > 1:
        # Explicit path (e.g. the daily-backup workflow's fixed
        # backups/leadbeheer-export.xlsx, overwritten and committed each run
        # so `git log` on that one file is the backup history).
        out_path = Path(sys.argv[1])
    else:
        import datetime
        out_path = Path(__file__).resolve().parent.parent / "backups" / f"leadbeheer-export-{datetime.date.today()}.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    headers = {"apikey": service_key, "Authorization": f"Bearer {service_key}"}

    print("Fetching companies, contacts, tags, company_tags...")
    companies = fetch_all(supabase_url, headers, "companies", order="name.asc")
    contacts = fetch_all(supabase_url, headers, "contacts")
    tags = fetch_all(supabase_url, headers, "tags")
    company_tags = fetch_all(supabase_url, headers, "company_tags")
    notes = fetch_notes(supabase_url, headers)

    rows = build_rows(companies, contacts, tags, company_tags, notes)

    # Overwrite, not append -- this is today's full snapshot, not an
    # incremental migration batch like the migrate_*.py scripts produce.
    clear_output(out_path)
    write_output(rows, out_path)
    print(f"({len(companies)} companies, {len(contacts)} contacts, {len(tags)} tags)")


if __name__ == "__main__":
    main()
