#!/usr/bin/env python3
"""Migrate an outreach/sequencing-tool export (Notities, Naam, Id, Check op
eerdere campagne, First Name, Last Name, Gender, Email, Email 2, Mobile
Phone, Work Phone, Occupation, Title, Company, Company Size, Company
Locality, Company Type, Company Industry, Company Founded At, Company Start
Date, Region, Website, Active Sequences, Custom Field 1-150, ...) to the
Leadbeheer template.

Assumptions (check the output and adjust if any of these are wrong for
your data):
  - "First Name"/"Last Name" are used directly -- "Naam" (a combined
    display name the tool also exports) is ignored rather than re-split,
    since the two dedicated columns are already authoritative.
  - "Id" and "Active Sequences" are the outreach tool's own bookkeeping,
    not CRM data -- ignored.
  - "Title" and "Occupation" both map to the template's single Job Title
    field, combined as "Title (Occupation)" when both are present.
  - "Region" holds country names in this export, so it maps directly to
    the template's Country column (confirmed with the data source --
    unlike a sales region/territory, which wouldn't).
  - "Website" -> Domain, "Company Industry" -> Industry, "Company Size" ->
    Company Size -- the template already has matching columns for these.
  - "Check op eerdere campagne", "Company Locality", "Company Type" and
    "Company Founded At" have no matching template field, so each is
    folded into Notities, tagged with its own column name so it stays
    distinguishable from the source "Notities" column.
  - "Company Start Date" (when the company entered this sequence tool,
    not a real business fact) is ignored, like Active Sequences.
  - Custom Field 1 through 150 are ignored entirely -- unused in this
    export.

Usage:
    pip install pandas openpyxl
    python migrate_sequence_export.py input.xlsx [output.xlsx]
"""

import sys
from pathlib import Path

from _common import append_note, clean, read_source, write_output

REQUIRED_COLUMNS = [
    "Notities", "Check op eerdere campagne", "First Name", "Last Name",
    "Gender", "Email", "Email 2", "Mobile Phone", "Work Phone", "Occupation",
    "Title", "Company", "Company Size", "Company Locality", "Company Type",
    "Company Industry", "Company Founded At", "Region", "Website",
]


def job_title(r):
    title = clean(r["Title"])
    occupation = clean(r["Occupation"])
    if title and occupation:
        return f"{title} ({occupation})"
    return title or occupation


def migrate(df):
    rows = []
    for _, r in df.iterrows():
        notities = clean(r["Notities"])
        notities = append_note(notities, "Check op eerdere campagne", r["Check op eerdere campagne"])
        notities = append_note(notities, "Company Locality", r["Company Locality"])
        notities = append_note(notities, "Company Type", r["Company Type"])
        notities = append_note(notities, "Company Founded At", r["Company Founded At"])

        rows.append({
            "Company": clean(r["Company"]),
            "Company LinkedIn": "",
            "Fase": "",
            "Bedrijfsnotities": "",
            "Tags": "",
            "Domain": clean(r["Website"]),
            "Company Size": clean(r["Company Size"]),
            "Industry": clean(r["Company Industry"]),
            "Country": clean(r["Region"]),
            "First Name": clean(r["First Name"]),
            "Last Name": clean(r["Last Name"]),
            "Job Title": job_title(r),
            "Gender": clean(r["Gender"]),
            "Email": clean(r["Email"]),
            "Email 2": clean(r["Email 2"]),
            "Mobile Phone": clean(r["Mobile Phone"]),
            "Work Phone": clean(r["Work Phone"]),
            "Beller": "",
            "Vervolg": "",
            "Vervolgdatum": "",
            "Notities": notities,
            "Belaantekeningen": "",
            "Mogelijk interessante hook": "",
        })
    return rows


def main():
    if len(sys.argv) < 2:
        raise SystemExit(f"Usage: python {Path(__file__).name} input.xlsx [output.xlsx]")
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else in_path.with_name(in_path.stem + "_migrated.xlsx")

    df = read_source(in_path, REQUIRED_COLUMNS)
    rows = migrate(df)
    write_output(rows, out_path)


if __name__ == "__main__":
    main()
