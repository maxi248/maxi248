#!/usr/bin/env python3
"""
probe_fama2.py - Runde 2 der AMI-Endpunkt-Suche.

Runde 1 (probe_fama.py) hat gezeigt:
  - ami.fama.gov.my ist eine Next.js-App (Bundle "page-*.js")
  - es gibt Unterseiten /awam, /mobile, /web, /web-awam (alle HTTP 200)
  - kein JSON unter den klassischen /api-Pfaden

Dieses Skript sucht deshalb dort, wo Next.js seine Daten wirklich ablegt:

  A) Unterseiten als Einstieg nehmen (nicht nur die Startseite) und ALLE
     ihre JS-Bundles scannen.
  B) Im HTML nach eingebetteten Daten suchen:
       - __NEXT_DATA__      (Next.js Pages Router)
       - self.__next_f.push (Next.js App Router / RSC-Payload)
     Steckt dort schon "harga"/"komoditi" drin, brauchen wir gar keine API.
  C) HTML-Tabellen zaehlen - server-gerenderte Preistabellen waeren der
     einfachste Fall ueberhaupt.
  D) Deutlich breitere Endpunkt-Suche: beliebige Hosts (die API kann auf
     einer ganz anderen Domain liegen), datenverdaechtige Pfade,
     /_next/data/<buildId>/*.json.
  E) Alle im JS erwaehnten Hostnamen auflisten - falls FAMA ein separates
     Backend betreibt, faellt es hier auf.

Alle geladenen Seiten werden als Datei gespeichert, damit man sie
weiterreichen kann.

    python3 probe_fama2.py
    python3 probe_fama2.py --timeout 45

Nur Standardbibliothek.
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

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

SEEDS = [
    "https://ami.fama.gov.my/",
    "https://ami.fama.gov.my/awam",
    "https://ami.fama.gov.my/web-awam",
    "https://ami.fama.gov.my/web",
    "https://ami.fama.gov.my/mobile",
]

# Woerter, die auf Preisdaten hindeuten (Malaiisch + Englisch).
DATA_WORDS = [
    "harga", "komoditi", "runcit", "borong", "ladang", "pasar", "gred",
    "price", "commodity", "market", "item", "barang", "sayur", "buah",
]
DATA_WORD_RE = re.compile("|".join(DATA_WORDS), re.I)

ASSET_EXT = (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
             ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".webp", ".map")

NOISE_HOSTS = re.compile(
    r"(google|gstatic|googleapis|jquery|bootstrap|cloudflare|jsdelivr|unpkg"
    r"|w3\.org|schema\.org|facebook|twitter|youtube|github|npmjs|vercel"
    r"|nextjs\.org|react|mozilla|example\.com)", re.I)

# Breitere Endpunkt-Muster als in Runde 1.
PATTERNS = [
    # absolute URLs auf beliebigen Hosts
    re.compile(r"""["'`](https?://[a-zA-Z0-9.\-]+(?::\d+)?/[^"'`\s\\]{0,200})["'`]"""),
    # Pfade mit datenverdaechtigen Woertern
    re.compile(r"""["'`](/[^"'`\s\\]*(?:""" + "|".join(DATA_WORDS) +
               r"""|api|rest|data|list|senarai|laporan|carta|graf)[^"'`\s\\]{0,160})["'`]""", re.I),
    # explizite Aufrufe
    re.compile(r"""(?:fetch|axios(?:\.\w+)?|\.get|\.post|useSWR|useQuery)\s*\(\s*["'`]([^"'`]{2,200})["'`]"""),
    # Template-Basis-URLs, z.B.  baseURL: "https://..."
    re.compile(r"""(?:baseURL|BASE_URL|apiUrl|API_URL|endpoint|NEXT_PUBLIC_\w*URL)\s*[:=]\s*["'`]([^"'`]{4,200})["'`]"""),
    re.compile(r"""["'`](/_next/data/[^"'`\s\\]+\.json)["'`]"""),
]

MAX_BUNDLES = 120
MAX_CANDIDATES = 250
SNAPDIR = "fama_snapshots"


def build_opener(insecure: bool) -> urllib.request.OpenerDirector:
    ctx = ssl.create_default_context()
    if insecure:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))


def fetch(opener, url: str, timeout: int, referer: str | None = None) -> dict[str, Any]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "gzip",
        "Accept-Language": "ms-MY,ms;q=0.9,en;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    out: dict[str, Any] = {"url": url}
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=timeout) as resp:
            raw = resp.read(8_000_000)
            if resp.headers.get("Content-Encoding") == "gzip":
                try:
                    raw = gzip.decompress(raw)
                except OSError:
                    pass
            out.update(status=resp.status,
                       content_type=resp.headers.get("Content-Type", ""),
                       final_url=resp.geturl(),
                       bytes=len(raw),
                       text=raw.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        out.update(status=exc.code, error=f"HTTP {exc.code} {exc.reason}")
    except Exception as exc:
        out.update(status=None, error=f"{type(exc).__name__}: {exc}")
    return out


def save_snapshot(name: str, text: str) -> str:
    os.makedirs(SNAPDIR, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "page"
    path = os.path.join(SNAPDIR, safe)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def find_embedded_data(html: str) -> dict[str, Any]:
    """Sucht Next.js-Daten, die direkt in der Seite stecken."""
    info: dict[str, Any] = {}

    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        info["next_data_bytes"] = len(m.group(1))
        try:
            payload = json.loads(m.group(1))
            info["next_data_keys"] = sorted(payload)[:30]
            props = payload.get("props", {}).get("pageProps", {})
            if isinstance(props, dict):
                info["page_props_keys"] = sorted(props)[:40]
            info["next_data_has_price_words"] = bool(DATA_WORD_RE.search(m.group(1)))
        except json.JSONDecodeError:
            info["next_data_parse_error"] = True

    flight = re.findall(r'self\.__next_f\.push\(\[\d+,\s*"((?:[^"\\]|\\.)*)"\]\)', html)
    if flight:
        joined = "".join(flight)
        try:
            joined = joined.encode().decode("unicode_escape")
        except UnicodeDecodeError:
            pass
        info["rsc_chunks"] = len(flight)
        info["rsc_bytes"] = len(joined)
        hits = Counter(w.lower() for w in DATA_WORD_RE.findall(joined))
        info["rsc_price_words"] = dict(hits.most_common(10))
        if hits:
            idx = DATA_WORD_RE.search(joined).start()
            info["rsc_sample"] = joined[max(0, idx - 200): idx + 600]
        info["_rsc_full"] = joined
    return info


def table_stats(html: str) -> dict[str, int]:
    return {
        "tables": len(re.findall(r"<table", html, re.I)),
        "rows": len(re.findall(r"<tr", html, re.I)),
        "cells": len(re.findall(r"<td", html, re.I)),
    }


def script_urls(html: str, base: str) -> list[str]:
    return [urllib.parse.urljoin(base, m.group(1))
            for m in re.finditer(r"""<script[^>]+src=["']([^"']+)["']""", html, re.I)]


def extract_candidates(text: str, base: str) -> set[str]:
    found: set[str] = set()
    for pat in PATTERNS:
        for m in pat.finditer(text):
            raw = m.group(1).strip()
            if not raw or raw.startswith(("data:", "mailto:", "javascript:", "#", "//#")):
                continue
            low = raw.lower()
            if any(low.endswith(e) for e in ASSET_EXT):
                continue
            if NOISE_HOSTS.search(low):
                continue
            absolute = urllib.parse.urljoin(base, raw)
            if absolute.startswith("http"):
                found.add(absolute)
    return found


def extract_hosts(text: str) -> Counter:
    hosts = Counter()
    for m in re.finditer(r"https?://([a-zA-Z0-9.\-]+)", text):
        host = m.group(1).lower()
        if not NOISE_HOSTS.search(host):
            hosts[host] += 1
    return hosts


def looks_like_json(res: dict[str, Any]) -> tuple[bool, Any]:
    text = res.get("text")
    if not text or not text.lstrip().startswith(("{", "[")):
        return False, None
    try:
        return True, json.loads(text)
    except json.JSONDecodeError:
        return False, None


def summarize(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        first = payload[0] if payload else None
        return {"type": "array", "length": len(payload),
                "first_item_keys": sorted(first)[:40] if isinstance(first, dict) else None}
    if isinstance(payload, dict):
        return {"type": "object", "keys": sorted(payload)[:40]}
    return {"type": type(payload).__name__}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="fama_probe2_report.json")
    ap.add_argument("--timeout", type=int, default=40)
    ap.add_argument("--insecure", action="store_true")
    args = ap.parse_args()

    opener = build_opener(args.insecure)
    report: dict[str, Any] = {"pages": [], "hosts": {}, "json_endpoints": [],
                              "candidates_tested": 0, "embedded_data_hits": []}
    candidates: set[str] = set()
    bundles: list[str] = []
    hosts: Counter = Counter()

    print("== 1. AMI-Unterseiten laden und im HTML nach eingebetteten Daten suchen\n")
    for url in SEEDS:
        res = fetch(opener, url, args.timeout)
        entry: dict[str, Any] = {"url": url, "status": res.get("status"),
                                 "bytes": res.get("bytes"), "error": res.get("error")}
        print(f"  {str(res.get('status') or 'ERR'):>5}  {url}")
        html = res.get("text")
        if not html:
            report["pages"].append(entry)
            continue

        slug = urllib.parse.urlsplit(url).path.strip("/").replace("/", "_") or "root"
        entry["snapshot"] = save_snapshot(slug + ".html", html)
        entry["tables"] = table_stats(html)
        embedded = find_embedded_data(html)
        rsc_full = embedded.pop("_rsc_full", None)
        entry["embedded"] = embedded

        if entry["tables"]["rows"] > 3:
            print(f"         HTML-Tabelle: {entry['tables']['rows']} Zeilen, {entry['tables']['cells']} Zellen")
        if embedded.get("rsc_price_words"):
            print(f"         RSC-Daten in der Seite: {embedded['rsc_bytes']:,} Zeichen, "
                  f"Treffer {embedded['rsc_price_words']}")
            report["embedded_data_hits"].append(url)
            if rsc_full:
                p = save_snapshot((urllib.parse.urlsplit(url).path.strip('/') or 'root') + ".rsc.txt", rsc_full)
                print(f"         -> gespeichert: {p}")
        if embedded.get("page_props_keys"):
            print(f"         __NEXT_DATA__ pageProps: {embedded['page_props_keys']}")
            report["embedded_data_hits"].append(url)

        report["pages"].append(entry)
        candidates |= extract_candidates(html, url)
        hosts += extract_hosts(html)
        for s in script_urls(html, url):
            if s not in bundles:
                bundles.append(s)

    if not bundles and not candidates:
        print("\n  !! Nichts geladen - Netzwerk pruefen.")
        return 2

    print(f"\n== 2. {min(len(bundles), MAX_BUNDLES)} JS-Bundles scannen")
    for src in bundles[:MAX_BUNDLES]:
        res = fetch(opener, src, args.timeout, referer=SEEDS[1])
        if not res.get("text"):
            continue
        new = extract_candidates(res["text"], src)
        hosts += extract_hosts(res["text"])
        if new:
            print(f"  +{len(new):>3} aus {src.rsplit('/', 1)[-1][:60]}")
        candidates |= new

    report["hosts"] = dict(hosts.most_common(40))
    print("\n== 3. Erwaehnte Hostnamen (moegliche Backends)")
    for host, n in hosts.most_common(20):
        print(f"  {n:>5}x  {host}")

    ordered = sorted(candidates)[:MAX_CANDIDATES]
    report["candidates_tested"] = len(ordered)
    print(f"\n== 4. {len(ordered)} Kandidaten auf JSON testen")
    for url in ordered:
        res = fetch(opener, url, args.timeout, referer=SEEDS[1])
        ok, payload = looks_like_json(res)
        if ok:
            entry = {"url": url, "status": res.get("status"),
                     "content_type": res.get("content_type"),
                     "bytes": res.get("bytes"), "schema": summarize(payload)}
            report["json_endpoints"].append(entry)
            print(f"  JSON  {res.get('status')}  {url}")
            print(f"        -> {json.dumps(entry['schema'], ensure_ascii=False)[:300]}")

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    print(f"\n== Report: {args.out}")
    print(f"== Seiten-Snapshots im Ordner: {SNAPDIR}/")
    if report["json_endpoints"]:
        print(f"Ergebnis: {len(report['json_endpoints'])} JSON-Endpunkt(e) -> automatischer Abruf moeglich.")
        return 0
    if report["embedded_data_hits"]:
        print("Ergebnis: keine offene API, ABER die Preisdaten stecken im HTML/RSC der Seite.")
        print("          -> Abruf ist trotzdem automatisierbar, siehe Snapshots.")
        return 0
    print("Ergebnis: weder API noch eingebettete Daten gefunden.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
