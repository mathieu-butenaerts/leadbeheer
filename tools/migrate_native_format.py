#!/usr/bin/env python3
"""Migrate an Excel export with these columns to the Leadbeheer template:

    Notities  Beller  Vervolg  Belaantekeningen  Mogelijk interessante hook  Id
    First Name  Last Name  Gender  Email  Email 2  Mobile Phone  Work Phone
    Company  Company LinkedIn  Job Function

This is almost the template shape already -- it's a near 1:1 column
rename (Job Function -> Job Title), plus "Id" is dropped (the app mints
its own ids) and Fase / Bedrijfsnotities / Vervolgdatum are left blank
since this source has no equivalent columns.

Usage:
    pip install pandas openpyxl
    python migrate_native_format.py input.xlsx [output.xlsx]
"""

import sys
from pathlib import Path

from _common import clean, read_source, write_output

REQUIRED_COLUMNS = [
    "Notities", "Beller", "Vervolg", "Belaantekeningen", "Mogelijk interessante hook",
    "First Name", "Last Name", "Gender", "Email", "Email 2", "Mobile Phone",
    "Work Phone", "Company", "Company LinkedIn", "Job Function",
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
            "Job Title": clean(r["Job Function"]),
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

