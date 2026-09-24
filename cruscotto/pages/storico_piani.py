"""Storico dei piani dell'assistente, per settimana."""
import json

import streamlit as st

import db
import logica

conn = db.connetti()
st.title("Storico piani")

storico = logica.storico_piani(db.piani(conn), db.impegni(conn), db.sessioni_chiuse(conn))
if not storico:
    st.caption("Nessun piano registrato.")

for sett in storico:
    lun = logica.a_data(sett["settimana"])
    with st.container(border=True):
        st.markdown(f"#### Settimana dal {lun:%d/%m/%Y}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Piani", sett["piani"])
        c2.metric("Ripianificazioni", sett["ripianificazioni"])
        c3.metric("Blocchi pianificati", sett["blocchi_pianificati"])
        c4.metric("Sessioni fatte", sett["sessioni_fatte"])
        for p in sett["elenco"]:
            proposta = json.loads(p["proposta_json"] or "{}")
            n_prop = len(proposta.get("validi", []))
            n_acc = len(proposta.get("accettati", []))
            etichetta = (f"{logica.a_dt(p['creato_il']):%d/%m %H:%M} · {p['tipo']} · {p['stato']} · "
                         f"{n_prop} blocchi proposti" + (f", {n_acc} accettati" if p["stato"] == "accettato" else ""))
            with st.expander(etichetta):
                if p["spiegazione"]:
                    st.write(p["spiegazione"])
                for a in proposta.get("avvisi", []):
                    st.caption(f"Avviso: {a}")
                for s in proposta.get("scartati", []):
                    st.caption(f"Scartato: {s.get('fronte', '?')} {s.get('inizio', '')} — {s['motivo']}")
                st.caption("Dati inviati all'assistente")
                st.json(json.loads(p["input_json"]), expanded=False)
