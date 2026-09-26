"""Cruscotto: avvio con `streamlit run app.py`."""
import hmac
import os
import time
from pathlib import Path

import streamlit as st

# Nel cloud la configurazione arriva dai "Secrets" di Streamlit: la copiamo nelle variabili
# d'ambiente, dove la leggono db.py (DATABASE_URL) e assistente.py (ANTHROPIC_API_KEY).
try:
    for chiave in ("DATABASE_URL", "ANTHROPIC_API_KEY", "CRUSCOTTO_PASSWORD"):
        if chiave in st.secrets and not os.environ.get(chiave):
            os.environ[chiave] = str(st.secrets[chiave])
except Exception:  # nessun file di secrets: uso sul PC
    pass

# I server cloud usano l'ora UTC: date, timer e calendario devono essere in ora italiana.
os.environ["TZ"] = "Europe/Rome"
if hasattr(time, "tzset"):  # non esiste su Windows, dove l'ora del PC è già quella giusta
    time.tzset()

import db  # noqa: E402

st.set_page_config(page_title="Cruscotto", page_icon="🧭", layout="wide")


def su_streamlit_cloud() -> bool:
    # Streamlit Community Cloud esegue le app da /mount/src con l'utente "appuser".
    return str(Path(__file__).resolve()).startswith("/mount/src") or \
        os.environ.get("HOME") == "/home/appuser"


# Online senza database o senza password l'app NON parte: i dati finirebbero in un file
# temporaneo cancellato a ogni riavvio, e l'app sarebbe aperta a chiunque.
if su_streamlit_cloud():
    mancanti = [k for k in ("DATABASE_URL", "CRUSCOTTO_PASSWORD") if not os.environ.get(k, "").strip()]
    if mancanti:
        st.title("Cruscotto")
        st.error("L'app online non è ancora configurata: mancano " + " e ".join(f"`{k}`" for k in mancanti)
                 + " nei Secrets. Finché mancano, l'app resta bloccata per non perdere dati.")
        st.markdown(
            "Su **share.streamlit.io**, accanto all'app: **⋮ → Settings → Secrets**, poi aggiungi:\n"
            "```\nDATABASE_URL = \"postgresql://...stringa di Neon...\"\n"
            "CRUSCOTTO_PASSWORD = \"la tua password\"\n```\n"
            "Salva e attendi circa un minuto. Guida completa nel README, sezione "
            "*Usarlo anche dal telefono*."
        )
        st.stop()

pagine = [
    st.Page("pages/home.py", title="Home", icon="🏠", default=True),
    st.Page("pages/sessione.py", title="Sessione", icon="⏱️"),
    st.Page("pages/calendario.py", title="Calendario", icon="📅"),
    st.Page("pages/storico_piani.py", title="Storico piani", icon="🗂️"),
    st.Page("pages/fronti.py", title="Fronti", icon="🎯"),
    st.Page("pages/rinvii.py", title="Rinvii", icon="↪️"),
    st.Page("pages/acquisti.py", title="Acquisti", icon="🛒"),
    st.Page("pages/fonti.py", title="Fonti", icon="📚"),
    st.Page("pages/preferenze.py", title="Preferenze e backup", icon="⚙️"),
]

# Password (solo se impostata, cioè nel cloud).
password = os.environ.get("CRUSCOTTO_PASSWORD", "")
if password and not st.session_state.get("autenticata"):
    # "Ricordami": dopo l'accesso l'indirizzo contiene una chiave derivata dalla password.
    # Salvando quell'indirizzo (es. sulla schermata Home del telefono) non serve riscriverla.
    chiave = hmac.new(password.encode(), b"cruscotto", "sha256").hexdigest()[:32]
    if hmac.compare_digest(st.query_params.get("accesso", ""), chiave):
        st.session_state["autenticata"] = True
    else:
        st.navigation(pagine, position="hidden")  # resta sulla pagina richiesta
        st.title("Cruscotto")
        with st.form("accesso"):
            tentativo = st.text_input("Password", type="password")
            if st.form_submit_button("Entra", type="primary"):
                if hmac.compare_digest(tentativo.encode(), password.encode()):
                    st.session_state["autenticata"] = True
                    st.query_params["accesso"] = chiave
                    st.rerun()
                st.error("Password errata.")
        st.stop()

try:
    db.connetti()  # crea il database al primo avvio
except Exception as e:  # database online non raggiungibile
    st.error("Il database non risponde. Riprova tra qualche secondo ricaricando la pagina.")
    st.caption(f"Dettaglio tecnico: {type(e).__name__}")
    st.stop()
st.navigation(pagine).run()
