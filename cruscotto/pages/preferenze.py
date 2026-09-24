"""Preferenze per l'assistente, backup e ripristino."""
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
if db.in_cloud():
    st.caption("I dati sono nel database online. Scarica ogni tanto una copia: è un file che puoi "
               "tenere anche su OneDrive.")
else:
    st.caption(f"Database: `{config.DB_PATH}`. Tienilo in una cartella locale; il backup può andare "
               "anche su OneDrive.")
st.download_button("Scarica backup", data=lambda: db.backup_in_byte(conn), file_name=db.nome_backup(),
                   mime="application/octet-stream", type="primary")

if not db.in_cloud():
    with st.expander("Salva il backup in una cartella del PC"):
        cartella = st.text_input("Cartella di destinazione", str(config.BACKUP_DIR))
        if st.button("Salva nella cartella"):
            try:
                dest = db.esporta_backup(conn, cartella)
                st.success(f"Backup salvato: {dest}")
            except OSError as e:
                st.error(f"Backup non riuscito: {e}")

st.divider()
st.markdown("#### Ripristina da un backup")
st.caption("Sostituisce **tutti** i dati attuali con quelli del file. Serve anche per portare nel "
           "cloud i dati che avevi sul PC.")
file = st.file_uploader("File di backup (.db)", type=["db"])
if file is not None:
    conferma = st.checkbox("Ho capito: i dati attuali verranno sostituiti")
    if st.button("Ripristina", disabled=not conferma):
        try:
            db.ripristina_backup(conn, file.getvalue())
            st.success("Dati ripristinati.")
        except ValueError as e:
            st.error(str(e))
