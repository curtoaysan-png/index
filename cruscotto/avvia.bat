@echo off
rem Avvio del Cruscotto con doppio clic (Windows).
chcp 65001 >nul
title Cruscotto
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 goto senza_python

if not exist data mkdir data

rem Installa le librerie alla prima esecuzione e quando requirements.txt cambia.
fc /b requirements.txt data\requisiti_installati.txt >nul 2>nul
if errorlevel 1 goto installa
goto dopo_installa

:installa
echo Installo le librerie: la prima volta ci vuole qualche minuto...
python -m pip install -r requirements.txt
if errorlevel 1 goto errore_installazione
copy /y requirements.txt data\requisiti_installati.txt >nul

:dopo_installa
rem Crea i fronti iniziali solo al primo avvio (i dati stanno in AppData\Local\Cruscotto).
python seed.py --se-vuoto

rem Evita la domanda sull'email che Streamlit fa al primo avvio.
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    echo [general]> "%USERPROFILE%\.streamlit\credentials.toml"
    echo email = "">> "%USERPROFILE%\.streamlit\credentials.toml"
)

echo.
echo Il Cruscotto si apre nel browser.
echo Per chiuderlo, chiudi questa finestra.
echo.
python -m streamlit run app.py --browser.gatherUsageStats false
pause
exit /b

:senza_python
echo Python non trovato.
echo Installalo da python.org e, nella prima schermata, spunta "Add Python to PATH".
pause
exit /b 1

:errore_installazione
echo.
echo Installazione delle librerie non riuscita: copia il messaggio qui sopra e mandalo a Claude.
pause
exit /b 1
