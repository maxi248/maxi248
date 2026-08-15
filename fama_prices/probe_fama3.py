#!/usr/bin/env python3
"""
probe_fama3.py - Runde 3: die eigentlichen AMI-Apps auslesen.

Was die Snapshots aus Runde 2 gezeigt haben:

  ami.fama.gov.my/            = reine Next.js-Landingpage (Werbung + Login-Auswahl),
                                enthaelt KEINE Preisdaten. Die "harga"-Treffer aus
                                Runde 2 stammten nur aus dem Meta-Description-Text.
  ami.fama.gov.my/awam        = eigenstaendige Quasar/Vue-App ("AWAM" = oeffentlich)
  ami.fama.gov.my/web-awam    = Quasar-App, mit Excel-Export (xlsx.full.min.js)
  ami.fama.gov.my/web         = Quasar-App "FAMA - Maklumat Harga", mit Excel-Export
  ami.fama.gov.my/mobile      = Quasar-App
  alle vier laden Keycloak    = https://ami.fama.gov.my/kc/js/keycloak.js

Runde 2 hat die App-Bundles NIE gelesen: die Seiten liegen unter /awam (ohne
Slash), ihre Scripts sind relativ ("js/app.f23a7cd2.js"), also wurde daraus
faelschlich https://ami.fama.gov.my/js/app... statt .../awam/js/app...

Runde 3 macht es richtig und sucht in den App-Bundles nach:
  - der REST-Basis-URL (axios baseURL, process.env.API o.ae.)
  - konkreten Endpunkt-Pfaden
  - der Keycloak-Konfiguration (realm, clientId) - daraus laesst sich ableiten,
    ob ein oeffentlicher Token-Zugang moeglich ist
  - den Vue-Router-Routen (welche Ansichten es gibt)

Ergebnisse mit HTTP 401/403 sind KEIN Fehlschlag, sondern der Beweis, dass es
eine API gibt - sie braucht dann nur ein Token.

    python3 probe_fama3.py
    python3 probe_fama3.py --timeout 60

Nur Standardbibliothek. App-Bundles landen in fama_bundles/.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

ORIGIN = "https://ami.fama.gov.my"
APPS = ["awam", "web-awam", "web", "mobile"]

BUNDLEDIR = "fama_bundles"

DATA_WORDS = ["harga", "komoditi", "runcit", "borong", "ladang", "pasar", "gred",
              "barang", "sayur", "buah", "price", "commodity", "market", "item",
              "negeri", "daerah", "laporan", "carta", "senarai", "purata"]

ASSET_EXT = (".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff",
             ".woff2", ".ttf", ".eot", ".mp4", ".webp", ".map", ".html")

NOISE = re.compile(r"(google|gstatic|jquery|bootstrap|cloudflare|jsdelivr|unpkg"
                   r"|w3\.org|schema\.org|facebook|instagram|twitter|x\.com|youtube"
                   r"|github|npmjs|vuejs|quasar\.dev|redux|stackoverflow|bit\.ly"
                   r"|qrserver|mozilla|example\.)", re.I)

# --- Muster fuer minifizierten Quasar/axios-Code -------------------------------
RE_BASEURL = re.compile(
    r"""(?:baseURL|baseUrl|API_URL|apiUrl|API_BASE|VUE_APP_\w*API\w*|process\.env\.\w*API\w*)"""
    r"""\s*[:=]\s*["'`]([^"'`]{4,200})["'`]""")
RE_ABS = re.compile(r"""["'`](https?://[a-zA-Z0-9.\-]+(?::\d+)?(?:/[^"'`\s\\]{0,200})?)["'`]""")
RE_PATH = re.compile(
    r"""["'`](/(?:api|rest|v\d|service|services)[^"'`\s\\]{0,160}"""
    r"""|/[^"'`\s\\]{0,60}(?:""" + "|".join(DATA_WORDS) + r""")[^"'`\s\\]{0,100})["'`]""", re.I)
RE_AXIOS = re.compile(
    r"""\.(?:get|post|put|delete)\s*\(\s*["'`]([^"'`]{2,200})["'`]""")
RE_TEMPLATE = re.compile(r"""[`]([^`]{4,160}\$\{[^`]{0,120})[`]""")
RE_REALM = re.compile(r"""realm\s*:\s*["']([^"']{1,60})["']""")
RE_CLIENTID = re.compile(r"""clientId\s*:\s*["']([^"']{1,60})["']""")
RE_KCURL = re.compile(r"""url\s*:\s*["'](https?://[^"']*?/kc[^"']*)["']""")
RE_ROUTE = re.compile(r"""path\s*:\s*["'](/[^"']{0,80})["']""")


def opener_for(insecure: bool):
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))


def fetch(op, url: str, timeout: int, referer: str | None = None) -> dict[str, Any]:
    h = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "gzip",
         "Accept-Language": "ms-MY,ms;q=0.9,en;q=0.8"}
    if referer:
        h["Referer"] = referer
    out: dict[str, Any] = {"url": url}
    try:
        with op.open(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            raw = r.read(20_000_000)
            if r.headers.get("Content-Encoding") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except OSError:
                    pass
            out.update(status=r.status, content_type=r.headers.get("Content-Type", ""),
                       bytes=len(raw), text=raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(4000).decode("utf-8", errors="replace")
        except Exception:
            pass
        out.update(status=e.code, error=f"HTTP {e.code} {e.reason}", body=body,
                   content_type=e.headers.get("Content-Type", "") if e.headers else "")
    except Exception as e:
        out.update(status=None, error=f"{type(e).__name__}: {e}")
    return out


def clean(raw: str, base: str) -> str | None:
    raw = raw.strip()
    if not raw or raw.startswith(("data:", "mailto:", "javascript:", "#", "tel:")):
        return None
    low = raw.lower()
    if any(low.endswith(e) for e in ASSET_EXT) or low.endswith(".js"):
        return None
    if NOISE.search(low):
        return None
    absolute = urllib.parse.urljoin(base, raw)
    return absolute if absolute.startswith("http") else None


def scan_bundle(text: str, base: str) -> dict[str, Any]:
    found: dict[str, Any] = {
        "base_urls": sorted({m.group(1) for m in RE_BASEURL.finditer(text)}),
        "realms": sorted({m.group(1) for m in RE_REALM.finditer(text)}),
        "client_ids": sorted({m.group(1) for m in RE_CLIENTID.finditer(text)}),
        "kc_urls": sorted({m.group(1) for m in RE_KCURL.finditer(text)}),
        "routes": sorted({m.group(1) for m in RE_ROUTE.finditer(text)})[:60],
        "templates": sorted({m.group(1) for m in RE_TEMPLATE.finditer(text)
                             if re.search("|".join(DATA_WORDS) + "|api", m.group(1), re.I)})[:40],
    }
    cands: set[str] = set()
    rel: set[str] = set()
    for pat in (RE_ABS, RE_PATH, RE_AXIOS):
        for m in pat.finditer(text):
            raw = m.group(1).strip()
            # Relative Pfade merken: die gehoeren an die API-Basis, nicht an die Seiten-URL.
            if raw.startswith("/") and not raw.startswith("//"):
                rel.add(raw)
            c = clean(raw, base)
            if c:
                cands.add(c)
    found["candidates"] = cands
    found["rel_paths"] = rel
    return found


def save(folder: str, name: str, text: str) -> str:
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120])
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="fama_probe3_report.json")
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--insecure", action="store_true")
    ap.add_argument("--keep-vendor", action="store_true", help="auch die grossen vendor.js speichern")
    args = ap.parse_args()

    op = opener_for(args.insecure)
    report: dict[str, Any] = {"apps": {}, "keycloak": {}, "endpoints": {
        "open_json": [], "auth_required": [], "other": []}}
    all_cands: set[str] = set()
    all_rel: set[str] = set()
    all_bases: set[str] = set()
    realms: set[str] = set()
    kc_urls: set[str] = set()

    print("== 1. Die vier AMI-Apps und ihre Bundles laden\n")
    for app in APPS:
        base = f"{ORIGIN}/{app}/"          # <- Trailing Slash: DAS war der Fehler in Runde 2
        page = fetch(op, base, args.timeout)
        info: dict[str, Any] = {"index_status": page.get("status"), "bundles": []}
        print(f"  {str(page.get('status') or 'ERR'):>5}  {base}")
        html = page.get("text")
        if not html:
            report["apps"][app] = info
            continue

        srcs = [urllib.parse.urljoin(base, m.group(1).strip('"\''))
                for m in re.finditer(r"""<script[^>]+src=["']?([^"'\s>]+)""", html, re.I)]
        for src in srcs:
            if "keycloak.js" in src:
                continue
            is_vendor = "vendor" in src
            res = fetch(op, src, args.timeout, referer=base)
            entry = {"url": src, "status": res.get("status"), "bytes": res.get("bytes")}
            info["bundles"].append(entry)
            if not res.get("text"):
                print(f"        {str(res.get('status') or 'ERR'):>5}  {src.rsplit('/', 1)[-1]}")
                continue
            print(f"        {res['status']:>5}  {src.rsplit('/', 1)[-1]}  ({res['bytes']:,} B)")
            hit = scan_bundle(res["text"], base)
            cands = hit.pop("candidates")
            all_rel |= hit.pop("rel_paths")
            all_cands |= cands
            all_bases |= {b for b in hit["base_urls"] if b.startswith("http")}
            realms |= set(hit["realms"])
            kc_urls |= set(hit["kc_urls"])
            entry["found"] = {k: v for k, v in hit.items() if v}
            for key in ("base_urls", "realms", "client_ids", "kc_urls"):
                if hit[key]:
                    print(f"              {key}: {hit[key]}")
            if hit["routes"]:
                print(f"              routes: {hit['routes'][:12]}")
            if cands:
                print(f"              +{len(cands)} Endpunkt-Kandidaten")
            if not is_vendor or args.keep_vendor:
                save(BUNDLEDIR, f"{app}_{src.rsplit('/', 1)[-1]}", res["text"])
        report["apps"][app] = info

    print("\n== 2. Keycloak-Konfiguration abfragen")
    kc_base = (sorted(kc_urls)[0].rstrip("/") if kc_urls else f"{ORIGIN}/kc")
    for realm in sorted(realms) or ["fama", "ami", "awam", "master"]:
        url = f"{kc_base}/realms/{urllib.parse.quote(realm)}/.well-known/openid-configuration"
        res = fetch(op, url, args.timeout)
        ok = res.get("text", "").lstrip().startswith("{")
        print(f"  {str(res.get('status') or 'ERR'):>5}  realm '{realm}'")
        if ok:
            try:
                cfg = json.loads(res["text"])
                report["keycloak"][realm] = {
                    "token_endpoint": cfg.get("token_endpoint"),
                    "grant_types": cfg.get("grant_types_supported"),
                    "issuer": cfg.get("issuer"),
                }
                print(f"        token_endpoint: {cfg.get('token_endpoint')}")
                print(f"        grant_types:    {cfg.get('grant_types_supported')}")
            except json.JSONDecodeError:
                pass

    # Relative Pfade an jede gefundene API-Basis haengen (nicht an die Seiten-URL).
    report["api_bases"] = sorted(all_bases)
    if all_bases:
        print(f"\n== 2b. Gefundene API-Basis-URLs: {sorted(all_bases)}")
        for b in all_bases:
            for path in all_rel:
                all_cands.add(b.rstrip("/") + path)

    ordered = sorted(all_cands)[:400]
    print(f"\n== 3. {len(ordered)} Endpunkt-Kandidaten testen")
    for url in ordered:
        res = fetch(op, url, args.timeout, referer=f"{ORIGIN}/awam/")
        st = res.get("status")
        text = res.get("text", "")
        rec = {"url": url, "status": st, "content_type": res.get("content_type"), "bytes": res.get("bytes")}
        if text.lstrip().startswith(("{", "[")):
            try:
                payload = json.loads(text)
                rec["schema"] = (
                    {"type": "array", "length": len(payload),
                     "first_keys": sorted(payload[0])[:30] if payload and isinstance(payload[0], dict) else None}
                    if isinstance(payload, list) else
                    {"type": "object", "keys": sorted(payload)[:30]})
                report["endpoints"]["open_json"].append(rec)
                print(f"  JSON  {st}  {url}")
                print(f"        -> {json.dumps(rec['schema'], ensure_ascii=False)[:250]}")
                continue
            except json.JSONDecodeError:
                pass
        if st in (401, 403):
            rec["body_excerpt"] = (res.get("body") or "")[:200]
            report["endpoints"]["auth_required"].append(rec)
            print(f"  AUTH  {st}  {url}   <- API vorhanden, Token noetig")
        elif st and st != 404:
            report["endpoints"]["other"].append(rec)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)

    print(f"\n== Report: {args.out}")
    print(f"== App-Bundles im Ordner: {BUNDLEDIR}/")
    o, a = len(report["endpoints"]["open_json"]), len(report["endpoints"]["auth_required"])
    if o:
        print(f"Ergebnis: {o} offene JSON-Endpunkte -> direkter automatischer Abruf moeglich.")
        return 0
    if a:
        print(f"Ergebnis: {a} Endpunkte mit 401/403 -> API existiert, Zugang ueber Keycloak-Token noetig.")
        return 0
    print("Ergebnis: keine Endpunkte bestaetigt. Bitte den Ordner fama_bundles/ schicken.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
