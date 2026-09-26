"""Piccoli aiuti condivisi dalle pagine Streamlit."""
import streamlit as st

import db


def conn():
    return db.connetti()


@st.cache_data(max_entries=300, show_spinner=False)
def _foto(capo_id: int) -> bytes | None:
    return db.foto_capo(conn(), capo_id)


def foto(capo: dict, **kwargs) -> None:
    """Mostra la foto del capo, o un segnaposto se manca."""
    dati = _foto(capo["id"])
    if dati:
        st.image(dati, **kwargs)
    else:
        st.markdown(f"🧺 *{capo['categoria']}*")


def svuota_cache_foto() -> None:
    """Da chiamare dopo un ripristino: gli stessi id possono indicare foto diverse."""
    _foto.clear()


def descrizione(capo: dict) -> str:
    colori = ", ".join(capo["colori"]) or "colore n.d."
    return f"**{capo['categoria']}** · {colori} · {capo['stile'] or 'stile n.d.'} · formalità {capo['formalita']}"
