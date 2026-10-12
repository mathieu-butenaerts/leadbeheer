#!/usr/bin/env python3
"""Rebuild a tag that was deleted for good, from a daily backup made BEFORE
it was deleted.

Each backups/leadbeheer-export-<date>.xlsx has a Tags column per company.
This picks the companies that carried a given tag in that backup and writes
a minimal Company + Tags file for "Importeren" -- minimal on purpose: an
import refreshes enrichment fields (LinkedIn / Crystal Ball data) of
companies that already exist, so re-importing a whole old backup could put
older values over newer ones. A Company + Tags sheet touches nothing but
the tag (no contacts, no notes, no stage).

Usage:
    pip install pandas openpyxl

    # 1. See which tags a backup contains (and how many companies each):
    python restore_tag_from_backup.py ../backups/leadbeheer-export-2026-10-11.xlsx

    # 2. Write the import file for one tag -- by its list number, or by a
    #    unique part of its name:
    python restore_tag_from_backup.py ../backups/leadbeheer-export-2026-10-11.xlsx 2
    python restore_tag_from_backup.py ../backups/leadbeheer-export-2026-10-11.xlsx "Prio"

Then in the app: Importeren > pick the produced file. Clear the batch-tag
field on the confirmation screen (or it tags every company with that too),
and the tag is created again and put back on those companies.

Pick the newest backup from before the deletion -- the day of the deletion
itself is already too late if the nightly backup (03:00 UTC) ran after it.
Companies that were merged or removed since are not in the app anymore and
are simply created again by the import, so check the preview screen's
"Nieuwe bedrijven" count: it should be 0.

Limit: the Tags column separates tags with commas/semicolons, so a tag whose
own name contains a comma can't be told apart here.
"""

import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

from _common import clear_output, write_output


def split_tags(cell):
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return []
    return [t.strip() for t in re.split(r"[;,]", str(cell)) if t.strip()]


def main():
    if len(sys.argv) < 2:
        raise SystemExit(f"Usage: python {Path(__file__).name} backup.xlsx [tag name] [output.xlsx]")
    backup = Path(sys.argv[1])
    df = pd.read_excel(backup, dtype=str)
    if "Company" not in df.columns or "Tags" not in df.columns:
        raise SystemExit('This file has no "Company" and "Tags" columns -- is it a leadbeheer-export backup?')

    # One backup row per contact, so a company appears several times --
    # collapse to one tag set per company first.
    tags_by_company = {}
    for _, row in df.iterrows():
        company = str(row["Company"]).strip()
        if not company or company.lower() == "nan":
            continue
        tags_by_company.setdefault(company, set()).update(split_tags(row["Tags"]))

    counts = Counter(t for tags in tags_by_company.values() for t in tags)
    ordered = sorted(counts.items(), key=lambda kv: kv[0].lower())

    if len(sys.argv) < 3:
        print(f"{backup.name}: {len(tags_by_company)} companies, {len(counts)} tags\n")
        for i, (name, n) in enumerate(ordered, 1):
            print(f"  {i:3d})  {n:5d} companies  {name}")
        print('\nPick one by its number or by a unique part of its name, e.g. "Prio" or 2.')
        return

    # By list number, exact name, or a unique piece of the name -- so tags
    # with quotes or odd characters needn't be typed out (shells mangle them).
    query = sys.argv[2].strip()
    if query.isdigit() and 1 <= int(query) <= len(ordered):
        wanted = ordered[int(query) - 1][0]
    else:
        exact = [n for n, _ in ordered if n.lower() == query.lower()]
        partial = [n for n, _ in ordered if query.lower() in n.lower()]
        matches = exact or partial
        if not matches:
            raise SystemExit(f'No tag matches "{query}" in {backup.name}. Run without a tag name to list them.')
        if len(matches) > 1:
            raise SystemExit('"%s" matches several tags, be more specific:\n  ' % query + "\n  ".join(matches))
        wanted = matches[0]
    companies = sorted(c for c, tags in tags_by_company.items() if wanted in tags)

    out_path = Path(sys.argv[3]) if len(sys.argv) > 3 else backup.with_name(f"restore_tag_{re.sub(r'[^A-Za-z0-9]+', '_', wanted).strip('_')}.xlsx")
    rows = [{"Company": c, "Tags": wanted} for c in companies]
    clear_output(out_path)
    write_output(rows, out_path)
    print(f'{len(companies)} compan{"y" if len(companies) == 1 else "ies"} had "{wanted}" in {backup.name}.')


if __name__ == "__main__":
    main()
