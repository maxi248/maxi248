@echo off
REM ---------------------------------------------------------------------------
REM Taeglicher NuMIS-Import der FAMA-Preise (Windows Aufgabenplanung).
REM
REM Einmalig vorbereiten:
REM   setx NUMIS_SERVICE_KEY "<supabase-service-role-key>"
REM   (danach ein NEUES Eingabeaufforderungs-Fenster oeffnen)
REM
REM Taeglich einplanen (einmal ausfuehren, Pfad ggf. anpassen):
REM   schtasks /create /tn "NuMIS FAMA Import" ^
REM     /tr "C:\Users\carst\Downloads\run_fama_import.bat" ^
REM     /sc daily /st 07:30 /f
REM
REM Das Fenster --days 7 ist Absicht: faellt der Rechner eine Woche aus,
REM holt der naechste Lauf alle fehlenden Tage selbsttaetig nach.
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

set LOG=fama_import.log

if "%NUMIS_SERVICE_KEY%"=="" (
  echo [%date% %time%] FEHLER: NUMIS_SERVICE_KEY ist nicht gesetzt.>> "%LOG%"
  exit /b 2
)

echo.>> "%LOG%"
echo ===== [%date% %time%] Start =====>> "%LOG%"

python fama_to_numis.py --days 7 >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%

echo ===== [%date% %time%] Ende, Rueckgabewert %RC% =====>> "%LOG%"
exit /b %RC%
