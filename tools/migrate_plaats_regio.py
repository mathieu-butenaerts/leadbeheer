#!/usr/bin/env python3
"""Migrate an Excel export with these columns to the Leadbeheer template:

    Notities  Telefoon 1  Naam  Functie  Bedrijf  Plaats / regio  E-mail  Telefoon 2  LinkedIn

Assumptions (check the output and adjust if any of these are wrong for
your data):
  - "Telefoon 1" -> Mobile Phone, "Telefoon 2" -> Work Phone.
  - "Naam" is one "Voornaam Achternaam" field; it's split on the first
    space (see _common.split_name for the exact rule and its limits).
  - "LinkedIn" is the CONTACT's personal profile, not a company page --
    there's no personal-LinkedIn column in the template, so it's folded
    into Notities as "LinkedIn: <url>" rather than mismapped onto
    Company LinkedIn (which would overwrite across contacts at the same
    company).
  - "Plaats / regio" describes the company, not the person, so it goes
    into Bedrijfsnotities as "Regio: <value>".

Usage:
    pip install pandas openpyxl
    python migrate_plaats_regio.py input.xlsx [output.xlsx]
"""

import sys
from pathlib import Path

from _common import append_note, clean, read_source, split_name, write_output

REQUIRED_COLUMNS = [
    "Notities", "Telefoon 1", "Naam", "Functie", "Bedrijf",
    "Plaats / regio", "E-mail", "Telefoon 2", "LinkedIn",
]


def migrate(df):
    rows = []
    for _, r in df.iterrows():
        first_name, last_name = split_name(r["Naam"])
        notities = clean(r["Notities"])
        notities = append_note(notities, "LinkedIn", r["LinkedIn"])
        bedrijfsnotities = append_note("", "Regio", r["Plaats / regio"])

        rows.append({
            "Company": clean(r["Bedrijf"]),
            "Company LinkedIn": "",
            "Fase": "",
            "Bedrijfsnotities": bedrijfsnotities,
            "First Name": first_name,
            "Last Name": last_name,
            "Job Title": clean(r["Functie"]),
            "Gender": "",
            "Email": clean(r["E-mail"]),
            "Email 2": "",
            "Mobile Phone": clean(r["Telefoon 1"]),
            "Work Phone": clean(r["Telefoon 2"]),
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
