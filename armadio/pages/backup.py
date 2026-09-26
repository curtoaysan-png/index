"""Backup e ripristino di tutti i dati, foto comprese."""
import streamlit as st

import config
import db
import ui

c = ui.conn()
st.title("Backup")

if db.in_cloud():
    st.caption("I dati sono nel database online. Scarica ogni tanto una copia: è un file che puoi "
               "tenere anche su OneDrive.")
else:
    st.caption(f"Database: `{config.DB_PATH}`. Tienilo in una cartella locale; il backup può andare "
               "anche su OneDrive.")
st.download_button("Scarica backup", data=lambda: db.backup_in_byte(c), file_name=db.nome_backup(),
                   mime="application/octet-stream", type="primary")

if not db.in_cloud():
    with st.expander("Salva il backup in una cartella del PC"):
        cartella = st.text_input("Cartella di destinazione", str(config.BACKUP_DIR))
        if st.button("Salva nella cartella"):
            try:
                dest = db.esporta_backup(c, cartella)
                st.success(f"Backup salvato: {dest}")
            except OSError as e:
                st.error(f"Backup non riuscito: {e}")

st.divider()
st.markdown("#### Ripristina da un backup")
st.caption("Sostituisce **tutti** i dati attuali con quelli del file. Serve anche per portare online "
           "i dati che avevi sul PC.")
file = st.file_uploader("File di backup (.db)", type=["db"])
if file is not None:
    conferma = st.checkbox("Ho capito: i dati attuali verranno sostituiti")
    if st.button("Ripristina", disabled=not conferma):
        try:
            db.ripristina_backup(c, file.getvalue())
            ui.svuota_cache_foto()
            st.success("Dati ripristinati.")
        except ValueError as e:
            st.error(str(e))
