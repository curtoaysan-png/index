"""Assistente outfit: descrivo l'occasione, ricevo un abbinamento fatto con i miei capi."""
from datetime import date

import streamlit as st

import ai
import config
import db
import ui

st.title("Cosa mi metto?")
c = ui.conn()
stato = st.session_state

capi = db.capi(c)
if not capi:
    st.info("L'armadio è vuoto: aggiungi qualche capo dalla pagina Armadio.")
    st.stop()
if not ai.chiave_presente():
    st.warning("L'assistente richiede la variabile d'ambiente ANTHROPIC_API_KEY.")

per_id = {k["id"]: k for k in capi}

with st.form("richiesta"):
    richiesta = st.text_area("Per cosa ti vesti?", placeholder="es. cena informale sabato sera, fa freddo")
    partenza = st.selectbox("Capo da cui partire (facoltativo)", [None] + list(per_id),
                            format_func=lambda i: "—" if i is None else
                            f"#{i} {per_id[i]['categoria']} · {', '.join(per_id[i]['colori'])}")
    invia = st.form_submit_button("✨ Proponi outfit", type="primary", disabled=not ai.chiave_presente())

if invia:
    if not richiesta.strip():
        st.error("Scrivi per cosa ti vesti.")
    else:
        with st.spinner("Sto pensando all'outfit…"):
            try:
                proposta = ai.proponi_outfit(richiesta, capi, db.profilo(c), db.outfit_recenti(c, 10),
                                             capo_partenza=partenza, oggi=date.today().isoformat())
            except ai.ErroreAI as e:
                st.error(str(e))
            else:
                alt = proposta.get("alternativa_stile")
                stato.outfit_id = db.salva_outfit(
                    c, richiesta.strip(), [v["capo_id"] for v in proposta["outfit"]],
                    proposta["spiegazione"], alt["stile"] if alt else "",
                    {"outfit": proposta["outfit"], "alternativa_stile": alt, "manca": proposta.get("manca")},
                )


def mostra(o: dict, chiave: str) -> None:
    dettagli = o["dettagli"]
    voci = [v for v in dettagli.get("outfit", []) if v["capo_id"] in per_id]
    if len(voci) < len(o["capi_ids"]):
        st.caption("Alcuni capi di questo outfit sono stati eliminati dall'armadio.")
    if voci:
        for col, v in zip(st.columns(max(len(voci), 1)), voci):
            with col:
                ui.foto(per_id[v["capo_id"]], width="stretch")
                st.markdown(ui.descrizione(per_id[v["capo_id"]]))
                st.caption(v["perche"])
    st.write(o["spiegazione"])

    alt = dettagli.get("alternativa_stile")
    if alt:
        with st.container(border=True):
            st.markdown(f"**Stile: {alt['stile']}** invece di *{alt['rispetto_a']}*")
            st.write(alt["perche"])
    if dettagli.get("manca"):
        st.caption(f"ℹ️ Starebbe bene anche: {dettagli['manca']}")

    cols = st.columns(len(config.GIUDIZI) + 1)
    icone = {"mi piace": "👍", "non mi piace": "👎", "indossato": "✅"}
    for col, g in zip(cols, config.GIUDIZI):
        attivo = o.get("giudizio") == g
        if col.button(f"{icone[g]} {g}", key=f"{chiave}_{g}", type="primary" if attivo else "secondary"):
            db.imposta_giudizio(c, o["id"], None if attivo else g)
            st.rerun()


if stato.get("outfit_id"):
    o = db.outfit(c, stato.outfit_id)
    if o:
        st.subheader("La proposta")
        mostra(o, "attuale")

st.divider()
st.subheader("Ultimi outfit")
for o in db.outfit_recenti(c, 10):
    if o["id"] == stato.get("outfit_id"):
        continue
    titolo = f"{o['creato_il'][:10]} — {o['richiesta']}" + (f" · {o['giudizio']}" if o["giudizio"] else "")
    with st.expander(titolo):
        mostra(o, f"o{o['id']}")
