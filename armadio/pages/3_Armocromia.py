"""Armocromia indicativa da selfie e preferenze di stile."""
import html

import streamlit as st

import ai
import config
import db
import ui

st.set_page_config(page_title="Armocromia", page_icon="👗", layout="wide")
st.title("Armocromia e profilo")
c = ui.conn()
stato = st.session_state


def campioni(colori: list[dict]) -> None:
    celle = []
    for col in colori:
        hex_ = col.get("hex") or "#DDDDDD"
        celle.append(
            f'<div style="text-align:center;width:84px">'
            f'<div style="background:{html.escape(hex_)};height:56px;border-radius:8px;'
            f'border:1px solid rgba(0,0,0,.15)"></div>'
            f'<div style="font-size:.8rem;margin-top:4px">{html.escape(col.get("nome", ""))}</div></div>')
    st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:10px">{"".join(celle)}</div>',
                unsafe_allow_html=True)


profilo = db.profilo(c)

# --- stima da selfie ------------------------------------------------------------
with st.expander("📸 Nuova stima da selfie", expanded=not profilo["stagione_armocromia"]):
    st.markdown("""
**Per una foto utile:**
- luce naturale indiretta (vicino a una finestra, non al sole diretto);
- niente trucco, capelli raccolti;
- sfondo neutro (bianco o grigio), niente filtri.
""")
    st.caption("La stima da foto è indicativa: l'affidabilità è al massimo «media».")
    selfie = st.file_uploader("Da 1 a 3 selfie", type=["jpg", "jpeg", "png", "webp"],
                              accept_multiple_files=True)
    if selfie and len(selfie) > 3:
        st.warning("Uso solo le prime 3 foto.")
        selfie = selfie[:3]
    if st.button("Stima armocromia", type="primary", disabled=not (selfie and ai.chiave_presente())):
        try:
            with st.spinner("Analizzo i selfie…"):
                stato.stima = ai.stima_armocromia([ai.prepara_foto(f.getvalue()) for f in selfie])
        except ai.ErroreAI as e:
            st.error(str(e))
    if not ai.chiave_presente():
        st.caption("La stima richiede ANTHROPIC_API_KEY; puoi comunque compilare il profilo a mano qui sotto.")

stima = stato.get("stima")
if stima:
    st.info(f"**Nuova stima** (affidabilità {stima['affidabilita']}): {stima['stagione_armocromia']}, "
            f"in alternativa {stima['seconda_stagione']}. {stima['limiti']}\n\n"
            "Controlla i campi qui sotto e salva per aggiornare il profilo.")
    base = {**profilo, **{k: v for k, v in stima.items() if k != "limiti"}, "note_armocromia": stima["limiti"]}
else:
    base = profilo

# --- profilo modificabile ---------------------------------------------------------
st.subheader("Profilo")
if stato.get("messaggio"):
    st.success(stato.pop("messaggio"))
if base["palette_consigliata"]:
    st.markdown("**Palette consigliata**")
    campioni(base["palette_consigliata"])
if base["colori_da_evitare"]:
    st.markdown("**Colori da evitare**")
    campioni(base["colori_da_evitare"])


def _indice(opzioni, valore):
    return opzioni.index(valore) + 1 if valore in opzioni else 0


with st.form("profilo"):
    a, b, d = st.columns(3)
    stagioni = [""] + config.STAGIONI_ARMOCROMIA
    stagione = a.selectbox("Stagione", stagioni, index=_indice(config.STAGIONI_ARMOCROMIA, base["stagione_armocromia"]))
    seconda = b.selectbox("Seconda stagione più probabile", stagioni,
                          index=_indice(config.STAGIONI_ARMOCROMIA, base["seconda_stagione"]))
    sottotono = d.selectbox("Sottotono", [""] + config.SOTTOTONI, index=_indice(config.SOTTOTONI, base["sottotono"]))
    affidabilita = st.radio("Affidabilità", ["", "bassa", "media", "alta (consulenza)"], horizontal=True,
                            index=_indice(["bassa", "media", "alta (consulenza)"], base["affidabilita"]),
                            help="Da foto al massimo «media». Usa «alta» solo se inserisci i dati di una consulenza vera.")
    p1, p2 = st.columns(2)
    palette = p1.text_area("Palette consigliata (una riga per colore: nome #RRGGBB)",
                           db.colori_a_testo(base["palette_consigliata"]), height=220)
    evitare = p2.text_area("Colori da evitare (una riga per colore: nome #RRGGBB)",
                           db.colori_a_testo(base["colori_da_evitare"]), height=220)
    note = st.text_input("Note sull'armocromia", base["note_armocromia"])
    preferenze = st.text_area("Le mie preferenze di stile", base["preferenze_stile"],
                              placeholder="es. comoda, niente tacchi alti, mi piacciono i colori neutri")
    if st.form_submit_button("💾 Salva profilo", type="primary"):
        db.aggiorna_profilo(
            c, stagione_armocromia=stagione, seconda_stagione=seconda, sottotono=sottotono,
            affidabilita=affidabilita, palette_consigliata=db.testo_a_colori(palette),
            colori_da_evitare=db.testo_a_colori(evitare), note_armocromia=note.strip(),
            preferenze_stile=preferenze.strip(),
        )
        stato.pop("stima", None)
        stato.messaggio = "Profilo salvato."
        st.rerun()
