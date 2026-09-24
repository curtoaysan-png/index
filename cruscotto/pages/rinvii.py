"""Registro dei rinvii, per fronte e in ordine cronologico."""
import streamlit as st

import db
import logica

conn = db.connetti()
st.title("Rinvii")

tutti = db.rinvii(conn)
if not tutti:
    st.caption("Nessun rinvio registrato.")

for f in db.fronti(conn, solo_attivi=False):
    propri = [r for r in tutti if r["fronte_id"] == f["id"]]
    if not propri:
        continue
    volte = "volta" if len(propri) == 1 else "volte"
    st.markdown(f"#### {f['nome']} — rinviato {len(propri)} {volte}")
    for r in propri:
        st.markdown(
            f"- {logica.a_dt(r['data']):%d/%m/%Y}: {logica.a_data(r['vecchia_scadenza']):%d/%m/%Y} → "
            f"{logica.a_data(r['nuova_scadenza']):%d/%m/%Y} — {r['motivo']}"
        )
