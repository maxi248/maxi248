# NuMIS – Übergabe an eine neue Sitzung

Dieses Dokument ist der Einstieg für eine Claude-Code-Sitzung, die auf
`Carsten-F/nusatani-prices` läuft und dort an der App weiterarbeitet.

**Warum es das gibt:** Sitzungen sind an einen GitHub-Account gebunden. Eine Sitzung bei
`Carsten-F` kommt nicht an `maxi248/maxi248` heran und umgekehrt. Die ausführliche
Dokumentation (`README.md`, ~670 Zeilen) liegt in `maxi248/maxi248` unter `fama_prices/`
und sollte zusammen mit dieser Datei ins neue Repo kopiert werden – sie ist das Gedächtnis
des Projekts und erklärt jede Entscheidung samt Messwerten.

---

## Wozu das Ganze

Grundlage für eine App, mit der Farmer in Kelantan Marktpreise abrufen, sie validieren und
eigene Preise melden können – die ihnen von FAMA oder vom Peraih (Zwischenhändler) geboten
werden. Die Preisdatenbank ist die erste Säule; Meldung und Validierung stehen noch aus.

## Was steht

**Datenquelle.** FAMA betreibt unter `ami.fama.gov.my` eine undokumentierte, generische
REST-Schnittstelle: `https://ami.fama.gov.my/api/gen/<tabelle>?filter=<spalte>,<op>,'<wert>'`.
Sie ist **ohne Anmeldung** abrufbar. Zwei Eigenheiten, die viel Zeit gekostet haben:

- `order`/`sort` gibt es nicht (HTTP 500), `offset`/`skip`/`page` allein werden stillschweigend
  **ignoriert** – wer sich darauf verlässt, bekommt 1.000 Zeilen pro Tag und merkt es nicht.
  Deshalb immer mit `limit` arbeiten; `page` funktioniert nur zusammen mit `limit`.
- Ohne `limit` versucht der Server die ganze Tabelle und antwortet mit 502.

**Loader.** `fama_to_numis.py` (in `maxi248/maxi248`, Ordner `fama_prices/`) holt Tag für
Tag, fragt vorher `numis_missing_days` und lädt Versäumtes selbst nach. Läuft täglich per
Aufgabenplanung auf Carstens Windows-Rechner. Er ist stabil und war zuletzt nicht Gegenstand
von Änderungen.

**Datenbank.** Supabase-Projekt `otumcdmymenwiliwzrhj`, Schema `numis`. Stand zuletzt:
283.404 Beobachtungen, 01.01.2025 bis 27.08.2026, 277 Kulturen, 479 Märkte, 16 Bundesstaaten.

**Seiten.** In `Carsten-F/nusatani-prices`, ausgeliefert über Vercel:

| Datei | Adresse | |
|---|---|---|
| `index.html` | `/` | Einstieg |
| `tani.html` | `/tani` | Farmer-App, installierbar (PWA) |
| `preise.html` | `/preise` | volle Abfrage für die Auswertung |
| `diagnose.html` | `/diagnose` | vierstufiger Selbsttest |

Englisch und Bahasa Melayu, kein Deutsch – die Seiten gehen an malaysische Tester.

---

## Die Regeln, die das Ganze zusammenhalten

**1. Der Client bleibt dumm.** Alle Logik steckt in Postgres-Funktionen. Die Seiten rufen
nur RPCs auf. Schema `numis` ist **nicht** über die Data-API exponiert; alles läuft über
`SECURITY DEFINER`-Funktionen in `public`.

Für `anon` freigegeben (nur lesen): `numis_client_check`, `numis_filter_options`,
`numis_price_search`, `numis_price_summary`, `numis_price_series`, `numis_farmer_options`,
`numis_farmer_overview`. Alles Schreibende ist `service_role`.

**2. Jede Fassung ist sperrbar.** Die Seiten tragen ein Token
(`numis-2026-08-r1-8f3ac21d`, Fassung `2026.08.r1`). `numis.assert_client(p_token)` steckt in
**jedem** RPC. Steht der Eintrag in `numis.client_releases` nicht auf `ACTIVE`, liefert die
Datenbank nichts – auch weitergegebenen Kopien nicht. Sperren:

```sql
update numis.client_releases set status = 'BLOCKED' where token = '…';
```

Deshalb speichert der Service Worker (`sw.js`) **nur die Hülle** und lässt jede Anfrage an
Supabase unangetastet durch. Würde er Antworten cachen, liefe eine gesperrte Fassung weiter.
Das bitte nicht "optimieren".

**3. `anon` hat 3 Sekunden.** Supabase setzt für `anon` ein `statement_timeout` von 3 s
(`authenticated`: 8 s). Wird es gerissen, kommt `HTTP 500 / 57014` und im Browser steht
"Connection failed". Das ist schon einmal passiert: `numis_filter_options` brauchte 10,3 s.

Konsequenz für alles Neue: **keine korrelierte Unterabfrage pro Katalogzeile** und
**kein `DISTINCT` über `price_observations`**. Die belegten Auswahlwerte stehen in
`numis.filter_keys` (783 Zeilen), fortgeschrieben von `numis.touch_filter_keys(von, bis)`,
das `numis_ingest_fama_finish()` für jeden Importtag aufruft (24 ms). Nach größeren
Löschungen einmal `select numis.rebuild_filter_keys();`.

Aktuelle Laufzeiten als `anon`: `filter_options` 111 ms, `price_series` 436 ms,
`price_summary` 166 ms, `price_search` 20 ms, `farmer_options` 280 ms, `farmer_overview` 94 ms.

**4. Speicher ist knapp.** Zuletzt 423 von 500 MB. Carsten kümmert sich um den Ausbau.
Die Rohzeilen aus Juli (~150 MB) sind der nächste Hebel, falls es eng wird. Nach großen
Löschungen ist `VACUUM FULL` nötig, sonst wird nichts frei.

---

## Was als Nächstes ansteht

1. **Preismeldung durch Farmer.** Der eigentliche Zweck: was bietet FAMA, was bietet der
   Peraih. Braucht neue Tabellen, RLS und schreibende RPCs – bis jetzt ist alles nur lesend.
2. **Zugang für Tester.** Entschieden war: Einladungscode + Passwort. Noch nicht gebaut.
   Zurzeit ist die Vercel-Adresse öffentlich; der Schutz ist allein das widerrufbare Token.
3. **Validierung.** Farmer bestätigen oder bestreiten die FAMA-Preise.

## Fallen, in die ich schon getappt bin

- **`commodityvarietycd` ist nicht eindeutig.** 285 Varietäten fielen auf 35 Kulturen
  zusammen, Preise hingen an falschen Namen. Der Schlüssel ist vierteilig
  (`numis.fama_crop_code`). Falls Kulturen je wieder neu aufgebaut werden müssen:
  `numis_rebuild_crops`.
- **`commoditylevel`, `grade`, `unit` sind Codes, kein Text.** Die Zuordnung steht in
  `numis.fama_code_lookup` und kam aus FAMAs Referenztabellen – geraten war sie bei
  *jedem* Code falsch (`01`=BORONG, `03`=RUNCIT, `04`=LADANG).
- **Fremdschlüssel mit `ON DELETE SET NULL` braucht einen Index auf der verweisenden
  Spalte**, sonst laufen Löschungen in den 60-Sekunden-Timeout.
- **Leere Auswahlfelder** waren zweimal *nicht* eine veraltete Datei, sondern 3,7 s
  unsichtbares Nachladen. Erst messen, dann diagnostizieren.
- **`localStorage` kann `"de"` enthalten**, aus der Zeit mit deutschem Umschalter. Beide
  Seiten übernehmen deshalb nur Sprachen, die es wirklich gibt.

## Arbeitsweise, die sich bewährt hat

Carsten schreibt Deutsch; Antworten auf Deutsch. Code-Kommentare und `README.md` sind
deutsch, alles Sichtbare in den Seiten ist Englisch/Bahasa. Commit-Nachrichten Englisch.

Behauptungen über Laufzeiten, Zeilenzahlen oder Verhalten gehören gemessen, nicht geschätzt –
in diesem Projekt hat fast jede Vermutung sich als falsch erwiesen. Für die Seiten steht
Chromium bereit (`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`); ein lokaler
`python3 -m http.server` plus Playwright deckt Layout, Sprachwechsel und Fehlerpfade ab.
