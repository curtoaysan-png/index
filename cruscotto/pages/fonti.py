"""Fonti per fronte, con stato di lettura."""
import streamlit as st

import db

conn = db.connetti()
st.title("Fonti")

fronti = db.fronti(conn)
if not fronti:
    st.caption("Nessun fronte attivo.")
    st.stop()
nomi = {f["id"]: f["nome"] for f in fronti}
fronte_id = st.selectbox("Fronte", list(nomi), format_func=nomi.get)

with st.container(border=True):
    c1, c2 = st.columns([3, 1])
    titolo = c1.text_input("Nuova fonte")
    stato = c2.selectbox("Stato", db.STATI_FONTE)
    if st.button("Aggiungi", type="primary"):
        try:
            db.aggiungi_fonte(conn, fronte_id, titolo, stato)
            st.rerun()
        except ValueError as e:
            st.error(str(e))

solo_citato = st.checkbox("Solo citato (non davvero letto)")
elenco = db.fonti(conn, fronte_id)
conteggi = {s: sum(f["stato"] == s for f in elenco) for s in db.STATI_FONTE}
st.caption(" · ".join(f"{s}: {n}" for s, n in conteggi.items()))
if solo_citato:
    elenco = [f for f in elenco if f["stato"] == "solo citato"]
if not elenco:
    st.caption("Nessuna fonte.")
for fo in elenco:
    c1, c2, c3 = st.columns([4, 1.5, 0.6])
    c1.markdown(fo["titolo"])
    nuovo = c2.selectbox("Stato", db.STATI_FONTE, index=db.STATI_FONTE.index(fo["stato"]),
                         key=f"stato_{fo['id']}", label_visibility="collapsed")
    if nuovo != fo["stato"]:
        db.cambia_stato_fonte(conn, fo["id"], nuovo)
        st.rerun()
    if c3.button("✕", key=f"el_{fo['id']}", help="Elimina"):
        db.elimina_fonte(conn, fo["id"])
        st.rerun()
