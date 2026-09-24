"""Lista d'attesa acquisti: 48 ore prima di decidere."""
from datetime import date, datetime

import streamlit as st

import db
import logica

conn = db.connetti()
adesso = datetime.now()
st.title("Lista d'attesa acquisti")


def euro(x: float) -> str:
    return f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


with st.container(border=True):
    c1, c2, c3 = st.columns([3, 1, 1.5])
    oggetto = c1.text_input("Oggetto")
    prezzo = c2.number_input("Prezzo (€)", min_value=0.0, step=1.0, format="%.2f")
    categoria = c3.selectbox("Categoria", db.CATEGORIE_ACQUISTI)
    if st.button("Aggiungi alla lista", type="primary"):
        try:
            db.aggiungi_acquisto(conn, oggetto, prezzo, categoria)
            st.rerun()
        except ValueError as e:
            st.error(str(e))

tutti = db.acquisti(conn)
in_attesa = [a for a in tutti if a["stato"] == "in attesa"]
st.markdown("#### In attesa")
if not in_attesa:
    st.caption("Nessun oggetto in attesa.")
for a in in_attesa:
    residuo = logica.attesa_residua(a["aggiunto_il"], adesso, db.ATTESA_ACQUISTI_ORE)
    bloccato = residuo.total_seconds() > 0
    c1, c2, c3 = st.columns([4, 1, 1])
    testo = f"**{a['oggetto']}** — {euro(a['prezzo'])} · {a['categoria']}"
    if bloccato:
        ore, resto = divmod(int(residuo.total_seconds()), 3600)
        testo += f"  \nsi può decidere tra {ore} h {resto // 60} min"
    c1.markdown(testo)
    for col, stato in ((c2, "comprato"), (c3, "rinunciato")):
        if col.button(stato.capitalize(), key=f"{stato}_{a['id']}", disabled=bloccato):
            db.decidi_acquisto(conn, a["id"], stato)
            st.rerun()

# ---------------------------------------------------------------- riepilogo del mese
st.divider()
oggi = date.today()
r = logica.riepilogo_acquisti_mese(tutti, oggi.year, oggi.month)
st.markdown(f"#### {oggi:%m/%Y}")
m1, m2 = st.columns(2)
m1.metric("Non spesi questo mese", euro(r["rinunciato"]))
m2.metric("Comprati questo mese", euro(r["comprato"]))
if r["per_categoria"]:
    st.table([
        {"Categoria": cat, "Comprati": euro(v["comprato"]), "Rinunciati": euro(v["rinunciato"])}
        for cat, v in sorted(r["per_categoria"].items())
    ])

decisi = [a for a in tutti if a["stato"] != "in attesa"]
if decisi:
    with st.expander("Storico decisioni"):
        for a in decisi:
            st.markdown(f"- {logica.a_dt(a['deciso_il']):%d/%m/%Y} · {a['oggetto']} · "
                        f"{euro(a['prezzo'])} · {a['stato']}")
