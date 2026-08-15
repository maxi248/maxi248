#!/usr/bin/env python3
"""
fetch_pricecatcher.py - Automatischer Abruf der offiziell offenen
malaysischen Preisdaten (KPDN PriceCatcher ueber data.gov.my).

Das ist NICHT FAMA, sondern die Alternative, die dokumentiert und ohne
Vertrag/Key automatisiert abrufbar ist: taegliche Erhebung von
Einzelhandelspreisen in ~3.800 Premises, ~750 Artikel, alle 16
Bundesstaaten. FAMA liefert zusaetzlich Ladang-/Borong-Preise
(Erzeuger/Grosshandel), die es hier nicht gibt - siehe README.

Datenquelle (Parquet, kein API-Key):
    https://storage.data.gov.my/pricecatcher/pricecatcher_YYYY-MM.parquet
    https://storage.data.gov.my/pricecatcher/lookup_item.parquet
    https://storage.data.gov.my/pricecatcher/lookup_premise.parquet

Beispiele:
    python3 fetch_pricecatcher.py --months 2026-06 2026-07
    python3 fetch_pricecatcher.py --months 2026-07 --state Selangor --out selangor.csv
    python3 fetch_pricecatcher.py --months 2026-07 --item-contains bawang

Abhaengigkeiten:
    pip install pandas pyarrow
"""

from __future__ import annotations

import argparse
import sys

BASE = "https://storage.data.gov.my/pricecatcher"
MONTHLY_URL = BASE + "/pricecatcher_{month}.parquet"
LOOKUP_ITEM_URL = BASE + "/lookup_item.parquet"
LOOKUP_PREMISE_URL = BASE + "/lookup_premise.parquet"


def load(url: str):
    import pandas as pd

    print(f"  laden: {url}")
    return pd.read_parquet(url)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--months", nargs="+", required=True, metavar="YYYY-MM",
                        help="Monate, z.B. --months 2026-06 2026-07")
    parser.add_argument("--state", help="Filter auf Bundesstaat (Teilstring, case-insensitive)")
    parser.add_argument("--item-contains", help="Filter auf Artikelnamen (Teilstring, case-insensitive)")
    parser.add_argument("--out", default="pricecatcher.csv", help="Ziel-CSV")
    parser.add_argument("--no-lookups", action="store_true",
                        help="Nur Rohdaten ohne Artikel-/Premise-Namen joinen")
    args = parser.parse_args()

    try:
        import pandas as pd  # noqa: F401
    except ImportError:
        print("Fehlt: pandas. Installieren mit:  pip install pandas pyarrow", file=sys.stderr)
        return 2

    import pandas as pd

    frames = []
    for month in args.months:
        try:
            frames.append(load(MONTHLY_URL.format(month=month)))
        except Exception as exc:
            print(f"  !! {month} nicht ladbar: {type(exc).__name__}: {exc}", file=sys.stderr)
    if not frames:
        print("Keine Monatsdatei ladbar - Netzwerk oder Monatsangabe pruefen.", file=sys.stderr)
        return 1

    df = pd.concat(frames, ignore_index=True)
    print(f"  Rohdaten: {len(df):,} Zeilen, Spalten: {list(df.columns)}")

    if not args.no_lookups:
        for url, key in ((LOOKUP_ITEM_URL, "item_code"), (LOOKUP_PREMISE_URL, "premise_code")):
            try:
                lookup = load(url)
                if key in df.columns and key in lookup.columns:
                    df = df.merge(lookup, on=key, how="left", suffixes=("", "_lk"))
                else:
                    print(f"  !! Join-Key '{key}' fehlt - Lookup uebersprungen", file=sys.stderr)
            except Exception as exc:
                print(f"  !! Lookup {url} nicht ladbar ({type(exc).__name__}) - Namen fehlen", file=sys.stderr)

    if args.state:
        col = next((c for c in ("state", "negeri") if c in df.columns), None)
        if col:
            df = df[df[col].str.contains(args.state, case=False, na=False)]
        else:
            print("  !! Keine Spalte 'state' vorhanden - Filter ignoriert", file=sys.stderr)

    if args.item_contains:
        col = next((c for c in ("item", "item_name", "nama_item") if c in df.columns), None)
        if col:
            df = df[df[col].str.contains(args.item_contains, case=False, na=False)]
        else:
            print("  !! Keine Artikelnamen-Spalte vorhanden - Filter ignoriert", file=sys.stderr)

    df.to_csv(args.out, index=False)
    print(f"\nGeschrieben: {args.out}  ({len(df):,} Zeilen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
