"""Preferenze per l'assistente e backup del database."""
import streamlit as st

import config
import db

conn = db.connetti()
st.title("Preferenze")

pref = db.preferenze(conn)
st.markdown("#### Regole di lavoro")
st.caption("Usate dall'assistente per organizzare la settimana.")
testo = st.text_area("Regole", pref["testo_regole"], height=150, label_visibility="collapsed")
c1, c2, _ = st.columns([1, 1, 3])
if c1.button("Salva regole"):
    db.salva_preferenze(conn, testo_regole=testo)
    st.success("Regole salvate.")
if c2.button("Ripristina predefinite"):
    db.salva_preferenze(conn, testo_regole=db.REGOLE_DEFAULT)
    st.rerun()

st.divider()
st.markdown("#### Backup")
st.caption(f"Database: `{config.DB_PATH}`. Tienilo in una cartella locale; il backup può andare anche "
           "su OneDrive.")
cartella = st.text_input("Cartella di destinazione", str(config.BACKUP_DIR))
if st.button("Esporta backup", type="primary"):
    try:
        dest = db.esporta_backup(conn, cartella)
        st.success(f"Backup salvato: {dest}")
    except OSError as e:
        st.error(f"Backup non riuscito: {e}")
