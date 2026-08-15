#!/usr/bin/env python3
"""
fama_ami_client.py - Abruf der FAMA-AMI-Preisdaten.

Die API wurde aus den App-Bundles von ami.fama.gov.my rekonstruiert
(siehe README, Abschnitt "Die AMI-API"):

  REST-Basis   https://ami.fama.gov.my/api/gen/      (zweite Instanz: /api2/gen/)
  Aufrufform   GET <basis><tabelle>?filter=<spalte>,<op>,'<wert>'
  Anmeldung    Keycloak, https://ami.fama.gov.my/kc/
               Realm FAMA  + Client "webadmin"    (Web-App)
               Realm AMI   + Client "respondent"  (AWAM-App)
               Realm FAMA  + Client "mobilefama"  (Mobile-App)

Die Preistabelle heisst "harga". commoditytype: D = harian (taeglich),
W = mingguan (woechentlich). status: Hantar = eingereicht,
Disemak = geprueft, Ditolak = abgelehnt.

WICHTIG zum Passwort: Es wird nur zur Laufzeit abgefragt bzw. aus einer
Umgebungsvariablen gelesen und ausschliesslich an den Keycloak-Server
geschickt. Es wird nirgends gespeichert und steht in keiner Datei.

Beispiele
---------
    # 1. Ohne Anmeldung testen, was offen erreichbar ist
    python3 fama_ami_client.py probe

    # 2. Anmelden und Referenztabellen holen
    python3 fama_ami_client.py refs --user deine@mail.de

    # 3. Tagespreise eines Zeitraums als CSV
    python3 fama_ami_client.py prices --user deine@mail.de \
        --from 2026-08-01 --to 2026-08-14 --out harga.csv

    # 4. Beliebige Tabelle roh abrufen
    python3 fama_ami_client.py table --user deine@mail.de \
        --name refcommodity --out refcommodity.csv

Passwort alternativ per Umgebungsvariable:
    set FAMA_PASSWORD=...        (Windows)
    export FAMA_PASSWORD=...     (Mac/Linux)

Nur Standardbibliothek.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import gzip
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

ORIGIN = "https://ami.fama.gov.my"
API = ORIGIN + "/api/gen/"
API2 = ORIGIN + "/api2/gen/"
KC = ORIGIN + "/kc"

REALM_CLIENTS = [("FAMA", "webadmin"), ("AMI", "respondent"), ("FAMA", "mobilefama")]

# Aus dem App-Bundle extrahierte Tabellen-/Sichtnamen.
TABLES: dict[str, str] = {
    # Preise
    "harga": "harga",
    "harga_harian": "harga?filter=commoditytype,eq,'D'",
    "harga_mingguan": "harga?filter=commoditytype,eq,'W'",
    "harga2h": "harga2h",
    "harga2m": "harga2m",
    "harga_old": "harga_old",
    "monatsschnitt": "mv_mon_avg",
    "monatsmedian": "mv_mon_med",
    # Stammdaten
    "refcommodity": "refcommodity",
    "refcommodityvariety": "refcommodityvariety",
    "refcommoditycategory": "refcommoditycategory",
    "refcommoditygroup": "refcommoditygroup",
    "refcommoditytype": "refcommoditytype",
    "refgrade": "refgrade",
    "refunit": "refunit",
    "refcollectiontype": "refcollectiontype",
    "reflevel": "reflevel",
    "vclevel": "vclevel",
    "vstate": "vstate",
    "vdistrict": "vdistrict",
    "pasarborong": "f_vpasarborong",
    "refinstitution": "refinstitution",
    # Berichte
    "laporansegar": "smp.laporansegar",
    "laporanperingkat": "smp.laporanperingkat",
    "laporannegeri": "smp.laporannegeri",
    "laporankategori": "smp.laporankategori",
    "wartabarangan": "vwartabarangan",
}

REF_SET = ["refcommodity", "refcommodityvariety", "refcommoditycategory",
           "refcommoditygroup", "refcommoditytype", "refgrade", "refunit",
           "reflevel", "vstate", "vdistrict"]

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")


# --------------------------------------------------------------------------- HTTP

def make_opener(insecure: bool):
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))


def request(op, url: str, token: str | None = None, data: bytes | None = None,
            content_type: str | None = None, timeout: int = 60) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json",
               "Accept-Encoding": "gzip", "Origin": ORIGIN, "Referer": ORIGIN + "/web/"}
    if token:
        headers["Authorization"] = "Bearer " + token
    if content_type:
        headers["Content-Type"] = content_type
    out: dict[str, Any] = {"url": url}
    try:
        with op.open(urllib.request.Request(url, data=data, headers=headers), timeout=timeout) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except OSError:
                    pass
            out.update(status=r.status, text=raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(2000).decode("utf-8", errors="replace")
        except Exception:
            pass
        out.update(status=e.code, error=f"HTTP {e.code} {e.reason}", text=body)
    except Exception as e:
        out.update(status=None, error=f"{type(e).__name__}: {e}", text="")
    return out


def as_json(res: dict[str, Any]) -> Any | None:
    text = res.get("text") or ""
    if not text.lstrip().startswith(("{", "[")):
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def rows_of(payload: Any) -> list[dict]:
    """Vertraegt {"records":[...]}, {"data":[...]} und blanke Listen."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("records", "data", "rows", "result"):
            val = payload.get(key)
            if isinstance(val, list):
                return [r for r in val if isinstance(r, dict)]
    return []


# --------------------------------------------------------------------------- Auth

def login(op, user: str, password: str, realm: str | None, client: str | None,
          timeout: int) -> tuple[str | None, str]:
    """Keycloak Direct-Access-Grant. Probiert die bekannten Realm/Client-Paare."""
    pairs = [(realm, client)] if realm and client else REALM_CLIENTS
    last = ""
    for rlm, cli in pairs:
        url = f"{KC}/realms/{urllib.parse.quote(rlm)}/protocol/openid-connect/token"
        body = urllib.parse.urlencode({
            "grant_type": "password", "client_id": cli,
            "username": user, "password": password, "scope": "openid",
        }).encode()
        res = request(op, url, data=body,
                      content_type="application/x-www-form-urlencoded", timeout=timeout)
        payload = as_json(res) or {}
        if res.get("status") == 200 and payload.get("access_token"):
            print(f"  Anmeldung ok  (realm={rlm}, client={cli})")
            return payload["access_token"], f"{rlm}/{cli}"

        code = payload.get("error", "")
        desc = payload.get("error_description") or res.get("error") or ""
        # Die Fehlerkennung sagt genau, WO das Problem liegt.
        hint = {
            "invalid_grant": "Benutzername oder Passwort stimmt nicht (Zugangsweg selbst ist offen)",
            "unauthorized_client": "dieser Client erlaubt kein Passwort-Login -> Browser-Login noetig",
            "invalid_client": "Client-ID unbekannt in diesem Realm",
            "invalid_request": "Anfrage unvollstaendig",
        }.get(code, "")
        last = f"{rlm}/{cli}: {res.get('status')} {code} {desc}"
        print(f"  fehlgeschlagen: realm={rlm} client={cli} -> {res.get('status')} "
              f"{code}: {desc}" + (f"\n                  = {hint}" if hint else ""))
    return None, last


def get_password(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    env = os.environ.get("FAMA_PASSWORD")
    if env:
        return env
    return getpass.getpass("AMI-Passwort (Eingabe bleibt unsichtbar): ")


# --------------------------------------------------------------------------- API

def fetch_table(op, endpoint: str, token: str | None, timeout: int,
                page_size: int = 0, base: str | None = None, quiet: bool = False) -> list[dict]:
    """Holt eine Tabelle seitenweise mit ?limit=&offset= (am System gemessen).

    Ohne 'limit' liefert der Server bei grossen Tabellen einen 502, weil er die
    komplette Tabelle zu erzeugen versucht. Deshalb wird immer begrenzt.

    Wuerde 'offset' ignoriert, kaeme endlos dieselbe Seite - das wird an der
    ersten Zeile jeder Seite erkannt und bricht dann sauber ab.
    """
    base = base or API          # erst zur Laufzeit aufloesen, damit API ersetzbar bleibt
    limit = page_size or 1000
    collected: list[dict] = []
    offset = 0
    seen_first: set[str] = set()
    while True:
        sep = "&" if "?" in endpoint else "?"
        url = f"{base}{endpoint}{sep}limit={limit}&offset={offset}"
        res = request(op, url, token=token, timeout=timeout)
        payload = as_json(res)
        if payload is None:
            raise RuntimeError(f"{res.get('status')} {res.get('error') or ''} :: "
                               f"{(res.get('text') or '')[:160]}")
        batch = rows_of(payload)
        if not batch:
            return collected

        signature = json.dumps(batch[0], sort_keys=True, default=str)[:400]
        if signature in seen_first:
            print("    !! 'offset' wird vom Server ignoriert - Abbruch, "
                  "Ergebnis kann unvollstaendig sein")
            return collected
        seen_first.add(signature)

        collected.extend(batch)
        if not quiet and offset:
            print(f"    +{len(batch)} Zeilen (gesamt {len(collected):,})")
        if len(batch) < limit:
            return collected
        offset += limit


def write_csv(rows: list[dict], path: str) -> None:
    if not rows:
        print("  (keine Zeilen - keine Datei geschrieben)")
        return
    fields: list[str] = []
    for row in rows:
        for k in row:
            if k not in fields:
                fields.append(k)
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  geschrieben: {path}  ({len(rows):,} Zeilen, {len(fields)} Spalten)")


# --------------------------------------------------------------------------- Befehle

def cmd_probe(op, args) -> int:
    """Testet ohne Anmeldung, was offen ist und was ein Token braucht."""
    print("== Ohne Anmeldung testen\n")
    # Kein '?page=n,size': diese Syntax loest am Server einen 502 aus.
    targets = [API, API2, API + "reflevel", API + "vstate", API + "refcommodity",
               API + "refgrade", API + "auth/menu"]
    open_ok, need_auth = 0, 0
    for url in targets:
        res = request(op, url, timeout=args.timeout)
        payload = as_json(res)
        rows = rows_of(payload) if payload is not None else []
        status = res.get("status")
        if status == 200 and payload is not None:
            open_ok += 1
            if rows:
                print(f"  OFFEN  200  {url}\n         Spalten: {sorted(rows[0])[:15]}")
            else:
                keys = sorted(payload)[:10] if isinstance(payload, dict) else f"array[{len(payload)}]"
                print(f"  OFFEN  200  {url}\n         {keys}")
        elif status in (401, 403):
            need_auth += 1
            print(f"  TOKEN  {status}  {url}   <- vorhanden, Anmeldung noetig")
        else:
            print(f"  {str(status or 'ERR'):>5}       {url}  {(res.get('text') or res.get('error') or '')[:90]}")
    print(f"\n  offen: {open_ok}   anmeldepflichtig: {need_auth}")
    print("\n  Beides ist ein verwertbares Ergebnis: 401/403 heisst, die Tabelle")
    print("  existiert und ist mit deinem Konto abrufbar - dann 'refs' oder 'prices' nutzen.")
    return 0


def cmd_apitest(op, args) -> int:
    """Ermittelt OHNE Anmeldung die richtige Abruf-Syntax und was offen ist.

    Hintergrund: '?page=1,1' loest am Server einen 502 aus. Die Blaettersyntax
    dieser API ist also eine andere - hier wird sie an einer bekannt offenen,
    kleinen Tabelle (reflevel) durchprobiert.
    """
    import datetime as _dt

    def probe_url(endpoint: str, token: str | None = None) -> tuple[Any, int, list[str]]:
        res = request(op, API + endpoint, token=token, timeout=args.timeout)
        payload = as_json(res)
        rows = rows_of(payload) if payload is not None else []
        cols = sorted(rows[0]) if rows else []
        return res.get("status"), len(rows), cols

    print("== A. Blaetter-Syntax an der offenen Tabelle 'reflevel' ermitteln\n")
    base_status, base_n, base_cols = probe_url("reflevel")
    print(f"  ohne Parameter          -> {base_status}  {base_n} Zeilen")
    if base_cols:
        print(f"     Spalten: {base_cols}")

    variants = ["?limit=3", "?_limit=3", "?size=3", "?take=3", "?top=3",
                "?per_page=3", "?page=1&size=3", "?page=1&limit=3",
                "?offset=0&limit=3", "?page=1,3", "?start=0&count=3"]
    working: list[str] = []
    for v in variants:
        st, n, _ = probe_url("reflevel" + v)
        mark = ""
        if st == 200 and base_n and n == 3:
            working.append(v)
            mark = "   <- begrenzt korrekt auf 3"
        elif st != 200:
            mark = "   (Fehler)"
        elif n == base_n:
            mark = "   (Parameter wird ignoriert)"
        print(f"  {v:<22} -> {st}  {n} Zeilen{mark}")

    limit_syntax = working[0] if working else ""
    print(f"\n  Ergebnis: " + (f"funktionierende Begrenzung = {working}"
                               if working else "keine Begrenzung erkannt, Tabellen kommen komplett"))

    print("\n== B. Preistabelle 'harga' mit Datumsfilter (ohne Blaettern)\n")
    today = _dt.date.today()
    dates = [args.date] if args.date else [
        (today - _dt.timedelta(days=d)).isoformat() for d in (1, 2, 3, 7, 14)]
    for d in dates:
        ep = f"harga?filter=pricedate,eq,'{d}'"
        if limit_syntax:
            ep += "&" + limit_syntax.lstrip("?")
        st, n, cols = probe_url(ep)
        print(f"  {d}  -> {st}  {n} Zeilen")
        if cols:
            print(f"     Spalten: {cols}")
            break

    print("\n== C. Weitere Tabellen ohne Anmeldung\n")
    others = ["refcommodity", "refgrade", "refunit", "refcommodityvariety",
              "refcommoditycategory", "vdistrict", "f_vpasarborong",
              "harga2h", "harga2m", "mv_mon_avg", "smp.laporansegar"]
    for name in others:
        ep = name + (("?" + limit_syntax.lstrip("?")) if limit_syntax else "")
        st, n, cols = probe_url(ep)
        flag = "OFFEN" if st == 200 and n else ("TOKEN" if st in (401, 403) else "     ")
        print(f"  {flag} {str(st):>4}  {name:<24} {n} Zeilen")
        if cols:
            print(f"        Spalten: {cols[:14]}")
    print("\n  Hinweis: 'harga' ohne jeden Filter wird bewusst nicht abgerufen -")
    print("  die Tabelle ist gross und der Server antwortet dann mit 502.")
    return 0


def authenticate(op, args) -> str | None:
    """Anmeldung ist OPTIONAL - die Preistabellen sind offen erreichbar.

    Nur wenn --user gesetzt ist, wird ueberhaupt ein Token geholt. Bei einem
    ueber Google angelegten Konto kann der Passwort-Login prinzipiell nicht
    klappen: in Keycloak liegt dann gar kein Passwort, die Pruefung passiert
    bei Google. Fuer die Preisdaten wird beides nicht gebraucht.
    """
    if not getattr(args, "user", None):
        return None
    token, _ = login(op, args.user, get_password(args.password), args.realm, args.client, args.timeout)
    if not token:
        print("\n  Hinweis: Abruf laeuft ohne Token weiter - die Preistabellen sind offen.\n"
              "  Ein Passwort-Login ist bei Google-Konten technisch nicht moeglich.\n",
              file=sys.stderr)
    return token


def cmd_refs(op, args) -> int:
    token = authenticate(op, args)
    os.makedirs(args.outdir, exist_ok=True)
    print()
    for name in REF_SET:
        endpoint = TABLES[name]
        try:
            rows = fetch_table(op, endpoint, token, args.timeout,
                               page_size=args.page_size, quiet=True)
        except RuntimeError as exc:
            print(f"  {name}: Fehler {exc}")
            continue
        print(f"  {name}: {len(rows):,} Zeilen")
        write_csv(rows, os.path.join(args.outdir, name + ".csv"))
    return 0


def cmd_prices(op, args) -> int:
    """Holt 'harga' Tag fuer Tag.

    Bewusst Tag fuer Tag mit 'eq' statt einer Spanne mit 'ge'/'le': die App
    selbst benutzt nur 'eq'/'neq', ob der Server Vergleichsoperatoren kann, ist
    also ungeprueft. Ausserdem bleibt so jede einzelne Anfrage klein - genau
    daran (zu grosse Antwort) scheitert der Server sonst mit 502.
    """
    import datetime as _dt

    token = authenticate(op, args)
    try:
        start = _dt.date.fromisoformat(args.from_)
        end = _dt.date.fromisoformat(args.to) if args.to else start
    except (TypeError, ValueError):
        print("Fehlt oder ungueltig: --from JJJJ-MM-TT (optional --to JJJJ-MM-TT)", file=sys.stderr)
        return 2
    if end < start:
        start, end = end, start

    extra = []
    if args.type:
        extra.append(f"filter=commoditytype,eq,'{args.type}'")
    if args.level:
        extra.append(f"filter=commoditylevel,eq,{urllib.parse.quote(chr(39) + args.level + chr(39))}")
    if args.status:
        extra.append(f"filter=status,eq,'{args.status}'")

    all_rows: list[dict] = []
    day = start
    days = (end - start).days + 1
    print(f"\n  Zeitraum {start} bis {end}  ({days} Tag(e))\n")
    while day <= end:
        endpoint = f"harga?filter=pricedate,eq,'{day.isoformat()}'"
        if extra:
            endpoint += "&" + "&".join(extra)
        try:
            rows = fetch_table(op, endpoint, token, args.timeout,
                               page_size=args.page_size, quiet=True)
        except RuntimeError as exc:
            print(f"  {day}: Fehler {exc}")
            day += _dt.timedelta(days=1)
            continue
        all_rows.extend(rows)
        print(f"  {day}: {len(rows):,} Zeilen  (gesamt {len(all_rows):,})")
        day += _dt.timedelta(days=1)

    if all_rows:
        print(f"\n  Spalten: {sorted(all_rows[0])}")
    write_csv(all_rows, args.out)
    return 0


def cmd_table(op, args) -> int:
    token = authenticate(op, args)
    endpoint = TABLES.get(args.name, args.name)
    if args.filter:
        sep = "&" if "?" in endpoint else "?"
        endpoint += sep + "&".join(f"filter={f}" for f in args.filter)
    print(f"\n  Abruf: {API}{endpoint}")
    try:
        rows = fetch_table(op, endpoint, token, args.timeout, page_size=args.page_size)
    except RuntimeError as exc:
        print(f"  Fehler: {exc}", file=sys.stderr)
        return 1
    if rows:
        print(f"  Spalten: {sorted(rows[0])}")
    write_csv(rows, args.out or (args.name.replace(".", "_") + ".csv"))
    return 0


def main() -> int:
    # Gemeinsame Optionen, damit sie vor UND nach dem Unterbefehl stehen duerfen.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--timeout", type=int, default=60)
    common.add_argument("--insecure", action="store_true")

    ap = argparse.ArgumentParser(description=__doc__, parents=[common],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True, parser_class=lambda **kw: argparse.ArgumentParser(parents=[common], **kw))

    def add_auth(p):
        p.add_argument("--user", help="AMI-Anmeldeadresse (E-Mail)")
        p.add_argument("--password", help="besser weglassen - wird sonst abgefragt")
        p.add_argument("--realm", help="FAMA oder AMI (sonst werden beide probiert)")
        p.add_argument("--client", help="webadmin | respondent | mobilefama")
        # Der Server versteht ?limit=&offset= . Ohne 'limit' versucht er bei
        # grossen Tabellen die komplette Ausgabe und antwortet mit 502.
        p.add_argument("--page-size", type=int, default=1000,
                       help="Zeilen pro Anfrage (Standard 1000)")

    p = sub.add_parser("probe", help="ohne Anmeldung pruefen, was erreichbar ist")

    p = sub.add_parser("apitest", help="ohne Anmeldung: Blaetter-Syntax und offene Tabellen ermitteln")
    p.add_argument("--date", help="konkretes Datum JJJJ-MM-TT statt der letzten Tage")

    p = sub.add_parser("refs", help="Referenz-/Stammdatentabellen als CSV")
    add_auth(p)
    p.add_argument("--outdir", default="fama_refs")

    p = sub.add_parser("prices", help="Preistabelle 'harga' als CSV")
    add_auth(p)
    p.add_argument("--from", dest="from_", required=True, help="Startdatum JJJJ-MM-TT")
    p.add_argument("--to", help="Enddatum JJJJ-MM-TT (ohne Angabe nur der Starttag)")
    p.add_argument("--type", choices=["D", "W"], help="D = taeglich, W = woechentlich")
    p.add_argument("--level", help="Preisebene, z.B. Ladang | Borong | Runcit")
    p.add_argument("--status", help="z.B. Disemak (geprueft)")
    p.add_argument("--out", default="harga.csv")

    p = sub.add_parser("table", help="beliebige Tabelle abrufen")
    add_auth(p)
    p.add_argument("--name", required=True, help=f"Kurzname oder roher Tabellenname. Bekannt: {', '.join(sorted(TABLES))}")
    p.add_argument("--filter", action="append", help="z.B. --filter \"pricedate,eq,'2026-08-14'\"")
    p.add_argument("--out")

    args = ap.parse_args()
    op = make_opener(args.insecure)
    return {"probe": cmd_probe, "apitest": cmd_apitest, "refs": cmd_refs,
            "prices": cmd_prices, "table": cmd_table}[args.cmd](op, args)


if __name__ == "__main__":
    sys.exit(main())
