#!/usr/bin/env python3
"""Migrate a LinkedIn Company Page engagement export (CSV) to the Leadbeheer
template, so it can be imported to refresh companies' engagement metrics.

Source columns (LinkedIn's own export headers):
    Company name, Company page URL, Engagement level, Organic impressions,
    Organic engagements, Paid impressions, Paid clicks, Paid engagements,
    Paid video views, Paid conversions, Paid leads, Paid qualified leads,
    Cost per qualified lead

Unlike the other migrate_*.py scripts, this source has no contact people in
it at all -- every row is a company's marketing metrics, not a person. First
Name / Last Name are left blank on every output row, which the app's
importer already treats as "company information only": it updates the
company's fields without creating a contact.

Notes:
  - "Company page URL" is the company's own LinkedIn page, so it maps
    straight to Company LinkedIn.
  - Metric columns are left BLANK when the source cell is empty, not 0 --
    the app treats a blank as "never measured", distinct from "measured,
    was zero". "Cost per qualified lead" is parsed as money (strips a
    currency symbol or thousands separator, e.g. "$1,234.50").
  - Uploading this file for a company ALREADY in Leadbeheer (matched by
    name) only ever refreshes its engagement numbers -- it never touches
    that company's Fase, notes, or LinkedIn URL. Re-running this each time
    you pull a fresh LinkedIn export is exactly the intended use.

Usage:
    pip install pandas openpyxl
    python migrate_linkedin_engagement.py input.csv [output.xlsx]
"""

import sys
from pathlib import Path

from _common import clean, read_csv_source, to_money, to_number, write_output

REQUIRED_COLUMNS = [
    "Company name", "Company page URL", "Engagement level",
    "Organic impressions", "Organic engagements", "Paid impressions",
    "Paid clicks", "Paid engagements", "Paid video views",
    "Paid conversions", "Paid leads", "Paid qualified leads",
    "Cost per qualified lead",
]

# (source column, output template column, parser)
NUMBER_FIELDS = [
    ("Organic impressions", "Organic Impressions", to_number),
    ("Organic engagements", "Organic Engagements", to_number),
    ("Paid impressions", "Paid Impressions", to_number),
    ("Paid clicks", "Paid Clicks", to_number),
    ("Paid engagements", "Paid Engagements", to_number),
    ("Paid video views", "Paid Video Views", to_number),
    ("Paid conversions", "Paid Conversions", to_number),
    ("Paid leads", "Paid Leads", to_number),
    ("Paid qualified leads", "Paid Qualified Leads", to_number),
    ("Cost per qualified lead", "Cost Per Qualified Lead", to_money),
]


def migrate(df):
    rows = []
    for _, r in df.iterrows():
        row = {
            "Company": clean(r["Company name"]),
            "Company LinkedIn": clean(r["Company page URL"]),
            "Fase": "",
            "Bedrijfsnotities": "",
            "Engagement Level": clean(r["Engagement level"]),
            "First Name": "", "Last Name": "", "Job Title": "", "Gender": "",
            "Email": "", "Email 2": "", "Mobile Phone": "", "Work Phone": "",
            "Beller": "", "Vervolg": "", "Vervolgdatum": "",
            "Notities": "", "Belaantekeningen": "", "Mogelijk interessante hook": "",
        }
        for src_col, out_col, parser in NUMBER_FIELDS:
            value = parser(r[src_col])
            row[out_col] = "" if value is None else value
        rows.append(row)
    return rows


def main():
    if len(sys.argv) < 2:
        raise SystemExit(f"Usage: python {Path(__file__).name} input.csv [output.xlsx]")
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else in_path.with_name(in_path.stem + "_migrated.xlsx")

    if not in_path.exists():
        raise SystemExit(f"File not found: {in_path}")

    df = read_csv_source(in_path, REQUIRED_COLUMNS)
    if df.empty:
        raise SystemExit("The file contains no rows.")

    rows = migrate(df)
    write_output(rows, out_path)


if __name__ == "__main__":
    main()
