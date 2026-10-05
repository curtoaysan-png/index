"""Apre l'app su Streamlit Community Cloud per non farla andare in pausa.

Streamlit mette in pausa le app gratuite dopo circa 12 ore senza visite; la riapertura
richiede poi molto tempo. Questo script, lanciato ogni poche ore da GitHub Actions, apre la
pagina in un browser vero (serve una visita reale, non basta una richiesta HTTP) e, se l'app è
già in pausa, preme il pulsante per risvegliarla.

Uso: python sveglia_streamlit.py https://nome-app.streamlit.app
"""
import os
import sys
import time

from playwright.sync_api import sync_playwright

ATTESA_AVVIO_S = 180  # una ripartenza da zero può richiedere qualche minuto


def app_caricata(pagina) -> bool:
    # Su streamlit.app l'app vera è dentro un iframe: controllo tutti i frame.
    return any(f.locator("[data-testid=stApp]").count() for f in pagina.frames)


def sveglia(url: str) -> bool:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH") or None)
        pagina = browser.new_page()
        pagina.goto(url, wait_until="domcontentloaded", timeout=120_000)
        pagina.wait_for_timeout(10_000)

        pulsante = pagina.get_by_role("button", name="get this app back up")
        if pulsante.count():
            print("App in pausa: la risveglio.")
            pulsante.first.click()
        else:
            print("Nessuna pausa da interrompere.")

        pronta = False
        scadenza = time.monotonic() + ATTESA_AVVIO_S
        while time.monotonic() < scadenza:
            if app_caricata(pagina):
                pronta = True
                break
            pagina.wait_for_timeout(3_000)
        if pronta:
            pagina.wait_for_timeout(15_000)  # resto collegata un po': conta come visita
        browser.close()
        print("App pronta." if pronta else "App non pronta entro il tempo massimo.")
        return pronta


if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Indirizzo dell'app mancante: imposta il secret CRUSCOTTO_URL nel repository.")
        sys.exit(0)  # non è un errore del codice: manca solo la configurazione
    sys.exit(0 if sveglia(sys.argv[1].strip()) else 1)
