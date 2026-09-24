"""Pezzi di interfaccia condivisi tra più pagine."""
from datetime import date, datetime, timedelta

import streamlit as st

import db
import logica

COLORI = {
    "turno": "#b5533c",
    "lezione": "#3b6ea5",
    "esame": "#7a4fa0",
    "personale": "#6b7280",
    "blocco di lavoro": "#3f7d4f",
}


def prepara_sessione(fronte_id, durata_min):
    """Apre la pagina sessione con fronte e durata già impostati (senza avviare)."""
    st.session_state["fronte_scelto"] = fronte_id
    st.session_state["durata_scelta"] = int(durata_min)
    st.switch_page("pages/sessione.py")


def durata_min(occ) -> int:
    return round((occ["fine_dt"] - occ["inizio_dt"]).total_seconds() / 60)


def mostra_agenda_oggi(conn, oggi: date):
    occ = logica.espandi_impegni(db.impegni(conn), oggi, oggi + timedelta(days=1))
    st.markdown("#### Oggi")
    if not occ:
        st.caption("Nessun impegno in calendario.")
        return
    for o in occ:
        c1, c2 = st.columns([5, 1])
        pallino = f'<span style="color:{COLORI[o["tipo"]]}">●</span>'
        testo = o["titolo"]
        if o["tipo"] == "blocco di lavoro" and o.get("fronte"):
            testo = f"{o['fronte']} — {o['titolo']}" if o["titolo"] != o["fronte"] else o["fronte"]
        c1.markdown(
            f"{pallino} {o['inizio_dt']:%H:%M}–{o['fine_dt']:%H:%M} &nbsp; {testo} "
            f"<span style='color:#888'>({o['tipo']})</span>",
            unsafe_allow_html=True,
        )
        if o["tipo"] == "blocco di lavoro" and o.get("fronte_id"):
            if c2.button("Apri", key=f"agenda_{o['id']}_{o['inizio_dt']:%H%M}"):
                prepara_sessione(o["fronte_id"], durata_min(o))


def eventi_calendario(occorrenze, proposti=()) -> list[dict]:
    """Converte le occorrenze negli eventi di FullCalendar."""
    eventi = []
    for o in occorrenze:
        titolo = o["titolo"]
        if o["tipo"] == "blocco di lavoro" and o.get("fronte") and o["fronte"] not in titolo:
            titolo = f"{o['fronte']}: {titolo}"
        eventi.append({
            "id": f"{o['id']}_{o['inizio_dt']:%Y%m%d}",
            "title": titolo,
            "start": o["inizio_dt"].isoformat(),
            "end": o["fine_dt"].isoformat(),
            "backgroundColor": COLORI[o["tipo"]],
            "borderColor": COLORI[o["tipo"]],
            "extendedProps": {
                "impegno_id": o["id"], "tipo": o["tipo"], "fronte_id": o.get("fronte_id"),
                "durata": durata_min(o),
            },
        })
    for i, b in enumerate(proposti):
        eventi.append({
            "id": f"proposto_{i}",
            "title": f"[proposta] {b['fronte']}: {b.get('attivita', '')}",
            "start": b["inizio"],
            "end": b["fine"],
            "classNames": ["proposto"],
            "backgroundColor": "rgba(63,125,79,0.12)",
            "borderColor": COLORI["blocco di lavoro"],
            "textColor": "#1f3d27",
            "extendedProps": {"tipo": "proposta"},
        })
    return eventi


CSS_CALENDARIO = """
.fc-event.proposto { border-style: dashed !important; border-width: 2px !important; }
.fc-event { cursor: pointer; }
"""


def adesso() -> datetime:
    return datetime.now().replace(second=0, microsecond=0)
