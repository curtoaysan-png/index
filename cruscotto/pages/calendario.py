"""Calendario: vista settimanale, impegni, import iCal e assistente."""
import urllib.request
from datetime import date, datetime, time, timedelta

import streamlit as st
from streamlit_calendar import calendar

import assistente
import config
import db
import logica
from componenti import CSS_CALENDARIO, COLORI, eventi_calendario, prepara_sessione

conn = db.connetti()
oggi = date.today()
st.session_state.setdefault("lunedi", logica.lunedi_di(oggi))
st.session_state.setdefault("cal_ver", 0)
lunedi: date = st.session_state["lunedi"]
domenica = lunedi + timedelta(days=6)

st.title("Calendario")

# ---------------------------------------------------------------- navigazione settimana
c1, c2, c3, c4 = st.columns([1.3, 0.8, 1.3, 3.6])
if c1.button("◀ Precedente"):
    st.session_state["lunedi"] = lunedi - timedelta(days=7)
    st.rerun()
if c2.button("Oggi"):
    st.session_state["lunedi"] = logica.lunedi_di(oggi)
    st.rerun()
if c3.button("Successiva ▶"):
    st.session_state["lunedi"] = lunedi + timedelta(days=7)
    st.rerun()
c4.markdown(f"**Settimana {lunedi:%d/%m} – {domenica:%d/%m/%Y}**")

impegni = db.impegni(conn)
fronti = db.fronti(conn)
nomi_fronti = {f["id"]: f["nome"] for f in fronti}
occ = logica.espandi_impegni(impegni, lunedi, lunedi + timedelta(days=7))

# Blocchi proposti dall'assistente (anteprima, milestone 4)
proposta = st.session_state.get("proposta")
proposti = []
if proposta and proposta["lunedi"] == lunedi:
    proposti = [b for i, b in enumerate(proposta["validi"]) if st.session_state.get(f"tieni_{proposta['piano_id']}_{i}", True)]

# ---------------------------------------------------------------- calendario
opzioni = {
    "initialView": "timeGridWeek",
    "initialDate": str(lunedi),
    "firstDay": 1,
    # Oggetto locale passato direttamente: il componente non include i file di lingua.
    "locale": {"code": "it", "week": {"dow": 1, "doy": 4}},
    "headerToolbar": {"left": "", "center": "", "right": "timeGridWeek,timeGridDay"},
    "buttonText": {"week": "Settimana", "day": "Giorno"},
    "dayHeaderFormat": {"weekday": "short", "day": "numeric", "month": "numeric"},
    "slotMinTime": "07:00:00",
    "slotMaxTime": "23:30:00",
    "slotLabelFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
    "eventTimeFormat": {"hour": "2-digit", "minute": "2-digit", "hour12": False},
    "allDaySlot": False,
    "navLinks": True,
    "nowIndicator": True,
    "height": "auto",
}
eventi = eventi_calendario(occ, proposti)
stato = calendar(
    events=eventi, options=opzioni, custom_css=CSS_CALENDARIO, callbacks=["eventClick"],
    key=f"cal_{lunedi}_{st.session_state['cal_ver']}_{hash(str(eventi))}",
)
legenda = " &nbsp; ".join(f'<span style="color:{c}">■</span> {t}' for t, c in COLORI.items())
st.markdown(legenda + " &nbsp; <span style='color:#3f7d4f'>⬚</span> proposta", unsafe_allow_html=True)

if stato and stato.get("callback") == "eventClick":
    props = stato["eventClick"]["event"].get("extendedProps", {})
    st.session_state["cal_ver"] += 1  # azzera il clic
    if props.get("tipo") == "blocco di lavoro" and props.get("fronte_id"):
        prepara_sessione(props["fronte_id"], props["durata"])
    elif props.get("impegno_id"):
        st.session_state["modifica_id"] = props["impegno_id"]
        st.rerun()

# ---------------------------------------------------------------- riepilogo settimana
sessioni = db.sessioni_chiuse(conn, dal=lunedi - timedelta(days=14))
r = logica.riepilogo_settimana(occ, sessioni, lunedi)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Ore impegni fissi", logica.num(round(r["ore_fisse"], 1)))
m2.metric(f"Ore libere ({config.GIORNO_INIZIO}–{config.GIORNO_FINE})", logica.num(round(r["ore_libere"], 1)))
m3.metric("Ore blocchi pianificati", logica.num(round(r["ore_blocchi"], 1)))
m4.metric("Ore sessioni fatte", logica.num(round(r["ore_sessioni"], 1)))

# ---------------------------------------------------------------- assistente
st.divider()
st.markdown("#### Assistente")
settimana_corrente = lunedi == logica.lunedi_di(oggi)
fine_settimana_dt = datetime.combine(lunedi + timedelta(days=7), time())
if not assistente.chiave_presente():
    st.caption("Assistente non configurato: serve la variabile d'ambiente ANTHROPIC_API_KEY (vedi README).")


def pianifica(tipo: str):
    adesso = datetime.now().replace(second=0, microsecond=0)
    if fine_settimana_dt <= adesso:
        st.error("Questa settimana è già passata.")
        return
    dati = logica.costruisci_input(adesso, lunedi, tipo, fronti, sessioni, impegni,
                                   db.preferenze(conn)["testo_regole"])
    try:
        with st.spinner("L'assistente sta preparando il piano…"):
            risposta = assistente.chiedi_piano(dati)
    except assistente.ErroreAssistente as e:
        st.error(str(e))
        return
    # Verifica indipendente dal modello: niente blocchi sopra impegni o fuori periodo.
    da = max(adesso, datetime.combine(lunedi, time()))
    validi, scartati = logica.valida_blocchi(
        risposta["blocchi"], logica.occupati_per_piano(occ, adesso),
        {f["nome"] for f in fronti}, da, fine_settimana_dt,
    )
    proposta = {**risposta, "validi": validi, "scartati": scartati}
    piano_id = db.crea_piano(conn, lunedi, tipo, dati, proposta, risposta["spiegazione"])
    st.session_state["proposta"] = {
        "piano_id": piano_id, "lunedi": lunedi, "tipo": tipo, "da": da,
        "validi": validi, "scartati": scartati,
        "spiegazione": risposta["spiegazione"], "avvisi": risposta["avvisi"],
    }
    st.rerun()


b1, b2, _ = st.columns([1, 1, 2])
if b1.button("Organizza la settimana"):
    pianifica("settimana intera")
if b2.button("Ripianifica da oggi", disabled=not settimana_corrente,
             help="Disponibile solo per la settimana in corso."):
    pianifica("ripianifica da oggi")

if proposta and proposta["lunedi"] == lunedi:
    pid = proposta["piano_id"]
    with st.container(border=True):
        st.markdown(f"**Proposta ({proposta['tipo']})** — anteprima tratteggiata nel calendario. "
                    "Nulla viene aggiunto finché non accetti.")
        if proposta["spiegazione"]:
            st.write(proposta["spiegazione"])
        for avviso in proposta["avvisi"]:
            st.warning(avviso)
        if proposta["scartati"]:
            st.caption("Blocchi scartati dalla verifica automatica:")
            for s in proposta["scartati"]:
                st.caption(f"– {s.get('fronte', '?')} {s.get('inizio', '')}–{s.get('fine', '')}: {s['motivo']}")
        if not proposta["validi"]:
            st.info("Nessun blocco valido da aggiungere.")
        for i, b in enumerate(proposta["validi"]):
            ini, fin = logica.a_dt(b["inizio"]), logica.a_dt(b["fine"])
            st.checkbox(
                f"{logica.GIORNI[ini.weekday()]} {ini:%d/%m %H:%M}–{fin:%H:%M} · {b['fronte']}"
                + (f" · {b['attivita']}" if b["attivita"] else ""),
                value=True, key=f"tieni_{pid}_{i}",
            )
        per_nome = {f["nome"]: f for f in fronti}

        def accetta(blocchi):
            db.accetta_blocchi(conn, pid, blocchi, per_nome, proposta["da"], fine_settimana_dt)
            st.session_state.pop("proposta")
            st.session_state["msg_piano"] = f"Aggiunti {len(blocchi)} blocchi al calendario."
            st.rerun()

        a1, a2, a3 = st.columns(3)
        if a1.button("Accetta tutto", type="primary", disabled=not proposta["validi"]):
            accetta(proposta["validi"])
        if a2.button("Accetta i selezionati", disabled=not proposta["validi"]):
            accetta(proposti)
        if a3.button("Rifiuta"):
            db.rifiuta_piano(conn, pid)
            st.session_state.pop("proposta")
            st.rerun()
        if proposta["tipo"] == "ripianifica da oggi" or proposta["da"] > datetime.combine(lunedi, time()):
            st.caption(f"Accettando, i blocchi dell'assistente dopo il {proposta['da']:%d/%m %H:%M} "
                       "vengono sostituiti; quelli passati restano.")
        else:
            st.caption("Accettando, i blocchi dell'assistente di questa settimana vengono sostituiti.")

if msg := st.session_state.pop("msg_piano", None):
    st.success(msg)


# ---------------------------------------------------------------- aggiunta e modifica
def campi_impegno(pref: str, v: dict | None):
    """Campi del modulo impegno. `v` = valori esistenti (modifica) o None (nuovo)."""
    v = v or {}
    ini = logica.a_dt(v["inizio"]) if v.get("inizio") else datetime.combine(oggi, time(9))
    fin = logica.a_dt(v["fine"]) if v.get("fine") else datetime.combine(oggi, time(10, 30))
    titolo = st.text_input("Titolo", v.get("titolo", ""), key=f"{pref}_titolo")
    tipi = db.TIPI_IMPEGNO
    tipo = st.selectbox("Tipo", tipi, index=tipi.index(v.get("tipo", "turno")), key=f"{pref}_tipo")
    a, b, c = st.columns(3)
    giorno = a.date_input("Giorno", ini.date(), key=f"{pref}_giorno", format="DD/MM/YYYY")
    ora_ini = b.time_input("Inizio", ini.time(), key=f"{pref}_ini", step=900)
    ora_fin = c.time_input("Fine", fin.time(), key=f"{pref}_fin", step=900)
    fronte_id = None
    if tipo == "blocco di lavoro":
        ids = list(nomi_fronti)
        if not ids:
            st.warning("Nessun fronte attivo.")
        else:
            fronte_id = st.selectbox(
                "Fronte", ids, index=ids.index(v["fronte_id"]) if v.get("fronte_id") in ids else 0,
                format_func=nomi_fronti.get, key=f"{pref}_fronte",
            )
    settimanale = st.checkbox("Ogni settimana", v.get("ricorrenza") == "settimanale", key=f"{pref}_ric")
    ric_fine = None
    if settimanale:
        rf = logica.a_data(v["ricorrenza_fine"]) if v.get("ricorrenza_fine") else None
        ric_fine = st.date_input("Fino al (facoltativo)", rf, key=f"{pref}_ricfine", format="DD/MM/YYYY")
    return {
        "titolo": titolo or (nomi_fronti.get(fronte_id, "") if fronte_id else ""),
        "tipo": tipo,
        "inizio": datetime.combine(giorno, ora_ini).isoformat(timespec="seconds"),
        "fine": datetime.combine(giorno, ora_fin).isoformat(timespec="seconds"),
        "ricorrenza": "settimanale" if settimanale else "nessuna",
        "ricorrenza_fine": ric_fine,
        "fronte_id": fronte_id,
    }


st.divider()
col_a, col_b = st.columns(2)
with col_a:
    st.markdown("#### Nuovo impegno")
    nuovo = campi_impegno("nuovo", None)
    if st.button("Aggiungi", type="primary"):
        try:
            db.salva_impegno(conn, **nuovo)
            st.rerun()
        except ValueError as e:
            st.error(str(e))

with col_b:
    st.markdown("#### Modifica impegno")
    serie = {}
    for o in occ:
        serie.setdefault(o["id"], o)
    scelto = st.session_state.get("modifica_id")
    if scelto and scelto not in serie and db.impegno(conn, scelto):
        serie[scelto] = {**db.impegno(conn, scelto), "inizio_dt": logica.a_dt(db.impegno(conn, scelto)["inizio"])}
    if not serie:
        st.caption("Nessun impegno in questa settimana.")
    else:
        ids = list(serie)
        imp_id = st.selectbox(
            "Impegno", ids, index=ids.index(scelto) if scelto in ids else 0,
            format_func=lambda i: f"{serie[i]['inizio_dt']:%a %d/%m %H:%M} — {serie[i]['titolo']} ({serie[i]['tipo']})",
        )
        st.session_state["modifica_id"] = imp_id
        valori = db.impegno(conn, imp_id)
        if valori["ricorrenza"] == "settimanale":
            st.caption("Impegno settimanale: le modifiche valgono per tutta la serie.")
        if valori["origine"] != "manuale":
            st.caption(f"Origine: {valori['origine']}.")
        mod = campi_impegno(f"mod{imp_id}", valori)
        b1, b2 = st.columns(2)
        if b1.button("Salva modifiche"):
            try:
                db.salva_impegno(conn, **mod, origine=valori["origine"], impegno_id=imp_id)
                st.rerun()
            except ValueError as e:
                st.error(str(e))
        if b2.button("Elimina"):
            db.elimina_impegno(conn, imp_id)
            st.session_state.pop("modifica_id", None)
            st.rerun()

# ---------------------------------------------------------------- iCal
st.divider()
with st.expander("Import da Google Calendar (iCal, solo lettura)"):
    pref = db.preferenze(conn)
    url = st.text_input("Indirizzo iCal segreto", pref.get("ical_url") or "", type="password",
                        help="Google Calendar → Impostazioni del calendario → Indirizzo segreto in formato iCal.")
    st.caption("Importa gli eventi di questa settimana come impegni fissi. Sostituisce solo gli eventi "
               "già importati da iCal; gli impegni manuali e dell'assistente non vengono toccati. "
               "Gli eventi di un giorno intero sono esclusi.")
    if st.button("Aggiorna da iCal", disabled=not url.strip()):
        try:
            db.salva_preferenze(conn, ical_url=url.strip())
            with urllib.request.urlopen(logica.normalizza_url_ical(url), timeout=20) as risposta:
                testo = risposta.read()
            eventi_ical = logica.eventi_da_ical(testo, lunedi, lunedi + timedelta(days=7))
            n = db.sostituisci_ical(
                conn, eventi_ical, datetime.combine(lunedi, time()),
                datetime.combine(lunedi + timedelta(days=7), time()),
            )
            st.session_state["msg_ical"] = f"Importati {n} eventi da iCal."
            st.rerun()
        except Exception as e:  # rete, URL o file non valido
            st.error(f"Import non riuscito: {e}")
    if msg := st.session_state.pop("msg_ical", None):
        st.success(msg)
