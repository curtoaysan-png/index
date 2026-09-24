"""Sessione di lavoro: avvio, timer e chiusura obbligatoria."""
from datetime import datetime

import streamlit as st

import assistente
import db
from logica import num

conn = db.connetti()

# Avvio diretto dalla home o dal calendario: st.session_state["avvia"] = (fronte_id, durata)
richiesta = st.session_state.pop("avvia", None)
if richiesta and not db.sessione_in_corso(conn):
    db.avvia_sessione(conn, *richiesta)

sessione = db.sessione_in_corso(conn)
st.title("Sessione")


def mostra_domande_precedenti(fronte_id):
    domande = db.ultime_domande(conn, fronte_id)
    if domande:
        st.markdown("**Domande rimaste dalla sessione precedente**")
        st.markdown("\n".join(f"- {d}" for d in domande))


if sessione is None:
    fronti = db.fronti(conn)
    if not fronti:
        st.info("Nessun fronte attivo. Crea un fronte (o esegui `python seed.py`).")
        st.stop()
    ids = [f["id"] for f in fronti]
    pre = st.session_state.get("fronte_scelto")
    fronte_id = st.selectbox(
        "Fronte", ids, index=ids.index(pre) if pre in ids else 0,
        format_func=lambda i: next(f["nome"] for f in fronti if f["id"] == i),
    )
    # Dal calendario arriva la durata del blocco di lavoro.
    durate = [90, 10]
    blocco = st.session_state.get("durata_scelta")
    if blocco and blocco not in durate:
        durate.insert(0, blocco)
    durata = st.radio("Durata", durate, index=durate.index(blocco) if blocco in durate else 0,
                      format_func=lambda m: f"{m} minuti", horizontal=True)
    rip = db.ultima_ripartenza(conn, fronte_id)
    if rip:
        st.markdown("**Da dove riparti**")
        st.info(rip)
    mostra_domande_precedenti(fronte_id)
    if st.button("Avvia", type="primary"):
        db.avvia_sessione(conn, fronte_id, durata)
        st.session_state.pop("durata_scelta", None)
        st.rerun()
    st.stop()

# ---------------------------------------------------------------- sessione in corso
st.subheader(sessione["fronte"])
rip = db.ultima_ripartenza(conn, sessione["fronte_id"])
if rip:
    st.markdown("**Da dove riparti**")
    st.info(rip)
mostra_domande_precedenti(sessione["fronte_id"])

inizio = datetime.fromisoformat(sessione["inizio"])
durata_s = sessione["durata_prevista_min"] * 60


@st.fragment(run_every=1)
def timer():
    trascorso = int((datetime.now() - inizio).total_seconds())
    residuo = durata_s - trascorso
    m, s = divmod(abs(residuo), 60)
    if residuo >= 0:
        st.metric("Tempo residuo", f"{m:02d}:{s:02d}")
    else:
        st.metric("Oltre la durata prevista", f"+{m:02d}:{s:02d}")
    st.progress(min(trascorso / durata_s, 1.0),
                text=f"{sessione['durata_prevista_min']} minuti previsti, iniziata alle {inizio:%H:%M}")


timer()

st.divider()
st.markdown("#### Chiusura")
st.caption("Si può chiudere anche prima della fine. Tutti e tre i campi sono obbligatori.")
output = st.number_input(f"Output prodotto ({sessione['unita']})", min_value=0, step=1, value=None,
                         placeholder="anche 0")
spiegazione = st.text_area(
    "Spiegazione: 3 frasi con parole tue su cosa hai prodotto",
    help=f"Almeno {db.MIN_SPIEGAZIONE} caratteri.",
)
st.caption(f"{len(spiegazione.strip())} / {db.MIN_SPIEGAZIONE} caratteri")

# Domande in stile Feynman sulla spiegazione (facoltative): solo domande, nessuna risposta.
chiave_domande = f"domande_{sessione['id']}"
if st.button("Fammi domande su questa spiegazione",
             disabled=len(spiegazione.strip()) < db.MIN_SPIEGAZIONE,
             help="L'assistente fa 3 domande sul tuo testo. Non scrive risposte né corregge."):
    try:
        with st.spinner("Preparo le domande…"):
            st.session_state[chiave_domande] = assistente.chiedi_domande(sessione["fronte"], spiegazione)
    except assistente.ErroreAssistente as e:
        st.error(str(e))
domande = st.session_state.get(chiave_domande, [])
if domande:
    with st.container(border=True):
        st.markdown("\n".join(f"{i}. {d}" for i, d in enumerate(domande, 1)))
        st.caption("Le domande vengono salvate con la sessione e riproposte all'avvio della prossima.")
ripartenza = st.text_input("Ripartenza: la frase da cui ricominciare la prossima volta")

col1, col2 = st.columns([1, 1])
if col1.button("Salva e chiudi", type="primary"):
    errori = []
    if output is None:
        errori.append("Inserisci l'output (anche 0).")
    if len(spiegazione.strip()) < db.MIN_SPIEGAZIONE:
        errori.append(f"La spiegazione deve avere almeno {db.MIN_SPIEGAZIONE} caratteri.")
    if not ripartenza.strip():
        errori.append("Inserisci la ripartenza.")
    if errori:
        for e in errori:
            st.error(e)
    else:
        db.chiudi_sessione(conn, sessione["id"], output, spiegazione, ripartenza, domande=domande)
        st.session_state.pop(chiave_domande, None)
        st.session_state["msg_home"] = f"Sessione salvata: {num(output)} {sessione['unita']}."
        st.switch_page("pages/home.py")

with col2.popover("Annulla sessione"):
    st.write("La sessione viene eliminata senza salvare nulla.")
    if st.button("Conferma annullamento"):
        db.annulla_sessione(conn, sessione["id"])
        st.rerun()
