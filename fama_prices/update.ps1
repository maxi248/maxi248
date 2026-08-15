# update.ps1 - holt die aktuellen NuMIS/FAMA-Dateien nach hier.
#
# Aufruf im Ordner mit den Skripten:
#     powershell -ExecutionPolicy Bypass -File update.ps1
# oder, wenn Skripte erlaubt sind:
#     .\update.ps1
#
# Hinweis: update.ps1 aktualisiert sich absichtlich NICHT selbst - eine Datei
# zu ueberschreiben, waehrend sie laeuft, ist unnoetig riskant. Falls sich das
# Skript selbst aendert, steht das ausdruecklich dabei.

$base = "https://raw.githubusercontent.com/maxi248/maxi248/refs/heads/" +
        "claude/fama-malaysia-price-data-tu8qfj/fama_prices/"

$files = @(
  "fama_ami_client.py",
  "fama_to_numis.py",
  "numis_preisabfrage.html",
  "run_fama_import.bat"
)

Write-Host "Aktualisiere aus GitHub ..." -ForegroundColor Cyan
$fehler = 0

foreach ($f in $files) {
  try {
    # Erst in eine Nebendatei laden, dann ersetzen: bricht der Download ab,
    # bleibt die funktionierende alte Datei stehen.
    $tmp = "$f.neu"
    Invoke-WebRequest -Uri ($base + $f) -OutFile $tmp -UseBasicParsing -ErrorAction Stop
    Move-Item -Path $tmp -Destination $f -Force
    Write-Host ("  ok      " + $f)
  } catch {
    $fehler++
    Write-Host ("  FEHLER  " + $f + " - " + $_.Exception.Message) -ForegroundColor Red
    if (Test-Path "$f.neu") { Remove-Item "$f.neu" -Force }
  }
}

# Alte kompilierte Zwischenstaende koennen sonst eine veraltete Fassung liefern.
if (Test-Path "__pycache__") { Remove-Item "__pycache__" -Recurse -Force }

if ($fehler -eq 0) {
  Write-Host "Fertig - alle Dateien aktuell." -ForegroundColor Green
} else {
  Write-Host ("Fertig, aber " + $fehler + " Datei(en) fehlgeschlagen.") -ForegroundColor Yellow
}
