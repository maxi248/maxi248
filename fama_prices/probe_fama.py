#!/usr/bin/env python3
"""
probe_fama.py - Findet heraus, ob und wie die FAMA-/AMI-Preisdaten
automatisiert abrufbar sind.

Das Skript raet keine Endpunkte, sondern entdeckt sie:

  1. Erreichbarkeit der bekannten FAMA-Hosts pruefen.
  2. HTML der Portalseiten laden, alle <script src>-Bundles einsammeln.
  3. In HTML + JS-Bundles nach API-Pfaden suchen (fetch/axios/XHR-Strings).
  4. Jeden gefundenen Kandidaten aufrufen und pruefen, ob echtes JSON
     zurueckkommt - inklusive Vorschau der Felder.
  5. Ergebnis als JSON-Report ablegen.

Nur Standardbibliothek, keine Installation noetig:

    python3 probe_fama.py
    python3 probe_fama.py --out report.json --timeout 30

Hinweis: Aus manchen Netzen (z.B. CI-Runner mit Egress-Policy) sind
*.gov.my-Hosts blockiert. Das Skript meldet das dann explizit als
"blocked/unreachable" statt "kein API vorhanden".
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

# Einstiegsseiten, die die Preis-Frontends ausliefern.
SEED_PAGES = [
    "https://ami.fama.gov.my/",
    "https://www.fama.gov.my/harga-pasaran-terkini",
    "https://www.fama.gov.my/maklumat-harga-agromakanan-terpilih",
    "https://www.fama.gov.my/analisis-harga-komoditi-terpilih",
    "https://www.fama.gov.my/laporan-dan-analisis-maklumat-pasaran",
]

# Muster, an denen sich API-Aufrufe im JS erkennen lassen.
ENDPOINT_PATTERNS = [
    re.compile(r"""["'`](/(?:api|rest|service|services|data|json|ws)/[^"'`\s\\]{2,120})["'`]"""),
    re.compile(r"""["'`](https?://[a-z0-9.\-]*fama\.gov\.my/[^"'`\s\\]{2,160})["'`]""", re.I),
    re.compile(r"""(?:fetch|axios\.(?:get|post)|\$\.(?:get|ajax|getJSON))\s*\(\s*["'`]([^"'`]{2,160})["'`]"""),
    re.compile(r"""["'`]([^"'`\s\\]{2,120}\.(?:json|geojson))["'`]"""),
]

# Pfade, die in Behoerden-Portalen erfahrungsgemaess Daten liefern und
# billig mitgetestet werden koennen, falls die JS-Analyse nichts findet.
FALLBACK_PATHS = [
    "/api", "/api/", "/api/v1", "/api/v1/", "/api/harga", "/api/price",
    "/api/commodity", "/api/komoditi", "/rest", "/data", "/swagger.json",
    "/openapi.json", "/v3/api-docs", "/swagger-ui/index.html", "/sitemap.xml",
    "/robots.txt",
]

MAX_BUNDLES = 40
MAX_CANDIDATES = 120


def build_opener(insecure: bool) -> urllib.request.OpenerDirector:
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))


def fetch(opener, url: str, timeout: int) -> dict[str, Any]:
    """Holt eine URL und liefert immer ein Ergebnis-Dict (nie eine Exception)."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Encoding": "gzip",
            "Accept-Language": "ms-MY,ms;q=0.9,en;q=0.8",
        },
    )
    out: dict[str, Any] = {"url": url}
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read(3_000_000)
            if resp.headers.get("Content-Encoding") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except OSError:
                    pass
            out["status"] = resp.status
            out["content_type"] = resp.headers.get("Content-Type", "")
            out["final_url"] = resp.geturl()
            out["bytes"] = len(raw)
            out["text"] = raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        out["status"] = exc.code
        out["content_type"] = exc.headers.get("Content-Type", "") if exc.headers else ""
        out["error"] = f"HTTP {exc.code} {exc.reason}"
    except Exception as exc:  # URLError, ssl, timeout, proxy-403 ...
        out["status"] = None
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def looks_like_json(result: dict[str, Any]) -> tuple[bool, Any]:
    text = result.get("text")
    if not text:
        return False, None
    stripped = text.lstrip()
    if not stripped.startswith(("{", "[")):
        return False, None
    try:
        return True, json.loads(text)
    except json.JSONDecodeError:
        return False, None


def summarize_json(payload: Any) -> dict[str, Any]:
    """Kurzprofil der JSON-Struktur, damit man das Schema sofort sieht."""
    if isinstance(payload, list):
        first = payload[0] if payload else None
        return {
            "type": "array",
            "length": len(payload),
            "first_item_keys": sorted(first)[:40] if isinstance(first, dict) else None,
            "sample": first if not isinstance(first, (dict, list)) else None,
        }
    if isinstance(payload, dict):
        return {"type": "object", "keys": sorted(payload)[:40]}
    return {"type": type(payload).__name__}


def collect_script_urls(html: str, base_url: str) -> list[str]:
    urls = []
    for match in re.finditer(r"""<script[^>]+src=["']([^"']+)["']""", html, re.I):
        urls.append(urllib.parse.urljoin(base_url, match.group(1)))
    return urls


def extract_candidates(text: str, base_url: str) -> set[str]:
    found: set[str] = set()
    for pattern in ENDPOINT_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(1).strip()
            if not raw or raw.startswith(("data:", "mailto:", "javascript:", "#")):
                continue
            if any(raw.endswith(ext) for ext in (".js", ".css", ".png", ".jpg", ".svg", ".woff", ".woff2", ".ico")):
                continue
            absolute = urllib.parse.urljoin(base_url, raw)
            if absolute.startswith("http"):
                found.add(absolute)
    return found


def probe(timeout: int, insecure: bool, include_fallbacks: bool) -> dict[str, Any]:
    opener = build_opener(insecure)
    report: dict[str, Any] = {
        "seed_pages": [],
        "bundles_scanned": [],
        "candidate_endpoints": [],
        "json_endpoints": [],
        "network_blocked": False,
    }
    candidates: set[str] = set()
    bundles: list[str] = []

    print("== 1. Einstiegsseiten pruefen")
    reachable = 0
    for page in SEED_PAGES:
        res = fetch(opener, page, timeout)
        status = res.get("status")
        print(f"  {status if status is not None else 'ERR':>5}  {page}  {res.get('error', '')}")
        report["seed_pages"].append({k: v for k, v in res.items() if k != "text"})
        if not res.get("text"):
            continue
        reachable += 1
        html = res["text"]
        base = res.get("final_url", page)
        candidates |= extract_candidates(html, base)
        for src in collect_script_urls(html, base):
            if src not in bundles:
                bundles.append(src)

    if reachable == 0:
        report["network_blocked"] = True
        print(
            "\n  !! Keine einzige FAMA-Seite erreichbar.\n"
            "     Das ist mit hoher Wahrscheinlichkeit eine Netzwerk-/Proxy-Sperre,\n"
            "     KEINE Aussage darueber, ob FAMA eine API hat.\n"
            "     Skript in einem Netz ohne Egress-Filter erneut ausfuehren."
        )
        return report

    print(f"\n== 2. JS-Bundles scannen ({min(len(bundles), MAX_BUNDLES)} von {len(bundles)})")
    for src in bundles[:MAX_BUNDLES]:
        res = fetch(opener, src, timeout)
        report["bundles_scanned"].append({"url": src, "status": res.get("status"), "bytes": res.get("bytes")})
        if res.get("text"):
            new = extract_candidates(res["text"], src)
            if new:
                print(f"  +{len(new):>3} Kandidaten aus {src.rsplit('/', 1)[-1]}")
            candidates |= new

    if include_fallbacks:
        for page in SEED_PAGES:
            parts = urllib.parse.urlsplit(page)
            root = f"{parts.scheme}://{parts.netloc}"
            for path in FALLBACK_PATHS:
                candidates.add(root + path)

    ordered = sorted(candidates)[:MAX_CANDIDATES]
    report["candidate_endpoints"] = ordered
    print(f"\n== 3. {len(ordered)} Kandidaten testen")

    for url in ordered:
        res = fetch(opener, url, timeout)
        is_json, payload = looks_like_json(res)
        if is_json:
            entry = {
                "url": url,
                "status": res.get("status"),
                "content_type": res.get("content_type"),
                "bytes": res.get("bytes"),
                "schema": summarize_json(payload),
            }
            report["json_endpoints"].append(entry)
            print(f"  JSON  {res.get('status')}  {url}")
            print(f"        -> {json.dumps(entry['schema'], ensure_ascii=False)[:300]}")
        elif res.get("status") == 200:
            print(f"  200   (kein JSON)  {url}")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="fama_probe_report.json", help="Pfad fuer den JSON-Report")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout pro Request in Sekunden")
    parser.add_argument("--insecure", action="store_true", help="TLS-Verifikation abschalten (nur bei kaputten Gov-Zertifikaten)")
    parser.add_argument("--no-fallbacks", action="store_true", help="Keine generischen Pfade wie /api, /swagger.json mittesten")
    args = parser.parse_args()

    report = probe(args.timeout, args.insecure, include_fallbacks=not args.no_fallbacks)

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print(f"\n== Report: {args.out}")
    if report["network_blocked"]:
        print("Ergebnis: unentschieden - Netzwerk blockiert.")
        return 2
    if report["json_endpoints"]:
        print(f"Ergebnis: {len(report['json_endpoints'])} JSON-Endpunkt(e) gefunden -> automatischer Abruf moeglich.")
        return 0
    print("Ergebnis: kein offener JSON-Endpunkt gefunden. Naechster Schritt: HTML-Scraping oder Datenantrag bei FAMA.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
