# FAMA Malaysia – Preisdaten automatisiert abrufen

Recherche-Stand: 15.08.2026

## Kurzfassung

FAMA veröffentlicht **keine dokumentierte öffentliche API** und ist auch **nicht** im
nationalen Open-Data-Katalog (data.gov.my / OpenDOSM) gelistet. Ein automatischer Abruf
ist trotzdem realistisch – über drei Wege, in dieser Reihenfolge:

| Weg | Deckt ab | Aufwand | Rechtlich |
|---|---|---|---|
| 1. AMI-Portal-Endpunkte selbst entdecken (`probe_fama.py`) | Ladang / Borong / Runcit, täglich, 262 Sorten | niedrig, aber unbestätigt | Graubereich, ToS prüfen |
| 2. PriceCatcher über data.gov.my (`fetch_pricecatcher.py`) | nur Runcit (Einzelhandel), ~750 Artikel | sehr niedrig, dokumentiert | offene Lizenz |
| 3. Offizieller Datenantrag bei FAMA | alles, inkl. Historie | Wochen | sauber |

**Wichtig:** Aus der Session, in der dieses Repo erstellt wurde, waren *alle*
`*.gov.my`-Hosts durch die Netzwerk-Policy gesperrt (403 beim CONNECT-Tunnel). Ich konnte
die AMI-Endpunkte deshalb **nicht selbst live testen**. Genau dafür ist `probe_fama.py` da:
Du führst es aus einem normalen Netz aus und bekommst eine belastbare Antwort statt einer
Vermutung.

## 1. AMI-Portal (`ami.fama.gov.my`)

Das *Agri Market Insight*-System ist FAMAs Preisplattform. Laut FAMA werden Preise auf
drei Ebenen täglich von FAMA-Beamten im ganzen Land erfasst:

- **Ladang** – Ab-Hof / Erzeugerpreis
- **Borong** – Großhandel
- **Runcit** – Einzelhandel

Abdeckung: 262 Sorten (Obst, Gemüse, Vieh, Fischerei). Das Portal erzeugt automatisch
Wochen-, Monats- und Jahresberichte mit Trendanalysen und zeigt interaktive Charts und
Karten – **interaktive Frontends dieser Art laden ihre Daten praktisch immer über
JSON-Endpunkte nach**. Das ist der Ansatzpunkt.

`probe_fama.py` macht genau das systematisch:

```bash
python3 probe_fama.py                 # Standardlauf, schreibt fama_probe_report.json
python3 probe_fama.py --timeout 45    # bei langsamer Gov-Infrastruktur
python3 probe_fama.py --insecure      # falls das TLS-Zertifikat kaputt ist
```

Ablauf: Erreichbarkeit prüfen → HTML der Preis-Seiten laden → alle JS-Bundles einsammeln →
darin nach `fetch(...)`, `axios.get(...)`, `/api/...`-Strings suchen → jeden Fund aufrufen →
prüfen, ob echtes JSON zurückkommt, inkl. Schema-Vorschau.

Exit-Codes: `0` = JSON-Endpunkte gefunden, `1` = keine gefunden (dann HTML-Scraping oder
Weg 3), `2` = Netzwerk blockiert, Ergebnis unentschieden.

Findet das Skript Endpunkte, steht im Report direkt das Feld-Schema – daraus ist ein
Tagesabruf dann eine Sache von wenigen Zeilen.

**Vor dem Dauerbetrieb:** Nutzungsbedingungen und `robots.txt` von FAMA prüfen und
freundlich crawlen (1 Request/Sekunde, einmal täglich reicht bei Tagesdaten).

## 2. PriceCatcher über data.gov.my – der sichere Weg

Das ist der einzige Weg, der offiziell dokumentiert und ohne Absprache nutzbar ist.
Achtung: Das sind **KPDN-Daten, nicht FAMA** – erhoben mit der PriceCatcher-App in rund
3.800 Verkaufsstellen über alle 16 Bundesstaaten, ~750 Artikel.

Bereitstellung als Parquet-Datei pro Monat, **nicht** über die OpenAPI – laut
data.gov.my ist der Datensatz für API-Zugriff zu groß (über eine Million Preissätze pro Monat):

```
https://storage.data.gov.my/pricecatcher/pricecatcher_YYYY-MM.parquet
https://storage.data.gov.my/pricecatcher/lookup_item.parquet
https://storage.data.gov.my/pricecatcher/lookup_premise.parquet
```

```bash
pip install pandas pyarrow
python3 fetch_pricecatcher.py --months 2026-06 2026-07
python3 fetch_pricecatcher.py --months 2026-07 --state Selangor --item-contains bawang
```

Der entscheidende Unterschied zu FAMA: **PriceCatcher hat nur Endkundenpreise.** Wenn du
Erzeuger- oder Großhandelspreise brauchst (also Handelsspannen, Ab-Hof-Kalkulation), reicht
das nicht – dann führt kein Weg an FAMA vorbei.

Für andere malaysische Datensätze gibt es sehr wohl eine echte OpenAPI:
`https://api.data.gov.my/data-catalogue?id=<dataset_id>` mit `filter`, `include`/`exclude`
und `limit`. Dokumentation: <https://developer.data.gov.my/>.

## 3. Offizieller Zugang bei FAMA

Für belastbaren, dauerhaften Zugriff (inkl. Historie und ohne Scraping-Risiko) ist das der
richtige Weg. FAMA gibt Marktinformationsberichte laut eigener Website kostenlos ab; der
Kontakt für Datenabgabe ist die **Unit Pengurusan & Penyebaran Data, Bahagian Maklumat
Pasaran**, Tel. 03-6136 2020 App. 2141 / 2153.

Sinnvoll im Anschreiben: Zweck, benötigte Warenarten, Preisebenen (Ladang/Borong/Runcit),
Zeitraum, gewünschtes Format (CSV/JSON statt PDF) und explizit die Frage nach einem
maschinellen Abrufweg. Behördenintern läuft so etwas in Malaysia oft über den
Datenaustausch **MyGDX**.

## 4. Drittanbieter (nur als Notnagel)

Es existiert ein MCP-Server `manamurah` (MIT-Lizenz), der beide Quellen bereits aggregiert:
PriceCatcher wöchentlich plus FAMA-Tagespreise auf allen drei Preisebenen für ~46 Artikel,
erreichbar über `https://mcp.manamurah.com/mcp` (JSON-RPC 2.0). Praktisch zum schnellen
Gegenchecken, ob FAMA-Daten überhaupt maschinell zu bekommen sind – für Produktion aber
eine Abhängigkeit von einem privaten Proxy ohne Verfügbarkeitszusage.

Repo: <https://github.com/manamurah/mcp-server>

## Empfehlung

1. `probe_fama.py` aus einem unbeschränkten Netz laufen lassen – das entscheidet in
   Minuten, ob Weg 1 trägt.
2. Parallel den FAMA-Datenantrag anstoßen (Weg 3), weil das die einzige Variante ist,
   die langfristig nicht bricht.
3. `fetch_pricecatcher.py` sofort nutzen, wenn Einzelhandelspreise für den Anwendungsfall
   ausreichen.

## Quellen

- [Portal AMI](https://ami.fama.gov.my/)
- [Maklumat Pasaran – FAMA](https://www.fama.gov.my/maklumat-pasaran)
- [Harga Pasaran Terkini – FAMA](https://www.fama.gov.my/harga-pasaran-terkini)
- [Laporan Dan Analisis Maklumat Pasaran – FAMA](https://www.fama.gov.my/laporan-dan-analisis-maklumat-pasaran)
- [PriceCatcher: Transactional Records – data.gov.my](https://data.gov.my/data-catalogue/pricecatcher)
- [Malaysia's Official Open API – Data Catalogue](https://developer.data.gov.my/static-api/data-catalogue)
- [Request Query – developer.data.gov.my](https://developer.data.gov.my/request-query)
- [manamurah/mcp-server](https://github.com/manamurah/mcp-server)
