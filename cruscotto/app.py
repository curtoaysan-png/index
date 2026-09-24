"""Cruscotto: avvio con `streamlit run app.py`."""
import streamlit as st

import db

st.set_page_config(page_title="Cruscotto", page_icon="🧭", layout="wide")
db.connetti()  # crea il database al primo avvio

pagine = [
    st.Page("pages/home.py", title="Home", icon="🏠", default=True),
    st.Page("pages/sessione.py", title="Sessione", icon="⏱️"),
    st.Page("pages/calendario.py", title="Calendario", icon="📅"),
    st.Page("pages/storico_piani.py", title="Storico piani", icon="🗂️"),
    st.Page("pages/fronti.py", title="Fronti", icon="🎯"),
    st.Page("pages/rinvii.py", title="Rinvii", icon="↪️"),
    st.Page("pages/preferenze.py", title="Preferenze e backup", icon="⚙️"),
]
st.navigation(pagine).run()
