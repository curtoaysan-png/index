"""Armadio — pagina iniziale. Avvio: streamlit run app.py"""
import streamlit as st

import ai
import db
import ui

st.set_page_config(page_title="Armadio", page_icon="👗", layout="wide")
st.title("👗 Armadio")
st.write("Un'app personale per decidere cosa indossare.")

c = ui.conn()
capi = db.capi(c)
profilo = db.profilo(c)

col1, col2, col3 = st.columns(3)
col1.metric("Capi nell'armadio", len(capi))
col2.metric("Outfit proposti", len(db.outfit_recenti(c, 10_000)))
col3.metric("Stagione armocromia", profilo["stagione_armocromia"] or "—")

st.markdown("""
- **Armadio**: fotografa i capi, controlla la scheda precompilata e salva.
- **Outfit**: descrivi l'occasione e ricevi un abbinamento fatto con i tuoi capi.
- **Armocromia**: stima indicativa di sottotono e palette a partire da un selfie.
""")

if not ai.chiave_presente():
    st.info("Nessuna chiave API trovata (ANTHROPIC_API_KEY): l'armadio funziona con l'inserimento "
            "manuale; outfit e armocromia richiedono la chiave.")
