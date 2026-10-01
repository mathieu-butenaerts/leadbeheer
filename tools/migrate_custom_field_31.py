#!/usr/bin/env python3
"""Migrate an Excel export with these columns to the Leadbeheer template:

    Notities  Beller  Vervolg  Belaantekeningen  Mogelijk interessante hook  Id
    First Name  Last Name  Gender  Email  Email 2  Mobile Phone  Work Phone
    Company  Company LinkedIn  Custom Field 31

Same shape as migrate_native_format.py's source format, except that
source's "Job Function" column is named "Custom Field 31" in this export
-- confirmed it holds the same job-title data, just under the outreach
tool's generic custom-field slot instead of a named column this time.
"Id" is dropped (the app mints its own ids); Fase / Bedrijfsnotities /
Vervolgdatum are left blank since this source has no equivalent columns.

Usage:
    pip install pandas openpyxl
    python migrate_custom_field_31.py input.xlsx output.xlsx
"""

from pathlib import Path

from _common import clean, read_source, write_output

REQUIRED_COLUMNS = [
    "Notities", "Beller", "Vervolg", "Belaantekeningen", "Mogelijk interessante hook",
    "First Name", "Last Name", "Gender", "Email", "Email 2", "Mobile Phone",
    "Work Phone", "Company", "Company LinkedIn", "Custom Field 31",
]


def migrate(df):
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "Company": clean(r["Company"]),
            "Company LinkedIn": clean(r["Company LinkedIn"]),
            "Fase": "",
            "Bedrijfsnotities": "",
            "First Name": clean(r["First Name"]),
            "Last Name": clean(r["Last Name"]),
            "Job Title": clean(r["Custom Field 31"]),
            "Gender": clean(r["Gender"]),
            "Email": clean(r["Email"]),
            "Email 2": clean(r["Email 2"]),
            "Mobile Phone": clean(r["Mobile Phone"]),
            "Work Phone": clean(r["Work Phone"]),
            "Beller": clean(r["Beller"]),
            "Vervolg": clean(r["Vervolg"]),
            "Vervolgdatum": "",
            "Notities": clean(r["Notities"]),
            "Belaantekeningen": clean(r["Belaantekeningen"]),
            "Mogelijk interessante hook": clean(r["Mogelijk interessante hook"]),
        })
    return rows


def main(in_path_str, out_path_str):
    in_path = Path(in_path_str)
    out_path = Path(out_path_str)

    df = read_source(in_path, REQUIRED_COLUMNS)
    rows = migrate(df)
    write_output(rows, out_path)
