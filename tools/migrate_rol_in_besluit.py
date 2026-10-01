#!/usr/bin/env python3
"""Migrate an Excel export with these columns to the Leadbeheer template:

    Notities  Naam  Functie  Bedrijf  Land  Telefoonnummer  Mobiel  E-mail
    LinkedIn URL  Rol in besluit / opmerking

Assumptions (check the output and adjust if any of these are wrong for
your data):
  - "Naam" is one "Voornaam Achternaam" field; it's split on the first
    space (see _common.split_name for the exact rule and its limits).
  - "Telefoonnummer" -> Work Phone, "Mobiel" -> Mobile Phone (this source
    has both, unlike some of the other migrate_*.py scripts that only had
    one phone column).
  - "Land" -> Country directly -- the template has a real Country column
    (added for Crystal Ball imports), so unlike the older migrate_land.py
    script this doesn't need to be folded into Bedrijfsnotities.
  - "LinkedIn URL" is the CONTACT's personal profile, not a company page --
    there's no personal-LinkedIn column in the template, so it's folded
    into Notities as "LinkedIn: <url>" rather than mismapped onto Company
    LinkedIn (which would overwrite across contacts at the same company).
  - "Rol in besluit / opmerking" has no matching template field either, so
    it's folded into Notities the same way, tagged with its own column
    name so it stays distinguishable from the source "Notities" column.

Usage:
    pip install pandas openpyxl
    python migrate_rol_in_besluit.py input.xlsx [output.xlsx]
"""

import sys
from pathlib import Path

from _common import append_note, clean, read_source, split_name, write_output

REQUIRED_COLUMNS = [
    "Notities", "Naam", "Functie", "Bedrijf", "Land", "Telefoonnummer",
    "Mobiel", "E-mail", "LinkedIn URL", "Rol in besluit / opmerking",
]


def migrate(df):
    rows = []
    for _, r in df.iterrows():
        first_name, last_name = split_name(r["Naam"])
        notities = clean(r["Notities"])
        notities = append_note(notities, "Rol in besluit / opmerking", r["Rol in besluit / opmerking"])
        notities = append_note(notities, "LinkedIn", r["LinkedIn URL"])

        rows.append({
            "Company": clean(r["Bedrijf"]),
            "Company LinkedIn": "",
            "Fase": "",
            "Bedrijfsnotities": "",
            "Tags": "",
            "Country": clean(r["Land"]),
            "First Name": first_name,
            "Last Name": last_name,
            "Job Title": clean(r["Functie"]),
            "Gender": "",
            "Email": clean(r["E-mail"]),
            "Email 2": "",
            "Mobile Phone": clean(r["Mobiel"]),
            "Work Phone": clean(r["Telefoonnummer"]),
            "Beller": "",
            "Vervolg": "",
            "Vervolgdatum": "",
            "Notities": notities,
            "Belaantekeningen": "",
            "Mogelijk interessante hook": "",
        })
    return rows


def main():
    print("hello")
    if len(sys.argv) < 2:
        raise SystemExit(f"Usage: python {Path(__file__).name} input.xlsx [output.xlsx]")
    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else in_path.with_name(in_path.stem + "_migrated.xlsx")

    df = read_source(in_path, REQUIRED_COLUMNS)
    rows = migrate(df)
    print(len(rows))
    write_output(rows, out_path)


if __name__ == "__main__":
    main()
