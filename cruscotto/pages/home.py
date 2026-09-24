"""Home: da dove riparti, agenda di oggi, fronti e catena dei giorni."""
from datetime import date, timedelta

import streamlit as st

import db
import logica
from logica import num

conn = db.connetti()


def arrotonda(x):
    # Decimali solo per unità piccole (libri, capitoli), interi per le parole.
    return round(x, 2) if x < 10 else round(x)


oggi = date.today()

if msg := st.session_state.pop("msg_home", None):
    st.success(msg)


def avvia(fronte_id, durata):
    st.session_state["avvia"] = (fronte_id, durata)
    st.switch_page("pages/sessione.py")


fronti = db.fronti(conn)
sessioni = db.sessioni_chiuse(conn, dal=oggi - timedelta(days=30))
in_corso = db.sessione_in_corso(conn)

if in_corso:
    st.warning(f"Sessione in corso: {in_corso['fronte']}.")
    if st.button("Torna alla sessione", type="primary"):
        st.switch_page("pages/sessione.py")

# ---------------------------------------------------------------- da dove riparti
vicino = logica.fronte_piu_vicino(fronti)
if vicino:
    st.caption(f"Da dove riparti — {vicino['nome']}")
    rip = db.ultima_ripartenza(conn, vicino["id"])
    st.markdown(f"## {rip}" if rip else "## Nessuna sessione ancora registrata.")
    c1, c2, _ = st.columns([1, 1, 4])
    if c1.button("Avvia 90 minuti", type="primary", disabled=bool(in_corso)):
        avvia(vicino["id"], 90)
    if c2.button("Avvia 10 minuti", disabled=bool(in_corso)):
        avvia(vicino["id"], 10)
else:
    st.info("Nessun fronte attivo. Esegui `python seed.py` o crea un fronte nella pagina Fronti.")

# ---------------------------------------------------------------- fronti
st.divider()
PALLINO = {"verde": "🟢", "giallo": "🟡", "rosso": "🔴", "grigio": "⚪"}
n_rinvii = db.conta_rinvii(conn)
colonne = st.columns(2)
for i, f in enumerate(fronti):
    p = logica.proiezione(f, sessioni, oggi)
    with colonne[i % 2].container(border=True):
        st.markdown(f"#### {f['nome']}")
        if f["obiettivo"]:
            st.progress(min(f["attuale"] / f["obiettivo"], 1.0),
                        text=f"{num(f['attuale'])} / {num(f['obiettivo'])} {f['unita']}")
        else:
            st.caption(f"{num(f['attuale'])} {f['unita']} — obiettivo da definire")

        gm = p["giorni_mancanti"]
        scad = logica.a_data(f["scadenza"])
        testo_giorni = f"{gm} giorni alla scadenza" if gm >= 0 else f"scadenza superata da {-gm} giorni"
        st.markdown(f"{testo_giorni} ({scad:%d/%m/%Y})")

        if p["completato"]:
            st.markdown("🟢 Obiettivo raggiunto")
        elif f["obiettivo"]:
            stima = p["data_stimata"]
            stima_txt = f"stima: {stima:%d/%m/%Y}" if stima else "stima: non calcolabile"
            st.markdown(f"{PALLINO[p['colore']]} {stima_txt}")
            st.caption(
                f"servono ~{num(arrotonda(p['ritmo_necessario']))} {f['unita']}/giorno, "
                f"ritmo attuale: {num(round(p['ritmo_attuale'], 1))}"
            )
        rinvii = n_rinvii.get(f["id"], 0)
        st.caption(f"Rinvii registrati: {rinvii}")
        b1, b2, _ = st.columns([1, 1, 2])
        if b1.button("90 min", key=f"a90_{f['id']}", disabled=bool(in_corso)):
            avvia(f["id"], 90)
        if b2.button("10 min", key=f"a10_{f['id']}", disabled=bool(in_corso)):
            avvia(f["id"], 10)

# ---------------------------------------------------------------- catena dei giorni
st.divider()
catena = logica.catena_giorni(sessioni, oggi, 14)
quadrati = "".join(
    f'<div title="{g:%d/%m}" style="width:22px;height:22px;border-radius:4px;'
    f'border:2px solid #4a7c59;background:{"#4a7c59" if pieno else "transparent"}"></div>'
    for g, pieno in catena
)
st.caption("Ultimi 14 giorni")
st.markdown(f'<div style="display:flex;gap:6px">{quadrati}</div>', unsafe_allow_html=True)

