"""TV TCL più veloce: disattiva servizi e pubblicità inutili via ADB, con possibilità di annullare.

Avvio: `python tv.py` (su Windows doppio clic su avvia.bat). Serve solo Python, nessuna libreria.
Ogni pacchetto disattivato finisce in data/disattivati.txt, da cui il menu lo può ripristinare.
"""
import platform
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent
DATI = CARTELLA / "data"
FILE_IP = DATI / "tv.txt"
REGISTRO = DATI / "disattivati.txt"
PORTA = 5555

# Pacchetti che non vanno mai toccati: senza di loro la TV non si avvia, non ha la Home,
# non riceve il telecomando o non mostra gli ingressi HDMI.
PROTETTI = (
    "launcher", "settings", "systemui", "inputmethod", "keyboard", "leanbackime", "ime",
    "gms", "gsf", "vending", "packageinstaller", "permissioncontroller", "provider",
    "framework", "tvinput", "hdmi", "tuner", "bluetooth", "wifi", "remote", "rcu",
    "input", "audio", "display", "picture", "sound", "power", "ota", "systemupdate",
    "setupwizard", "oobe", "shell", "webview", "media", "storage", "network", "cec",
)

# Parole che indicano pubblicità, raccomandazioni, telemetria o app di contorno.
# Le parole corte valgono solo come segmento intero del nome (es. "ad" non deve
# riconoscere "download" o "android").
CANDIDATI = {
    "pubblicità": ("ad", "ads", "adsdk", "advert", "advertising", "adservice", "banner", "promo"),
    "raccomandazioni": ("recommend", "recommendation", "suggest", "channel", "homeshare"),
    "telemetria": ("report", "feedback", "analytics", "statistic", "statistics", "logcollect",
                   "bigdata", "tracker", "tracking", "collect", "dataservice", "userexperience"),
    "app di contorno": ("appmarket", "appstore", "gamecenter", "shop", "demo", "tips", "guide",
                        "manual", "weather", "news", "store", "magicconnect", "screenshare"),
}
PAROLE_CORTE = 4


def segmenti(pacchetto: str) -> list[str]:
    return [s for s in re.split(r"[._\-]", pacchetto.lower()) if s]


def protetto(pacchetto: str) -> bool:
    return pacchetto == "android" or any(p in pacchetto.lower() for p in PROTETTI)


def motivo(pacchetto: str) -> str | None:
    """Perché il pacchetto è un candidato da disattivare, oppure None."""
    if protetto(pacchetto):
        return None
    nome, parti = pacchetto.lower(), segmenti(pacchetto)
    for categoria, parole in CANDIDATI.items():
        for parola in parole:
            if len(parola) <= PAROLE_CORTE:
                if parola in parti:
                    return categoria
            elif parola in nome:
                return categoria
    return None


def da_valutare(pacchetto: str) -> bool:
    """Pacchetti TCL non protetti e non riconosciuti: da guardare a mano."""
    return pacchetto.lower().startswith(("com.tcl.", "com.tcl_", "com.tclhz.")) \
        and not protetto(pacchetto) and motivo(pacchetto) is None


# ---------- ADB ----------

def url_platform_tools() -> str:
    sistema = {"Windows": "windows", "Darwin": "darwin"}.get(platform.system(), "linux")
    return f"https://dl.google.com/android/repository/platform-tools-latest-{sistema}.zip"


def trova_adb() -> str | None:
    locale = CARTELLA / "platform-tools" / ("adb.exe" if platform.system() == "Windows" else "adb")
    if locale.exists():
        return str(locale)
    return shutil.which("adb")


def scarica_adb() -> str | None:
    print("ADB non trovato. Lo scarico dal sito di Google (circa 10 MB)...")
    zip_path = CARTELLA / "platform-tools.zip"
    try:
        urllib.request.urlretrieve(url_platform_tools(), zip_path)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(CARTELLA)
    except Exception as e:  # rete assente, proxy, disco pieno...
        print(f"Download non riuscito: {e}")
        print("Scarica a mano le 'SDK Platform-Tools' da developer.android.com ed estraile qui.")
        return None
    finally:
        zip_path.unlink(missing_ok=True)
    adb = trova_adb()
    if adb and platform.system() != "Windows":
        Path(adb).chmod(0o755)
    return adb


class Tv:
    def __init__(self, adb: str, indirizzo: str):
        self.adb = adb
        self.indirizzo = indirizzo

    def adb_cmd(self, *argomenti: str, timeout: int = 30) -> subprocess.CompletedProcess:
        return subprocess.run([self.adb, *argomenti], capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace")

    def shell(self, comando: str, timeout: int = 30) -> str:
        r = self.adb_cmd("-s", self.indirizzo, "shell", comando, timeout=timeout)
        return (r.stdout + r.stderr).strip()

    def collega(self) -> bool:
        uscita = self.adb_cmd("connect", self.indirizzo).stdout.strip()
        print(uscita)
        stato = self.adb_cmd("devices").stdout
        riga = next((r for r in stato.splitlines() if r.startswith(self.indirizzo)), "")
        if riga.endswith("device"):
            print("Collegato alla TV.")
            return True
        if "unauthorized" in riga:
            print("Sulla TV è comparsa una richiesta: scegli 'Consenti sempre' e riprova.")
        else:
            print("TV non raggiungibile: controlla l'IP, lo stesso Wi-Fi e il debug di rete attivo.")
        return False

    def pacchetti(self, attivi: bool = True) -> list[str]:
        uscita = self.shell("pm list packages " + ("-e" if attivi else "-d"))
        return sorted(r.removeprefix("package:").strip()
                      for r in uscita.splitlines() if r.startswith("package:"))

    def disattiva(self, pacchetto: str) -> str | None:
        """Ritorna il metodo usato ('disable' o 'uninstall'), None se non riuscito."""
        if "disabled" in self.shell(f"pm disable-user --user 0 {pacchetto}").lower():
            return "disable"
        # Alcuni firmware TCL rifiutano disable-user: "uninstall --user 0" toglie l'app
        # solo per l'utente, resta nel sistema e si ripristina con install-existing.
        if "success" in self.shell(f"pm uninstall -k --user 0 {pacchetto}").lower():
            return "uninstall"
        return None

    def ripristina(self, pacchetto: str, metodo: str) -> bool:
        if metodo == "uninstall":
            uscita = self.shell(f"cmd package install-existing {pacchetto}")
            return "installed" in uscita.lower() or "success" in uscita.lower()
        return "enabled" in self.shell(f"pm enable {pacchetto}").lower()


# ---------- Registro delle modifiche ----------

def leggi_registro() -> list[tuple[str, str]]:
    if not REGISTRO.exists():
        return []
    righe = [r.split("\t") for r in REGISTRO.read_text(encoding="utf-8").splitlines() if r.strip()]
    return [(r[0], r[1] if len(r) > 1 else "disable") for r in righe]


def scrivi_registro(voci: list[tuple[str, str]]) -> None:
    DATI.mkdir(exist_ok=True)
    REGISTRO.write_text("".join(f"{p}\t{m}\n" for p, m in voci), encoding="utf-8")


def aggiungi_al_registro(pacchetto: str, metodo: str) -> None:
    voci = [v for v in leggi_registro() if v[0] != pacchetto]
    scrivi_registro(voci + [(pacchetto, metodo)])


# ---------- Menu ----------

def chiedi(domanda: str) -> str:
    try:
        return input(domanda).strip()
    except EOFError:
        return ""


def si(domanda: str) -> bool:
    return chiedi(domanda + " [s/N] ").lower() in ("s", "si", "sì", "y")


def analizza(tv: Tv) -> list[tuple[str, str]]:
    print("\n--- Consumo CPU (ultimi minuti) ---")
    print("\n".join(tv.shell("dumpsys cpuinfo", timeout=60).splitlines()[:20]))
    attivi = tv.pacchetti()
    candidati = [(p, m) for p in attivi if (m := motivo(p))]
    print(f"\n--- {len(attivi)} pacchetti attivi, {len(candidati)} candidati da disattivare ---")
    for p, m in candidati:
        print(f"  {p:55} {m}")
    valutare = [p for p in attivi if da_valutare(p)]
    if valutare:
        print("\n--- Altri pacchetti TCL da valutare a mano (non li tocco da solo) ---")
        for p in valutare:
            print(f"  {p}")
    return candidati


def disattiva_consigliati(tv: Tv) -> None:
    candidati = analizza(tv)
    if not candidati:
        return
    print("\nTi chiedo conferma pacchetto per pacchetto.")
    for p, m in candidati:
        if si(f"Disattivo {p} ({m})?"):
            disattiva_uno(tv, p)


def disattiva_uno(tv: Tv, pacchetto: str) -> None:
    if protetto(pacchetto) and not si(f"{pacchetto} sembra di sistema: rischi di bloccare la TV. Sicuro?"):
        return
    metodo = tv.disattiva(pacchetto)
    if metodo:
        aggiungi_al_registro(pacchetto, metodo)
        print(f"  ✓ {pacchetto} disattivato")
    else:
        print(f"  ✗ {pacchetto}: la TV non lo consente")


def menu_ripristina(tv: Tv) -> None:
    voci = leggi_registro()
    if not voci:
        print("Nessun pacchetto disattivato da questo programma.")
        return
    for i, (p, _) in enumerate(voci, 1):
        print(f"  {i:2}. {p}")
    scelta = chiedi("Numero da ripristinare, 't' per tutti, invio per annullare: ").lower()
    if scelta == "t":
        scelti = voci
    elif scelta.isdigit() and 1 <= int(scelta) <= len(voci):
        scelti = [voci[int(scelta) - 1]]
    else:
        return
    rimasti = list(voci)
    for p, m in scelti:
        if tv.ripristina(p, m):
            rimasti.remove((p, m))
            print(f"  ✓ {p} ripristinato")
        else:
            print(f"  ✗ {p}: ripristino non riuscito")
    scrivi_registro(rimasti)


def animazioni(tv: Tv, scala: str) -> None:
    for chiave in ("window_animation_scale", "transition_animation_scale", "animator_duration_scale"):
        tv.shell(f"settings put global {chiave} {scala}")
    print(f"Animazioni impostate a {scala}.")


def salva_elenco(tv: Tv) -> None:
    DATI.mkdir(exist_ok=True)
    file = DATI / "pacchetti.txt"
    righe = [f"{p}\tattivo" for p in tv.pacchetti()] + [f"{p}\tdisattivato" for p in tv.pacchetti(False)]
    file.write_text("\n".join(righe) + "\n", encoding="utf-8")
    print(f"Elenco salvato in {file}: puoi incollarlo a Claude per un parere.")


MENU = """
================ TV TCL ================
 1. Analizza (CPU e pacchetti inutili)
 2. Disattiva i consigliati (con conferma)
 3. Disattiva un pacchetto a scelta
 4. Ripristina pacchetti disattivati
 5. Animazioni più veloci (0.5x)
 6. Animazioni normali (1x)
 7. Salva l'elenco completo dei pacchetti
 0. Esci
"""


def main() -> int:
    adb = trova_adb() or scarica_adb()
    if not adb:
        return 1
    ip = FILE_IP.read_text(encoding="utf-8").strip() if FILE_IP.exists() else ""
    nuovo = chiedi(f"IP della TV{f' [{ip}]' if ip else ''}: ") or ip
    if not nuovo:
        print("Serve l'IP: lo trovi sulla TV in Impostazioni → Rete.")
        return 1
    DATI.mkdir(exist_ok=True)
    FILE_IP.write_text(nuovo, encoding="utf-8")
    tv = Tv(adb, nuovo if ":" in nuovo else f"{nuovo}:{PORTA}")
    if not tv.collega():
        return 1

    azioni = {
        "1": lambda: analizza(tv),
        "2": lambda: disattiva_consigliati(tv),
        "3": lambda: (p := chiedi("Nome del pacchetto: ")) and disattiva_uno(tv, p),
        "4": lambda: menu_ripristina(tv),
        "5": lambda: animazioni(tv, "0.5"),
        "6": lambda: animazioni(tv, "1"),
        "7": lambda: salva_elenco(tv),
    }
    while True:
        print(MENU)
        scelta = chiedi("Scelta: ")
        if scelta in ("0", ""):
            break
        if scelta in azioni:
            try:
                azioni[scelta]()
            except subprocess.TimeoutExpired:
                print("La TV non risponde: è ancora accesa e sullo stesso Wi-Fi?")
    print("Per vedere l'effetto conviene riavviare la TV.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
