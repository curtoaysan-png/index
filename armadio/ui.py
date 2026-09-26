"""Piccoli aiuti condivisi dalle pagine Streamlit."""
import streamlit as st

import config
import db


@st.cache_resource
def conn():
    return db.connetti()


def foto(capo: dict, **kwargs) -> None:
    """Mostra la foto del capo, o un segnaposto se manca."""
    percorso = config.BASE / capo["foto_path"] if capo.get("foto_path") else None
    if percorso and percorso.exists():
        st.image(str(percorso), **kwargs)
    else:
        st.markdown(f"🧺 *{capo['categoria']}*")


def descrizione(capo: dict) -> str:
    colori = ", ".join(capo["colori"]) or "colore n.d."
    return f"**{capo['categoria']}** · {colori} · {capo['stile'] or 'stile n.d.'} · formalità {capo['formalita']}"
