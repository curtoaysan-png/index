"""Gestione dei fronti. Cambiare la scadenza richiede un motivo (registrato nei rinvii)."""
from datetime import date

import streamlit as st

import db
import logica

conn = db.connetti()
st.title("Fronti")

if msg := st.session_state.pop("msg_fronti", None):
    st.success(msg)


def obiettivo_input(chiave, valore):
    definito = st.checkbox("Obiettivo definito", valore is not None, key=f"{chiave}_def")
    if not definito:
        return None
    return st.number_input("Obiettivo", min_value=1, step=1, value=valore or 1, key=f"{chiave}_ob")


with st.expander("Nuovo fronte"):
    nome = st.text_input("Nome", key="n_nome")
    c1, c2 = st.columns(2)
    scadenza = c1.date_input("Scadenza", key="n_scad", format="DD/MM/YYYY")
    unita = c2.text_input("Unità (es. parole, capitoli, libri)", key="n_unita")
    obiettivo = obiettivo_input("n", None)
    if st.button("Crea fronte", type="primary"):
        try:
            db.crea_fronte(conn, nome, scadenza, unita, obiettivo)
            st.session_state["msg_fronti"] = f"Fronte creato: {nome}."
            st.rerun()
        except ValueError as e:
            st.error(str(e))

n_rinvii = db.conta_rinvii(conn)
for f in db.fronti(conn, solo_attivi=False):
    stato = "" if f["attivo"] else " (archiviato)"
    with st.expander(f"{f['nome']}{stato} — scadenza {logica.a_data(f['scadenza']):%d/%m/%Y}"):
        k = f"f{f['id']}"
        nome = st.text_input("Nome", f["nome"], key=f"{k}_nome")
        c1, c2 = st.columns(2)
        unita = c1.text_input("Unità", f["unita"], key=f"{k}_unita")
        attuale = c2.number_input("Stato attuale", min_value=0, step=1, value=f["attuale"], key=f"{k}_att")
        obiettivo = obiettivo_input(k, f["obiettivo"])
        attivo = st.checkbox("Attivo", bool(f["attivo"]), key=f"{k}_attivo",
                             help="Togli la spunta per archiviare il fronte.")
        if st.button("Salva", key=f"{k}_salva"):
            db.modifica_fronte(conn, f["id"], nome, unita, obiettivo, attuale, attivo)
            st.session_state["msg_fronti"] = "Modifiche salvate."
            st.rerun()

        st.markdown("**Cambia scadenza**")
        st.caption(f"Rinvii registrati: {n_rinvii.get(f['id'], 0)}")
        c1, c2 = st.columns([1, 2])
        nuova = c1.date_input("Nuova scadenza", logica.a_data(f["scadenza"]), key=f"{k}_nuova",
                              format="DD/MM/YYYY")
        motivo = c2.text_input("Motivo (obbligatorio)", key=f"{k}_motivo")
        if st.button("Cambia scadenza", key=f"{k}_cambia"):
            if nuova == logica.a_data(f["scadenza"]):
                st.error("La nuova scadenza è uguale a quella attuale.")
            elif not motivo.strip():
                st.error("Serve un motivo per cambiare la scadenza.")
            else:
                db.cambia_scadenza(conn, f["id"], nuova, motivo)
                st.session_state["msg_fronti"] = "Scadenza cambiata e registrata nei rinvii."
                st.rerun()
