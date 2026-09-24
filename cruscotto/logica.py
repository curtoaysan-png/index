"""Calcoli puri e testabili: ritmo, proiezione, calendario, validazione del piano."""
import json
import math
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta

import config

GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


# ---------------------------------------------------------------- utilità

def a_data(x) -> date:
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    return datetime.fromisoformat(str(x)).date()


def a_dt(x) -> datetime:
    if isinstance(x, datetime):
        return x
    if isinstance(x, date):
        return datetime.combine(x, time())
    return datetime.fromisoformat(str(x))


def lunedi_di(d) -> date:
    d = a_data(d)
    return d - timedelta(days=d.weekday())


def num(n) -> str:
    """Formato italiano: 1300 -> '1.300'."""
    if n is None:
        return "—"
    if isinstance(n, float) and not n.is_integer():
        testo = f"{n:,.2f}".rstrip("0").rstrip(".")
        return testo.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{int(n):,}".replace(",", ".")


def data_it(d) -> str:
    d = a_data(d)
    return f"{GIORNI[d.weekday()]} {d.day:02d}/{d.month:02d}/{d.year}"


# ---------------------------------------------------------------- ritmo e proiezione

def ritmo_medio(sessioni, fronte_id, oggi: date, giorni: int = 7) -> float:
    """Output medio al giorno negli ultimi `giorni` giorni (oggi compreso)."""
    inizio = oggi - timedelta(days=giorni - 1)
    totale = sum(
        (s.get("output") or 0)
        for s in sessioni
        if s["fronte_id"] == fronte_id and s.get("fine") and inizio <= a_data(s["fine"]) <= oggi
    )
    return totale / giorni


def colore_proiezione(data_stimata: date | None, scadenza: date) -> str:
    """Verde prima della scadenza, giallo entro 3 giorni dalla scadenza, rosso dopo."""
    if data_stimata is None or data_stimata > scadenza:
        return "rosso"
    if data_stimata >= scadenza - timedelta(days=3):
        return "giallo"
    return "verde"


def proiezione(fronte: dict, sessioni, oggi: date) -> dict:
    """Ritmo attuale, ritmo necessario, data stimata e colore per un fronte."""
    scadenza = a_data(fronte["scadenza"])
    giorni_mancanti = (scadenza - oggi).days
    ritmo = ritmo_medio(sessioni, fronte["id"], oggi, 7)
    ris = {
        "giorni_mancanti": giorni_mancanti,
        "ritmo_attuale": ritmo,
        "ritmo_14": ritmo_medio(sessioni, fronte["id"], oggi, 14),
        "ritmo_necessario": None,
        "rimanente": None,
        "data_stimata": None,
        "colore": "grigio",
        "completato": False,
    }
    obiettivo = fronte.get("obiettivo")
    if obiettivo is None:
        return ris  # obiettivo da definire: nessuna proiezione
    rimanente = max(obiettivo - (fronte.get("attuale") or 0), 0)
    ris["rimanente"] = rimanente
    if rimanente == 0:
        ris.update(completato=True, data_stimata=oggi, colore="verde", ritmo_necessario=0)
        return ris
    ris["ritmo_necessario"] = rimanente / max(giorni_mancanti, 1)
    if ritmo > 0:
        ris["data_stimata"] = oggi + timedelta(days=math.ceil(rimanente / ritmo))
    ris["colore"] = colore_proiezione(ris["data_stimata"], scadenza)
    return ris


def catena_giorni(sessioni, oggi: date, n: int = 14) -> list[tuple[date, bool]]:
    """Ultimi n giorni (dal più vecchio): True se quel giorno c'è stata almeno una sessione."""
    giorni_attivi = {a_data(s["inizio"]) for s in sessioni if s.get("fine")}
    return [(g, g in giorni_attivi) for g in (oggi - timedelta(days=i) for i in range(n - 1, -1, -1))]


def fronte_piu_vicino(fronti: list[dict]) -> dict | None:
    """Fronte attivo con la scadenza più vicina, escludendo quelli con l'obiettivo raggiunto."""
    aperti = [f for f in fronti if f["attivo"]
              and (f.get("obiettivo") is None or (f.get("attuale") or 0) < f["obiettivo"])]
    return min(aperti, key=lambda f: f["scadenza"]) if aperti else None


def normalizza_url_ical(url: str) -> str:
    """Google a volte mostra l'indirizzo come webcal://: va scaricato in https."""
    url = url.strip()
    if url.lower().startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    return url


# ---------------------------------------------------------------- calendario

def espandi_impegni(impegni, da: date, a: date) -> list[dict]:
    """Occorrenze degli impegni tra `da` (incluso) e `a` (escluso).

    Gli impegni settimanali si ripetono ogni 7 giorni fino a `ricorrenza_fine` (inclusa).
    Ogni occorrenza ha `inizio_dt` e `fine_dt` come datetime.
    """
    da_dt, a_dt_ = datetime.combine(da, time()), datetime.combine(a, time())
    ris = []
    for i in impegni:
        inizio, fine = a_dt(i["inizio"]), a_dt(i["fine"])
        durata = fine - inizio
        if i.get("ricorrenza") == "settimanale":
            limite = a_data(i["ricorrenza_fine"]) if i.get("ricorrenza_fine") else a
            k = max(0, (da - inizio.date()).days // 7 - 1)
            while True:
                occ = inizio + timedelta(weeks=k)
                if occ >= a_dt_ or occ.date() > limite:
                    break
                if occ + durata > da_dt:
                    ris.append({**i, "inizio_dt": occ, "fine_dt": occ + durata})
                k += 1
        elif inizio < a_dt_ and fine > da_dt:
            ris.append({**i, "inizio_dt": inizio, "fine_dt": fine})
    ris.sort(key=lambda o: o["inizio_dt"])
    return ris


def sottrai_intervalli(finestra, occupati):
    """Parti libere di `finestra` (inizio, fine) togliendo gli intervalli occupati."""
    liberi = [finestra]
    for o_ini, o_fin in sorted(occupati):
        nuovi = []
        for l_ini, l_fin in liberi:
            if o_fin <= l_ini or o_ini >= l_fin:
                nuovi.append((l_ini, l_fin))
                continue
            if o_ini > l_ini:
                nuovi.append((l_ini, o_ini))
            if o_fin < l_fin:
                nuovi.append((o_fin, l_fin))
        liberi = nuovi
    return [(i, f) for i, f in liberi if f > i]


def fasce_libere(occorrenze_occupate, lunedi: date, dal: datetime | None = None,
                 ora_inizio=config.GIORNO_INIZIO, ora_fine=config.GIORNO_FINE) -> dict[date, list]:
    """Fasce libere per ogni giorno della settimana, nella fascia oraria configurata."""
    ris = {}
    occupati = [(o["inizio_dt"], o["fine_dt"]) for o in occorrenze_occupate]
    for g in range(7):
        giorno = lunedi + timedelta(days=g)
        ini = datetime.combine(giorno, time(ora_inizio))
        fin = datetime.combine(giorno, time(ora_fine))
        if dal is not None:
            ini = max(ini, dal)
        ris[giorno] = sottrai_intervalli((ini, fin), occupati) if fin > ini else []
    return ris


def ore(intervalli) -> float:
    return sum((f - i).total_seconds() for i, f in intervalli) / 3600


def riepilogo_settimana(occorrenze, sessioni, lunedi: date) -> dict:
    """Ore fisse, ore libere, ore di blocchi pianificati e ore di sessioni fatte."""
    domenica_fine = datetime.combine(lunedi + timedelta(days=7), time())
    lun = datetime.combine(lunedi, time())

    def taglia(o):
        return (max(o["inizio_dt"], lun), min(o["fine_dt"], domenica_fine))

    fissi = [o for o in occorrenze if o["fisso"]]
    blocchi = [o for o in occorrenze if o["tipo"] == "blocco di lavoro"]
    libere = fasce_libere(fissi, lunedi)
    fatte = [
        (a_dt(s["inizio"]), a_dt(s["fine"])) for s in sessioni
        if s.get("fine") and lunedi <= a_data(s["inizio"]) < lunedi + timedelta(days=7)
    ]
    return {
        "ore_fisse": ore([taglia(o) for o in fissi]),
        "ore_libere": ore([i for v in libere.values() for i in v]),
        "ore_blocchi": ore([taglia(o) for o in blocchi]),
        "ore_sessioni": ore(fatte),
    }


# ---------------------------------------------------------------- assistente

def occupati_per_piano(occorrenze, adesso: datetime) -> list[dict]:
    """Occorrenze che l'assistente non può toccare.

    Tutto tranne i blocchi dell'assistente futuri (che il nuovo piano sostituisce).
    """
    return [
        o for o in occorrenze
        if not (o["origine"] == "assistente" and o["inizio_dt"] >= adesso)
    ]


def costruisci_input(adesso: datetime, lunedi: date, tipo: str, fronti, sessioni, impegni,
                     testo_regole: str) -> dict:
    """Dati inviati all'assistente (salvati anche in piani.input_json)."""
    oggi = adesso.date()
    settimana = espandi_impegni(impegni, lunedi, lunedi + timedelta(days=7))
    occupati = occupati_per_piano(settimana, adesso)
    dal = max(adesso, datetime.combine(lunedi, time()))
    libere = fasce_libere(occupati, lunedi, dal=dal)

    fronti_dati = []
    for f in fronti:
        p = proiezione(f, sessioni, oggi)
        fronti_dati.append({
            "nome": f["nome"],
            "scadenza": f["scadenza"],
            "unita": f["unita"],
            "obiettivo": f["obiettivo"],
            "attuale": f["attuale"],
            "giorni_mancanti": p["giorni_mancanti"],
            "ritmo_necessario_al_giorno": round(p["ritmo_necessario"], 1) if p["ritmo_necessario"] is not None else None,
            "ritmo_reale_7_giorni": round(p["ritmo_attuale"], 1),
            "ritmo_reale_14_giorni": round(p["ritmo_14"], 1),
            "data_stimata": str(p["data_stimata"]) if p["data_stimata"] else None,
            "proiezione": p["colore"],
        })

    inizio_14 = oggi - timedelta(days=13)
    sess_14 = [s for s in sessioni if s.get("fine") and a_data(s["inizio"]) >= inizio_14]
    blocchi_14 = [
        o for o in espandi_impegni(impegni, inizio_14, oggi + timedelta(days=1))
        if o["tipo"] == "blocco di lavoro" and o["inizio_dt"] < adesso
    ]
    per_giorno = []
    for g in range(14):
        giorno = inizio_14 + timedelta(days=g)
        pian = [o for o in blocchi_14 if o["inizio_dt"].date() == giorno]
        fatte = [s for s in sess_14 if a_data(s["inizio"]) == giorno]
        if pian or fatte:
            per_giorno.append({
                "data": str(giorno),
                "blocchi_pianificati": [o.get("fronte") or o["titolo"] for o in pian],
                "sessioni_fatte": len(fatte),
            })

    fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M")  # noqa: E731
    return {
        "adesso": fmt(adesso),
        "tipo_piano": tipo,
        "settimana": {"lunedi": str(lunedi), "domenica": str(lunedi + timedelta(days=6))},
        "pianificabile_dal": fmt(dal),
        "impegni_fissi_e_esistenti": [
            {"titolo": o["titolo"], "tipo": o["tipo"], "inizio": fmt(o["inizio_dt"]),
             "fine": fmt(o["fine_dt"])}
            for o in occupati
        ],
        "fasce_libere": {
            str(g): [[fmt(i), fmt(f)] for i, f in v] for g, v in libere.items() if v
        },
        "fronti": fronti_dati,
        "sessioni_ultimi_14_giorni": [
            {"data": str(a_data(s["inizio"])), "fronte": s["fronte"],
             "durata_prevista_min": s["durata_prevista_min"],
             "durata_effettiva_min": round((a_dt(s["fine"]) - a_dt(s["inizio"])).total_seconds() / 60),
             "output": s["output"]}
            for s in sess_14
        ],
        "pianificati_vs_fatti": per_giorno,
        "preferenze": testo_regole,
    }


def estrai_json(testo: str) -> dict:
    """Estrae e controlla il JSON della risposta. Solleva ValueError se non valido."""
    t = testo.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    ini, fin = t.find("{"), t.rfind("}")
    if ini == -1 or fin == -1:
        raise ValueError("Nessun oggetto JSON nella risposta.")
    try:
        dati = json.loads(t[ini:fin + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON non valido: {e}") from e
    if not isinstance(dati.get("blocchi"), list):
        raise ValueError("Manca l'elenco 'blocchi'.")
    dati.setdefault("spiegazione", "")
    dati.setdefault("avvisi", [])
    if not isinstance(dati["avvisi"], list):
        dati["avvisi"] = [str(dati["avvisi"])]
    return dati


def valida_blocchi(blocchi, occorrenze_occupate, nomi_fronti, da: datetime, a: datetime):
    """Scarta i blocchi non validi senza fidarsi del modello.

    Restituisce (validi, scartati); ogni scartato ha un campo 'motivo'.
    """
    validi, scartati = [], []
    occupati = [(o["inizio_dt"], o["fine_dt"], o["titolo"]) for o in occorrenze_occupate]
    for b in blocchi:
        def scarta(motivo):
            scartati.append({**b, "motivo": motivo})

        if not isinstance(b, dict):
            scartati.append({"blocco": str(b), "motivo": "formato non valido"})
            continue
        if b.get("fronte") not in nomi_fronti:
            scarta(f"fronte sconosciuto: {b.get('fronte')}")
            continue
        try:
            ini, fin = a_dt(b["inizio"]), a_dt(b["fine"])
        except (KeyError, ValueError, TypeError):
            scarta("orari non leggibili")
            continue
        if ini.tzinfo or fin.tzinfo:
            ini, fin = ini.replace(tzinfo=None), fin.replace(tzinfo=None)
        if fin <= ini:
            scarta("la fine è prima dell'inizio")
            continue
        if ini < da or fin > a:
            scarta("fuori dal periodo pianificabile")
            continue
        conflitto = next((t for oi, of, t in occupati if ini < of and fin > oi), None)
        if conflitto:
            scarta(f"si sovrappone a un impegno: {conflitto}")
            continue
        if any(ini < a_dt(v["fine"]) and fin > a_dt(v["inizio"]) for v in validi):
            scarta("si sovrappone a un altro blocco proposto")
            continue
        validi.append({
            "fronte": b["fronte"],
            "inizio": ini.isoformat(timespec="minutes"),
            "fine": fin.isoformat(timespec="minutes"),
            "attivita": str(b.get("attivita") or ""),
        })
    return validi, scartati


def storico_piani(piani, impegni, sessioni) -> list[dict]:
    """Per settimana: piani, ripianificazioni, blocchi pianificati e sessioni fatte."""
    per_sett = defaultdict(list)
    for p in piani:
        per_sett[p["settimana"]].append(p)
    ris = []
    for sett in sorted(per_sett, reverse=True):
        lun = a_data(sett)
        fine = lun + timedelta(days=7)
        blocchi = [o for o in espandi_impegni(impegni, lun, fine) if o["tipo"] == "blocco di lavoro"]
        fatte = [s for s in sessioni if s.get("fine") and lun <= a_data(s["inizio"]) < fine]
        ps = per_sett[sett]
        ris.append({
            "settimana": sett,
            "piani": len(ps),
            "ripianificazioni": sum(p["tipo"] == "ripianifica da oggi" for p in ps),
            "accettati": sum(p["stato"] == "accettato" for p in ps),
            "rifiutati": sum(p["stato"] == "rifiutato" for p in ps),
            "blocchi_pianificati": len(blocchi),
            "sessioni_fatte": len(fatte),
            "elenco": ps,
        })
    return ris


# ---------------------------------------------------------------- iCal

def tipo_da_titolo(titolo: str) -> str:
    t = titolo.lower()
    for chiave, tipo in (("turno", "turno"), ("lezione", "lezione"), ("esame", "esame")):
        if chiave in t:
            return tipo
    return "personale"


def eventi_da_ical(testo: bytes | str, da: date, a: date) -> list[dict]:
    """Eventi (anche ricorrenti) tra `da` e `a`, in ora locale. Gli eventi di un giorno intero sono esclusi."""
    import icalendar
    import recurring_ical_events

    cal = icalendar.Calendar.from_ical(testo)
    ris = []
    for ev in recurring_ical_events.of(cal).between(da, a):
        ini = ev.get("DTSTART").dt
        fin = ev.get("DTEND").dt if ev.get("DTEND") else None
        if not isinstance(ini, datetime):
            continue  # evento di un giorno intero
        if fin is None:
            fin = ini + (ev.get("DURATION").dt if ev.get("DURATION") else timedelta(hours=1))
        if ini.tzinfo:
            ini = ini.astimezone().replace(tzinfo=None)
        if fin.tzinfo:
            fin = fin.astimezone().replace(tzinfo=None)
        titolo = str(ev.get("SUMMARY") or "Impegno")
        ris.append({
            "titolo": titolo,
            "tipo": tipo_da_titolo(titolo),
            "inizio": ini.isoformat(timespec="seconds"),
            "fine": fin.isoformat(timespec="seconds"),
        })
    return ris


# ---------------------------------------------------------------- acquisti

def attesa_residua(aggiunto_il, adesso: datetime, ore_attesa: int = 48) -> timedelta:
    """Tempo che manca allo sblocco (zero o negativo = sbloccato)."""
    return a_dt(aggiunto_il) + timedelta(hours=ore_attesa) - adesso


def riepilogo_acquisti_mese(acquisti, anno: int, mese: int) -> dict:
    ris = {"comprato": 0.0, "rinunciato": 0.0, "per_categoria": defaultdict(lambda: {"comprato": 0.0, "rinunciato": 0.0})}
    for a in acquisti:
        if a["stato"] not in ("comprato", "rinunciato") or not a.get("deciso_il"):
            continue
        d = a_data(a["deciso_il"])
        if (d.year, d.month) != (anno, mese):
            continue
        ris[a["stato"]] += a["prezzo"]
        ris["per_categoria"][a["categoria"]][a["stato"]] += a["prezzo"]
    ris["per_categoria"] = dict(ris["per_categoria"])
    return ris
