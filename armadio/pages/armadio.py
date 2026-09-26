"""Armadio: aggiunta dei capi (foto → scheda → Salva) e griglia con filtri."""
import hashlib

import streamlit as st

import ai
import config
import db
import ui

st.title("Il mio armadio")
c = ui.conn()
stato = st.session_state
stato.setdefault("analisi", {})     # hash foto -> campi precompilati (o messaggio d'errore)
stato.setdefault("salvati", set())  # hash delle foto già salvate
stato.setdefault("uploader", 0)     # cambiando la chiave si svuota il caricatore

# --- aggiunta -----------------------------------------------------------------
st.subheader("Aggiungi capi")
if stato.get("msg_armadio"):
    st.success(stato.pop("msg_armadio"))
if not ai.chiave_presente():
    st.caption("Senza chiave API i campi vanno compilati a mano.")
file = st.file_uploader("Foto dei capi", type=["jpg", "jpeg", "png", "webp"],
                        accept_multiple_files=True, key=f"up_{stato.uploader}")


def _campi_vuoti():
    return {"categoria": "top", "colori": [], "materiale": "", "formalita": 3,
            "stagione": [], "stile": "casual", "note": ""}


def scheda(f) -> bool:
    """Mostra la scheda di una foto. Restituisce True se la foto è ancora da salvare."""
    dati = f.getvalue()
    h = hashlib.sha1(dati).hexdigest()
    if h in stato.salvati:
        return False
    try:
        jpeg = ai.prepara_foto(dati)
    except ai.ErroreAI as e:
        st.error(f"{f.name}: {e}")
        return False

    if h not in stato.analisi:
        if ai.chiave_presente():
            with st.spinner(f"Analizzo {f.name}…"):
                try:
                    stato.analisi[h] = ai.analizza_capo(jpeg)
                except ai.ErroreAI as e:
                    stato.analisi[h] = {"errore": str(e)}
        else:
            stato.analisi[h] = {}
    analisi = stato.analisi[h]
    if "errore" in analisi:
        st.warning(f"{f.name}: analisi non riuscita ({analisi['errore']}). Compila a mano.")
    v = {**_campi_vuoti(), **{k: x for k, x in analisi.items() if k != "errore"}}

    col_foto, col_form = st.columns([1, 2])
    col_foto.image(jpeg, width="stretch")
    with col_form.form(f"form_{h}", border=True):
        categoria = st.selectbox("Categoria", config.CATEGORIE, index=config.CATEGORIE.index(v["categoria"])
                                 if v["categoria"] in config.CATEGORIE else 0)
        colori = st.text_input("Colori (separati da virgola)", ", ".join(v["colori"]))
        a, b = st.columns(2)
        materiale = a.text_input("Materiale", v["materiale"])
        stili = config.STILI if v["stile"] in config.STILI else config.STILI + [v["stile"]]
        stile = b.selectbox("Stile", stili, index=stili.index(v["stile"]))
        formalita = st.slider("Formalità", 1, 5, int(v["formalita"]))
        stagione = st.multiselect("Stagione", config.STAGIONI,
                                  [s for s in v["stagione"] if s in config.STAGIONI])
        note = st.text_input("Note", v["note"])
        if st.form_submit_button("💾 Salva", type="primary"):
            db.aggiungi_capo(c, {
                "foto": jpeg,
                "categoria": categoria,
                "colori": [x.strip() for x in colori.split(",") if x.strip()],
                "materiale": materiale.strip(), "formalita": formalita, "stagione": stagione,
                "stile": stile, "note": note.strip(),
            })
            stato.salvati.add(h)
            stato.msg_armadio = f"Capo salvato ({categoria})."
            return False
    return True


if file:
    da_salvare = [f for f in file if scheda(f)]
    if not da_salvare:
        # Tutte salvate: svuoto il caricatore per la prossima volta.
        stato.uploader += 1
        stato.salvati.clear()
        st.rerun()

# --- griglia ------------------------------------------------------------------
st.divider()
capi = db.capi(c)
st.subheader(f"Capi ({len(capi)})")
if not capi:
    st.info("L'armadio è vuoto: carica la prima foto qui sopra.")
    st.stop()

f1, f2, f3 = st.columns(3)
filtro_cat = f1.multiselect("Categoria", config.CATEGORIE, placeholder="Tutte")
filtro_col = f2.multiselect("Colore", sorted({x for k in capi for x in k["colori"]}), placeholder="Tutti")
filtro_stile = f3.multiselect("Stile", sorted({k["stile"] for k in capi if k["stile"]}), placeholder="Tutti")
visibili = [k for k in capi
            if (not filtro_cat or k["categoria"] in filtro_cat)
            and (not filtro_col or set(k["colori"]) & set(filtro_col))
            and (not filtro_stile or k["stile"] in filtro_stile)]
st.caption(f"{len(visibili)} capi mostrati")

COLONNE = 4
for i in range(0, len(visibili), COLONNE):
    for col, k in zip(st.columns(COLONNE), visibili[i:i + COLONNE]):
        with col.container(border=True):
            ui.foto(k, width="stretch")
            st.markdown(f"#{k['id']} " + ui.descrizione(k))
            dettagli = [x for x in (k["materiale"], ", ".join(k["stagione"]), k["note"]) if x]
            if dettagli:
                st.caption(" · ".join(dettagli))
            with st.popover("🗑️ Elimina"):
                st.write("Eliminare questo capo?")
                if st.button("Sì, elimina", key=f"del_{k['id']}", type="primary"):
                    db.elimina_capo(c, k["id"])
                    st.rerun()
