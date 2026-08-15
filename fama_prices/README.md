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

### Was die Messläufe ergeben haben (Stand Runde 2)

Aufbau des Portals, aus den Snapshots rekonstruiert:

| URL | Technik | Rolle |
|---|---|---|
| `ami.fama.gov.my/` | Next.js | reine Landingpage: Werbetext + „Log Masuk mengikut jenis pengguna". **Keine Preisdaten.** |
| `ami.fama.gov.my/awam` | Quasar/Vue SPA | „awam" = öffentlich |
| `ami.fama.gov.my/web-awam` | Quasar/Vue SPA | öffentlich, mit Excel-Export (`xlsx.full.min.js`) |
| `ami.fama.gov.my/web` | Quasar/Vue SPA | „FAMA – Maklumat Harga", mit Excel-Export |
| `ami.fama.gov.my/mobile` | Quasar/Vue SPA | Mobilvariante |

Alle vier Apps laden `https://ami.fama.gov.my/kc/js/keycloak.js` – der Zugang läuft also
über **Keycloak** (OpenID Connect). Die Daten kommen damit mit hoher Wahrscheinlichkeit aus
einer REST-API, die ein Token erwartet.

Wichtige Korrektur zu Runde 2: Die Meldung „Preisdaten stecken im HTML/RSC" war ein
Fehlalarm – die Treffer auf „harga/komoditi" stammten aus dem Meta-Description-Text der
Landingpage, nicht aus echten Daten. Runde 2 hatte die SPA-Bundles außerdem nie gelesen,
weil deren relative Script-Pfade gegen `/awam` statt `/awam/` aufgelöst wurden.
`probe_fama3.py` behebt beides.

### Die AMI-API (aus den App-Bundles rekonstruiert, Runde 3)

Die Suche war erfolgreich. Die AMI-Apps sprechen mit einer generischen
Datenbank-REST-API im Stil von *php-crud-api*:

```
Basis        https://ami.fama.gov.my/api/gen/       (zweite Instanz: /api2/gen/)
Aufruf       GET <basis><tabelle>?filter=<spalte>,<operator>,'<wert>'
Weitere      /api3/ , /api/ldap/ , /api/file/ , /api/generic/file/ , /api/spec/bulk/
Auth-API     <basis>auth/menu , auth/permission , auth/report-permission  (?email=&type=)
```

Anmeldung über **Keycloak** unter `https://ami.fama.gov.my/kc/`:

| App | Realm | Client |
|---|---|---|
| `/web` | `FAMA` | `webadmin` |
| `/awam` | `AMI` | `respondent` |
| `/mobile` | `FAMA` | `mobilefama` |

Token-Endpunkt: `https://ami.fama.gov.my/kc/realms/<REALM>/protocol/openid-connect/token`.
Beide Realms unterstützen laut OIDC-Discovery u. a. `password` (Direct Access Grant),
`authorization_code` und `client_credentials`.

Die wichtigsten Tabellen aus dem Bundle:

| Zweck | Tabelle |
|---|---|
| **Preise (Kerndatensatz)** | `harga` |
| Preise aufbereitet täglich / wöchentlich | `harga2h` / `harga2m` |
| Altbestand | `harga_old` |
| Monatsmittel / -median | `mv_mon_avg` / `mv_mon_med` |
| Warenarten, Varietäten, Gruppen | `refcommodity`, `refcommodityvariety`, `refcommoditygroup`, `refcommoditycategory` |
| Güteklassen, Einheiten, Preisebenen | `refgrade`, `refunit`, `reflevel`, `vclevel` |
| Bundesstaaten, Distrikte | `vstate`, `vdistrict`, `mvdaerah` |
| Großmärkte | `f_vpasarborong` |
| Auswertungen | `smp.laporansegar`, `smp.laporanperingkat`, `smp.laporannegeri`, `smp.laporankategori` |

Feldwerte in `harga`: `commoditytype` = `D` (harian/täglich) oder `W` (mingguan/wöchentlich);
`status` = `Hantar` (eingereicht), `Disemak` (geprüft), `Ditolak` (abgelehnt);
weitere Spalten u. a. `pricedate`, `commoditylevel` (Ladang/Borong/Runcit),
`commodityvarietybm`, `gradecd`/`gradebm`, `sourceid`, `adminid`.

Die `baseURL: "https://api.example.com"` im Bundle ist ein ungenutzter Quasar-Standardwert,
keine echte Adresse – die realen Basis-URLs stehen im Modul `32554`.

### Ergebnis: die Preisdaten sind ohne Anmeldung abrufbar

Am laufenden System gemessen – **`harga` und alle Referenztabellen antworten anonym**,
es wird kein Token benötigt:

```
GET https://ami.fama.gov.my/api/gen/harga?filter=pricedate,eq,'2026-08-14'&limit=1000&offset=0
```

`harga` liefert rund 50 Spalten, darunter `price`, `oprice`, `pricedate`, `commoditylevel`,
`sublevel`, `commodityvarietybm`, `commoditygrade`, `commodityunit`, `negeri`, `daerah`,
`statecd`, `districtcd`, `institutionbm`, `instaddressnm`, `sourceid`, `supply`,
`average14`, `commodityfloorprice`, `commodityceilingprice`, `status`, `systemdate`.

Ebenfalls offen: `refcommodity`, `refgrade`, `refunit`, `refcommodityvariety`,
`refcommoditycategory`, `reflevel` (47 Zeilen), `vstate`, `vdistrict`, `f_vpasarborong`,
`harga2h`, `harga2m`, `mv_mon_avg` (`avg`, `bulan`, `tahun`, `negeri`, `commoditylevel`)
und `smp.laporansegar` (`averageprice`, `samplecount`, `gred`, `kategori`).

**Blättern:** Der Server akzeptiert `?limit=N` und `?offset=M`; `size`, `take`, `top`,
`per_page`, `page=n,size` werden stillschweigend ignoriert. Ohne `limit` versucht er bei
großen Tabellen die vollständige Ausgabe und bricht mit **502 Bad Gateway** ab – genau das
waren die anfänglichen 502er, nicht ein Berechtigungsproblem.

**Zum Login:** Ein Konto, das per *Sign in with Google* angelegt wurde, hat in Keycloak
kein eigenes Passwort – die Prüfung läuft bei Google. Der Direct Access Grant kann dafür
prinzipiell nicht funktionieren (`invalid_grant`). Für die Preisdaten ist das
bedeutungslos, da sie offen sind.

**Weitere Details:**

- Ein Teil der API ist **ohne jede Anmeldung** offen: `reflevel` und `vstate` liefern
  direkt Daten (`reflevel` u. a. mit `levelcd`, `levelbm`, `levelen`, `levelactive`,
  `parentlevelcd`, `order`, `icon`).
- Die Engine ist **nicht** php-crud-api: die App setzt Filterwerte in Anführungszeichen
  (`filter=adminid,eq,'X'`), was php-crud-api nicht tut. Entsprechend ist auch dessen
  Blätter-Syntax `?page=n,size` falsch – sie erzeugt am Server einen **502 Bad Gateway**.
  `fama_ami_client.py apitest` ermittelt die tatsächlich akzeptierte Begrenzung, indem es
  gängige Varianten (`limit`, `offset`, `size`, `page&limit` …) gegen die offene Tabelle
  `reflevel` durchprobiert und prüft, ob die Zeilenzahl wirklich sinkt.
- Keycloak antwortet auf den Passwort-Login mit `invalid_grant` („Invalid user
  credentials"), **nicht** mit `unauthorized_client`. Der Direct Access Grant ist also
  aktiv – scheitert es, liegt es an Benutzername/Passwort, nicht am Zugangsweg.

### Zugriff: `fama_ami_client.py`

```bash
python3 fama_ami_client.py probe                      # ohne Login: was ist offen?
python3 fama_ami_client.py refs   --user <email>      # Stammdaten als CSV
python3 fama_ami_client.py prices --user <email> --from 2026-08-01 --to 2026-08-14 --type D --out harga.csv
python3 fama_ami_client.py table  --user <email> --name refcommodity
```

Das Passwort wird per `getpass` abgefragt oder aus `FAMA_PASSWORD` gelesen, nie gespeichert
und ausschließlich an den Keycloak-Server geschickt. Findet das Skript den falschen Realm,
lässt er sich mit `--realm AMI --client respondent` erzwingen.

## NuMIS: täglicher Import in Supabase

Zielprojekt **NuMIS** (`otumcdmymenwiliwzrhj`, Schema `numis`). Die Quelle `FAMA_AMI` war
dort bereits angelegt; `crops`, `markets`, `raw_source_records` und `price_observations`
waren leer.

### Was am Schema ergänzt wurde

```sql
-- Wiederholbarkeit (ON CONFLICT-Ziele)
raw_source_records_source_external_uidx  (source_id, external_record_id)  UNIQUE
price_observations_source_record_uidx    (source_id, source_record_id)    UNIQUE
-- Abfrage-Indizes für die spätere PWA
price_observations (observation_date, crop_id) / (source_id, observation_date) / (market_id, observation_date)
raw_source_records (source_id, observed_at)
-- Lauf-Protokoll
numis.ingest_runs (source_id, target_date, status, raw_rows, observation_rows, …)
```

`ingest_runs` war nicht ausdrücklich bestellt, ist aber die Voraussetzung fürs Nachladen:
Ohne Protokoll ließe sich ein Tag, an dem es **wirklich keine Daten gab** (Feiertag), nicht
von einem Tag unterscheiden, der **nie geholt wurde** – er würde endlos erneut abgefragt.
Status `EMPTY` löst das.

### Serverseitige Import-Logik (Postgres-Funktionen)

| Funktion | Zweck |
|---|---|
| `public.numis_ingest_fama_batch(date, jsonb)` | Legt fehlende `crops`/`markets` an, sichert Rohzeilen, schreibt Beobachtungen – alles per Upsert |
| `public.numis_ingest_fama_finish(date, int, int, text)` | Schließt den Tag ab (`OK` / `EMPTY` / `ERROR`) |
| `public.numis_missing_days(from, to)` | Liefert die noch offenen Tage – steuert das Nachladen |

Alle drei sind `SECURITY DEFINER` und **nur für `service_role` ausführbar**; für `anon`
und `authenticated` wurde `EXECUTE` entzogen. Sie liegen in `public`, weil das Schema
`numis` nicht über die Data-API exponiert ist.

Feldzuordnung, Statusabbildung (`Disemak`/`Disahkan` → `VALIDATED`, `Ditolak` → `REJECTED`,
sonst `RAW`) und Schlüsselbildung (`fama_crop_code`, `fama_market_code`) stecken vollständig
in den Funktionen – der Client bleibt dumm und ist damit leicht austauschbar.

### Loader benutzen

```bash
set NUMIS_SERVICE_KEY=<service-role-key>     # Windows, einmalig: setx …
python fama_to_numis.py                      # letzte 7 Tage prüfen und nachholen
python fama_to_numis.py --days 30
python fama_to_numis.py --from 2026-07-01 --to 2026-07-31
python fama_to_numis.py --days 7 --dry-run   # nur abrufen, nichts schreiben
```

Der Loader fragt zuerst `numis_missing_days` und holt **nur** die offenen Tage. Ein Tag gilt
erst als erledigt, wenn `finish` gelaufen ist – bricht ein Stapel ab, bleibt der Tag offen
und wird beim nächsten Lauf vollständig wiederholt. Da alles Upserts sind, ist das gefahrlos.

### Täglich laufen lassen

Windows: `run_fama_import.bat` (schreibt `fama_import.log`), einmalig einplanen mit

```
schtasks /create /tn "NuMIS FAMA Import" /tr "C:\Users\carst\Downloads\run_fama_import.bat" /sc daily /st 07:30 /f
```

Mac/Linux: `30 7 * * * cd /pfad/zu/fama_prices && NUMIS_SERVICE_KEY=… python3 fama_to_numis.py --days 7 >> fama_import.log 2>&1`

Einmal täglich genügt – FAMA aktualisiert die Tagespreise nicht häufiger.

### Skripte im Überblick

`probe_fama.py` (Runde 1) macht die Grunderkennung:

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

`probe_fama3.py` (Runde 3) ist der eigentliche Schritt: Es lädt die vier Quasar-Apps mit
korrekt aufgelösten Bundle-Pfaden und sucht darin nach der axios-`baseURL`, konkreten
Endpunkt-Pfaden, den Vue-Router-Routen und der Keycloak-Konfiguration (`realm`,
`clientId`). Relative API-Pfade werden an die gefundene API-Basis gehängt, nicht an die
Seiten-URL. Anschließend fragt es die Keycloak-Discovery ab
(`/kc/realms/<realm>/.well-known/openid-configuration`), um zu sehen, welche Grant-Types
möglich sind.

```bash
python3 probe_fama3.py
```

Ein Ergebnis mit **HTTP 401/403 ist ein Erfolg**, kein Fehlschlag: Es beweist, dass die API
existiert und nur ein Token fehlt. Die App-Bundles landen in `fama_bundles/`.

Findet ein Skript Endpunkte, steht im Report direkt das Feld-Schema – daraus ist ein
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
