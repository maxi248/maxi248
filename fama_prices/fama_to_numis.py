#!/usr/bin/env python3
"""
fama_to_numis.py - Taeglicher Import der FAMA-AMI-Preise in die NuMIS-Datenbank.

Ablauf pro Lauf:
  1. Bei NuMIS nachfragen, welche Tage im Zeitfenster noch fehlen
     (RPC numis_missing_days). Dadurch werden ausgefallene Laeufe automatisch
     nachgeholt - es genuegt, das Skript einfach wieder zu starten.
  2. Fuer jeden fehlenden Tag die Tabelle 'harga' von ami.fama.gov.my holen.
  3. Die Zeilen stapelweise an numis_ingest_fama_batch schicken. Dort werden
     fehlende Kulturen und Maerkte angelegt, die Rohzeile in
     raw_source_records gesichert und die normalisierte Beobachtung in
     price_observations geschrieben - alles wiederholbar, ohne Duplikate.
  4. Den Tag mit numis_ingest_fama_finish abschliessen. Erst dann gilt er als
     erledigt. Bricht ein Tag mittendrin ab, wird er beim naechsten Lauf
     komplett wiederholt.

Voraussetzungen:
  - fama_ami_client.py liegt im selben Ordner (liefert den FAMA-Abruf)
  - Umgebungsvariable mit dem Supabase-Service-Role-Key:
        $env:NUMIS_SERVICE_KEY = "..."   (PowerShell)
        set NUMIS_SERVICE_KEY=...        (cmd.exe)
        export NUMIS_SERVICE_KEY=...     (Mac/Linux)
        setx NUMIS_SERVICE_KEY "..."     (dauerhaft, fuer die Aufgabenplanung)
    Achtung: In PowerShell ist 'set' ein Alias fuer Set-Variable und legt
    KEINE Umgebungsvariable an - der Befehl wirkt dann einfach nicht.
    Der Key umgeht RLS und gehoert deshalb NICHT in eine Datei im Repo.

Beispiele:
    python3 fama_to_numis.py                       # letzte 7 Tage pruefen/nachholen
    python3 fama_to_numis.py --days 30             # groesseres Fenster
    python3 fama_to_numis.py --from 2026-07-01 --to 2026-07-31
    python3 fama_to_numis.py --days 7 --dry-run    # nur zeigen, nichts schreiben

Nur Standardbibliothek.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

NEEDS_CLIENT = 6
CLIENT_URL = ("https://raw.githubusercontent.com/maxi248/maxi248/refs/heads/"
              "claude/fama-malaysia-price-data-tu8qfj/fama_prices/fama_ami_client.py")

try:
    import fama_ami_client
    from fama_ami_client import fetch_table, make_opener, IncompleteResult
except ImportError:
    print("fama_ami_client.py fehlt - bitte in denselben Ordner legen:\n  " + CLIENT_URL,
          file=sys.stderr)
    raise SystemExit(2)

# Aeltere Fassungen holen ohne 'limit' ab und laufen bei 'harga' in einen 502.
# Lieber hier klar abbrechen als spaeter mit einem TypeError.
_have = getattr(fama_ami_client, "CLIENT_VERSION", 0)
if _have < NEEDS_CLIENT:
    print(f"fama_ami_client.py ist veraltet (Version {_have}, benoetigt {NEEDS_CLIENT}).\n"
          "Bitte die Datei neu herunterladen und die alte ueberschreiben:\n  " + CLIENT_URL,
          file=sys.stderr)
    raise SystemExit(2)

SUPABASE_URL = os.environ.get("NUMIS_URL", "https://otumcdmymenwiliwzrhj.supabase.co")
RPC = SUPABASE_URL.rstrip("/") + "/rest/v1/rpc/"
BATCH_ROWS = 500          # Zeilen pro RPC-Aufruf
HTTP_RETRIES = 4


def service_key() -> str:
    key = os.environ.get("NUMIS_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        # PowerShell und cmd.exe setzen Umgebungsvariablen unterschiedlich.
        # In PowerShell ist 'set' ein Alias fuer Set-Variable und legt KEINE
        # Umgebungsvariable an - der Aufruf sieht erfolgreich aus, wirkt aber nicht.
        print("Umgebungsvariable NUMIS_SERVICE_KEY fehlt.\n"
              "\n"
              "  PowerShell (Eingabezeile beginnt mit 'PS'):\n"
              '      $env:NUMIS_SERVICE_KEY = "<service-role-key>"\n'
              "\n"
              "  cmd.exe:\n"
              "      set NUMIS_SERVICE_KEY=<service-role-key>\n"
              "\n"
              "  Mac/Linux:\n"
              "      export NUMIS_SERVICE_KEY=<service-role-key>\n"
              "\n"
              "Dauerhaft setzen (gilt auch fuer die Aufgabenplanung, danach neues\n"
              "Fenster oeffnen):\n"
              '      setx NUMIS_SERVICE_KEY "<service-role-key>"\n'
              "\n"
              "Zu finden im Supabase-Dashboard unter Project Settings -> API Keys\n"
              "als 'service_role'. Achtung: dieser Key umgeht alle Zugriffsregeln -\n"
              "nicht weitergeben und nicht in eine Datei im Repo schreiben.",
              file=sys.stderr)
        raise SystemExit(2)
    return key


def rpc(opener, name: str, payload: dict, key: str, timeout: int = 120):
    """Ruft eine Supabase-RPC auf; wiederholt bei Netz-/5xx-Fehlern."""
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "apikey": key,
        "Authorization": "Bearer " + key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }
    last = ""
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            req = urllib.request.Request(RPC + name, data=body, headers=headers, method="POST")
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    try:
                        raw = gzip.decompress(raw)
                    except OSError:
                        pass
                text = raw.decode("utf-8", errors="replace").strip()
                return json.loads(text) if text else None
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read(1500).decode("utf-8", errors="replace")
            except Exception:
                pass
            last = f"HTTP {exc.code}: {detail[:400]}"
            if exc.code < 500:           # 4xx wiederholen bringt nichts
                raise RuntimeError(last) from None
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        if attempt < HTTP_RETRIES:
            wait = 2 ** attempt
            print(f"      Versuch {attempt} fehlgeschlagen ({last}) - warte {wait}s")
            time.sleep(wait)
    raise RuntimeError(last)


def fetch_fama_day(opener, day: dt.date, timeout: int, page_size: int,
                   page_style: str | None) -> list[dict]:
    """Holt einen Tag vollstaendig.

    Greift das Blaettern nicht, wirft fetch_table IncompleteResult. Das ist
    Absicht: ein halber Tag darf nicht als geholt gelten, sonst fehlen fuer
    immer Preise, ohne dass es auffaellt.
    """
    endpoint = f"harga?filter=pricedate,eq,'{day.isoformat()}'"
    return fetch_table(opener, endpoint, None, timeout, page_size=page_size,
                       quiet=True, page_style=page_style, strict=True)


# FAMA speichert Preisebene, Guteklasse und Einheit als Codes ("03", "051",
# "01"). Die Klartexte stehen in diesen offenen Referenztabellen.
LOOKUPS = [("level", "reflevel"), ("grade", "refgrade"), ("unit", "refunit")]


def sync_lookups(opener, key: str, args) -> None:
    """Holt die Code-Tabellen und legt sie in NuMIS ab.

    Muss vor dem Tagesimport laufen, sonst landen wieder Codes statt Namen
    in price_observations.
    """
    print("Referenztabellen abgleichen:")
    for kind, table in LOOKUPS:
        try:
            rows = fetch_table(opener, table, None, args.timeout,
                               page_size=args.page_size, quiet=True,
                               page_style=args.page_style, strict=True)
            n = rpc(opener, "numis_sync_fama_lookup",
                    {"p_kind": kind, "p_rows": rows}, key)
            print(f"   {table:<10} {len(rows):>4} Zeilen -> {n} uebernommen")
        except (RuntimeError, IncompleteResult) as exc:
            print(f"   {table:<10} FEHLER: {exc}")
            print("   Ohne diese Tabelle bleiben Codes stehen statt Klartext.")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7,
                    help="Wie viele Tage rueckwaerts geprueft werden (Standard 7)")
    ap.add_argument("--from", dest="from_", help="Startdatum JJJJ-MM-TT (statt --days)")
    ap.add_argument("--to", help="Enddatum JJJJ-MM-TT (Standard: heute)")
    ap.add_argument("--timeout", type=int, default=90)
    ap.add_argument("--page-size", type=int, default=1000, help="Zeilen pro FAMA-Anfrage")
    ap.add_argument("--page-style", choices=["auto", "offset", "page", "skip", "start", "none"],
                    help="Blaetter-Verfahren; mit 'fama_ami_client.py pagetest' ermitteln")
    ap.add_argument("--backfill", action="store_true",
                    help="bereits importierte Zeilen neu aufloesen (Codes -> Klartext); "
                         "nutzt die gespeicherten Rohzeilen, kein erneuter FAMA-Abruf")
    ap.add_argument("--dry-run", action="store_true",
                    help="Nur abrufen und zeigen, nichts in die Datenbank schreiben")
    ap.add_argument("--insecure", action="store_true")
    args = ap.parse_args()

    key = "DRY-RUN" if args.dry_run else service_key()
    opener = make_opener(args.insecure)

    today = dt.date.today()
    end = dt.date.fromisoformat(args.to) if args.to else today
    start = dt.date.fromisoformat(args.from_) if args.from_ else end - dt.timedelta(days=args.days - 1)
    if end < start:
        start, end = end, start

    print(f"NuMIS: {SUPABASE_URL}")
    print(f"Fenster: {start} bis {end}\n")

    if not args.dry_run:
        sync_lookups(opener, key, args)
        if args.backfill:
            n = rpc(opener, "numis_backfill_fama_codes", {}, key)
            print(f"Nachgerechnet: {n:,} bestehende Beobachtungen neu aufgeloest.\n")

    if args.dry_run:
        days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
        print(f"Trockenlauf - alle {len(days)} Tage werden geholt, aber nichts geschrieben.\n")
    else:
        missing = rpc(opener, "numis_missing_days",
                      {"p_from": start.isoformat(), "p_to": end.isoformat()}, key)
        days = [dt.date.fromisoformat(d) for d in (missing or [])]
        if not days:
            print("Nichts zu tun - alle Tage im Fenster sind bereits geholt.")
            return 0
        print(f"Offen: {len(days)} Tag(e) -> {', '.join(d.isoformat() for d in days)}\n")

    total_raw = total_obs = 0
    failed: list[str] = []

    for day in days:
        print(f"{day}:")
        try:
            rows = fetch_fama_day(opener, day, args.timeout, args.page_size, args.page_style)
        except IncompleteResult as exc:
            print(f"   UNVOLLSTAENDIG: {exc}")
            print("   Tag wird NICHT als geholt vermerkt.")
            failed.append(day.isoformat())
            if not args.dry_run:
                try:
                    rpc(opener, "numis_ingest_fama_finish",
                        {"p_date": day.isoformat(), "p_raw": 0, "p_obs": 0,
                         "p_error": f"unvollstaendig: {exc}"[:500]}, key)
                except RuntimeError:
                    pass
            continue
        except Exception as exc:
            print(f"   FAMA-Abruf fehlgeschlagen: {type(exc).__name__}: {exc}")
            failed.append(day.isoformat())
            if not args.dry_run:
                try:
                    rpc(opener, "numis_ingest_fama_finish",
                        {"p_date": day.isoformat(), "p_raw": 0, "p_obs": 0,
                         "p_error": f"FAMA-Abruf: {exc}"[:500]}, key)
                except RuntimeError:
                    pass
            continue

        print(f"   {len(rows):,} Zeilen von FAMA")
        if args.dry_run:
            if rows:
                print(f"   Beispiel: {json.dumps(rows[0], ensure_ascii=False)[:300]}")
            continue

        day_raw = day_obs = 0
        try:
            # Leerer Tag: Schleife laeuft nicht, 'finish' setzt ihn auf EMPTY.
            for i in range(0, len(rows), BATCH_ROWS):
                batch = rows[i:i + BATCH_ROWS]
                res = rpc(opener, "numis_ingest_fama_batch",
                          {"p_date": day.isoformat(), "p_rows": batch}, key)
                day_raw += (res or {}).get("raw_rows", 0)
                day_obs += (res or {}).get("observation_rows", 0)
                print(f"   Stapel {i // BATCH_ROWS + 1}: "
                      f"{(res or {}).get('raw_rows', 0)} roh / "
                      f"{(res or {}).get('observation_rows', 0)} Beobachtungen")
            # Erst jetzt gilt der Tag als erledigt.
            rpc(opener, "numis_ingest_fama_finish",
                {"p_date": day.isoformat(), "p_raw": day_raw, "p_obs": day_obs}, key)
        except RuntimeError as exc:
            print(f"   Import fehlgeschlagen: {exc}")
            failed.append(day.isoformat())
            try:
                rpc(opener, "numis_ingest_fama_finish",
                    {"p_date": day.isoformat(), "p_raw": day_raw, "p_obs": day_obs,
                     "p_error": str(exc)[:500]}, key)
            except RuntimeError:
                pass
            continue

        total_raw += day_raw
        total_obs += day_obs
        print(f"   fertig: {day_raw:,} Rohzeilen, {day_obs:,} Beobachtungen"
              + ("   (Tag ohne Daten)" if day_raw == 0 else ""))

    print(f"\nGesamt: {total_raw:,} Rohzeilen, {total_obs:,} Beobachtungen")
    if failed:
        print(f"Fehlgeschlagen: {', '.join(failed)}")
        print("Diese Tage werden beim naechsten Lauf automatisch erneut versucht.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
