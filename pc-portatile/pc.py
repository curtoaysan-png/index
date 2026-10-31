"""Portatile più veloce: programmi all'avvio, app preinstallate, pubblicità di Windows e pulizia.

Avvio: doppio clic su avvia.bat (Windows 10/11). Serve solo Python, nessuna libreria.
Non tocca servizi di sistema, driver, antivirus né Windows Update. Ogni modifica a avvio e
impostazioni finisce in data/modifiche.json, da cui il menu la può annullare.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PureWindowsPath

try:
    import winreg
except ImportError:  # i test girano anche fuori da Windows
    winreg = None

CARTELLA = Path(__file__).resolve().parent
DATI = CARTELLA / "data"
REGISTRO = DATI / "modifiche.json"

# ---------- Programmi all'avvio ----------

# Mai proposti: sicurezza, audio, touchpad, tastiera, grafica, Bluetooth.
AVVIO_PROTETTI = (
    "securityhealth", "defender", "realtek", "rtkaud", "audio", "synaptics", "syntp", "elan",
    "etd", "touchpad", "precision", "igfx", "intel", "amd", "radeon", "nvidia", "bluetooth",
    "hotkey", "keyboard", "fn", "dolby", "waves", "maxxaudio", "nahimic",
)

# Programmi che rallentano l'accensione e si possono aprire a mano quando servono.
AVVIO_PESANTI = (
    "teams", "spotify", "discord", "steam", "epic", "skype", "onedrive", "dropbox",
    "googledrive", "adobe", "acrobat", "ccleaner", "zoom", "utorrent", "bittorrent", "opera",
    "edgeautolaunch", "msedge", "itunes", "cortana", "whatsapp", "telegram", "battle.net",
    "ubisoft", "origin", "eadesktop", "riot", "lghub", "razer", "icue", "copilot",
)


def _parola(testo: str, parola: str) -> bool:
    # Le parole corte ("fn", "amd") valgono solo intere, per non riconoscere nomi a caso.
    return parola in testo if len(parola) > 3 else parola in re.split(r"[^a-z0-9]+", testo)


def classifica_avvio(nome: str, comando: str = "") -> str:
    """'protetto', 'consigliato' (da togliere) o 'valutare'."""
    eseguibile = comando.strip().strip('"').split('"')[0]
    testo = f"{nome} {PureWindowsPath(eseguibile).stem}".lower()
    # Per i protetti conta anche la cartella del programma (es. ...\Elantech\ETDCtrl.exe).
    if any(_parola(f"{nome} {eseguibile}".lower(), p) for p in AVVIO_PROTETTI):
        return "protetto"
    if any(p in testo.replace(" ", "") for p in AVVIO_PESANTI):
        return "consigliato"
    return "valutare"


# ---------- App preinstallate ----------

# App dello Store: nome del pacchetto (in minuscolo, anche parziale) → descrizione.
APP_INUTILI = {
    "microsoft.bingnews": "Notizie (MSN)",
    "microsoft.bingweather": "Meteo (MSN)",
    "microsoft.getstarted": "Suggerimenti",
    "microsoft.gethelp": "Assistenza Microsoft",
    "microsoft.microsoftsolitairecollection": "Solitario con pubblicità",
    "microsoft.windowsfeedbackhub": "Hub di Feedback",
    "microsoft.mixedreality.portal": "Portale Realtà mista",
    "microsoft.microsoft3dviewer": "Visualizzatore 3D",
    "microsoft.people": "Contatti",
    "microsoft.skypeapp": "Skype",
    "microsoft.microsoftofficehub": "pubblicità di Office",
    "microsoft.windowsmaps": "Mappe",
    "microsoft.zunevideo": "Film e TV",
    "microsoft.549981c3f5f10": "Cortana",
    "microsoft.powerautomatedesktop": "Power Automate",
    "clipchamp": "Clipchamp",
    "king.com": "giochi King (Candy Crush…)",
    "candycrush": "Candy Crush",
    "disney": "Disney+ preinstallata",
    "tiktok": "TikTok preinstallata",
    "bytedance": "TikTok preinstallata",
    "facebook": "Facebook preinstallata",
    "instagram": "Instagram preinstallata",
    "amazonvideo": "Prime Video preinstallata",
    "booking": "Booking.com preinstallata",
    "jumpstart": "app di benvenuto del produttore",
    "mcafee": "prova di McAfee",
    "norton": "prova di Norton",
    "expressvpn": "prova di ExpressVPN",
    "wildtangent": "giochi WildTangent",
}

# Programmi classici (Pannello di controllo) da proporre: di solito prove a pagamento.
PROGRAMMI_INUTILI = {
    "mcafee": "prova di antivirus: Windows Defender basta",
    "norton": "prova di antivirus: Windows Defender basta",
    "wildtangent": "giochi preinstallati",
    "expressvpn": "prova a pagamento",
    "booking.com": "collegamento pubblicitario",
    "dropbox promotion": "pubblicità di Dropbox",
    "jumpstart": "app di benvenuto del produttore",
    "lenovo welcome": "app di benvenuto del produttore",
    "candy crush": "gioco preinstallato",
}


def motivo_app(nome: str) -> str | None:
    nome = nome.lower()
    return next((d for chiave, d in APP_INUTILI.items() if chiave in nome), None)


def motivo_programma(nome: str) -> str | None:
    nome = nome.lower()
    return next((d for chiave, d in PROGRAMMI_INUTILI.items() if chiave in nome), None)


# ---------- Pubblicità e suggerimenti (solo HKCU, niente permessi di amministratore) ----------

CDM = r"Software\Microsoft\Windows\CurrentVersion\ContentDeliveryManager"
EXPLORER_ADV = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
ANNUNCI = [
    (CDM, "SilentInstalledAppsEnabled", 0, "installazione automatica di app sponsorizzate"),
    (CDM, "SystemPaneSuggestionsEnabled", 0, "app suggerite nel menu Start"),
    (CDM, "SubscribedContent-338388Enabled", 0, "suggerimenti nel menu Start"),
    (CDM, "SubscribedContent-338389Enabled", 0, "consigli e trucchi di Windows"),
    (CDM, "SubscribedContent-353694Enabled", 0, "contenuti suggeriti in Impostazioni"),
    (CDM, "SubscribedContent-353696Enabled", 0, "altri contenuti suggeriti in Impostazioni"),
    (CDM, "SubscribedContent-310093Enabled", 0, "schermata di benvenuto dopo gli aggiornamenti"),
    (CDM, "SubscribedContent-338387Enabled", 0, "curiosità sulla schermata di blocco"),
    (CDM, "RotatingLockScreenOverlayEnabled", 0, "pubblicità sulla schermata di blocco"),
    (CDM, "SoftLandingEnabled", 0, "notifiche con suggerimenti"),
    (r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", 0, "ID pubblicitario"),
    (EXPLORER_ADV, "ShowSyncProviderNotifications", 0, "pubblicità in Esplora file"),
    (EXPLORER_ADV, "Start_IrisRecommendations", 0, "consigli nel menu Start (Windows 11)"),
    (r"Software\Microsoft\Windows\CurrentVersion\Privacy",
     "TailoredExperiencesWithDiagnosticDataEnabled", 0, "esperienze personalizzate dai dati di diagnostica"),
    (r"Software\Microsoft\Windows\CurrentVersion\UserProfileEngagement",
     "ScoobeSystemSettingEnabled", 0, "«Completa la configurazione del dispositivo»"),
    (r"Software\Policies\Microsoft\Windows\Explorer",
     "DisableSearchBoxSuggestions", 1, "risultati web di Bing nella ricerca di Start"),
]


# ---------- Registro delle modifiche (per annullarle) ----------

def leggi_registro() -> list[dict]:
    if not REGISTRO.exists():
        return []
    try:
        return json.loads(REGISTRO.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def scrivi_registro(voci: list[dict]) -> None:
    DATI.mkdir(exist_ok=True)
    REGISTRO.write_text(json.dumps(voci, ensure_ascii=False, indent=1), encoding="utf-8")


def _id(voce: dict) -> tuple:
    return voce["tipo"], voce.get("radice"), voce.get("chiave"), voce["nome"]


def aggiungi_al_registro(voce: dict) -> None:
    """Registra una modifica; se c'è già tiene la prima, che contiene il valore originale."""
    voci = leggi_registro()
    if all(_id(v) != _id(voce) for v in voci):
        scrivi_registro(voci + [voce])


# ---------- Windows: PowerShell e registro ----------

def powershell(comando: str, timeout: int = 120) -> str:
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + comando],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.stdout.strip()


def powershell_json(comando: str) -> list[dict]:
    uscita = powershell(comando + " | ConvertTo-Json -Depth 3")
    if not uscita:
        return []
    dati = json.loads(uscita)
    return dati if isinstance(dati, list) else [dati]


def radice(nome: str):
    return {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}[nome]


def leggi_valore(rad: str, chiave: str, nome: str):
    try:
        with winreg.OpenKey(radice(rad), chiave) as k:
            return winreg.QueryValueEx(k, nome)[0]
    except OSError:
        return None


def scrivi_valore(rad: str, chiave: str, nome: str, valore, tipo) -> None:
    with winreg.CreateKeyEx(radice(rad), chiave, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, nome, 0, tipo, valore)


def cancella_valore(rad: str, chiave: str, nome: str) -> None:
    try:
        with winreg.OpenKey(radice(rad), chiave, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, nome)
    except FileNotFoundError:
        pass


def valori(rad: str, chiave: str) -> list[tuple[str, object]]:
    try:
        with winreg.OpenKey(radice(rad), chiave) as k:
            n = winreg.QueryInfoKey(k)[1]
            return [winreg.EnumValue(k, i)[:2] for i in range(n)]
    except OSError:
        return []


# ---------- Avvio automatico ----------
# Windows (come Gestione attività) segna un elemento come disattivato in StartupApproved:
# 12 byte, il primo pari = attivo (02), dispari = disattivato (03). Il programma non viene toccato.

APPROVED = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved"
ATTIVO = bytes([2] + [0] * 11)
DISATTIVO = bytes([3] + [0] * 11)


def elementi_avvio() -> list[dict]:
    sorgenti = [
        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Run", "Run"),
        ("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Run", "Run"),
        ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run", "Run32"),
    ]
    elementi = []
    for rad, chiave, approvato in sorgenti:
        for nome, comando in valori(rad, chiave):
            elementi.append({"nome": nome, "comando": str(comando), "radice": rad,
                             "chiave": rf"{APPROVED}\{approvato}"})
    cartelle = [
        ("HKCU", Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"),
        ("HKLM", Path(os.environ.get("PROGRAMDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\StartUp"),
    ]
    for rad, cartella in cartelle:
        if cartella.is_dir():
            for f in cartella.iterdir():
                if f.name.lower() != "desktop.ini":
                    elementi.append({"nome": f.name, "comando": str(f), "radice": rad,
                                     "chiave": rf"{APPROVED}\StartupFolder"})
    for e in elementi:
        stato = leggi_valore(e["radice"], e["chiave"], e["nome"])
        e["attivo"] = not (isinstance(stato, bytes) and stato and stato[0] % 2 == 1)
        e["classe"] = classifica_avvio(e["nome"], e["comando"])
    return elementi


def imposta_avvio(voce: dict, attivo: bool) -> bool:
    try:
        scrivi_valore(voce["radice"], voce["chiave"], voce["nome"],
                      ATTIVO if attivo else DISATTIVO, winreg.REG_BINARY)
        return True
    except PermissionError:
        print("  Serve l'amministratore: clic destro su avvia.bat → Esegui come amministratore.")
        return False


# ---------- Menu ----------

def chiedi(domanda: str) -> str:
    try:
        return input(domanda).strip()
    except EOFError:
        return ""


def si(domanda: str) -> bool:
    return chiedi(domanda + " [s/N] ").lower() in ("s", "si", "sì", "y")


def analizza() -> None:
    print("\nRaccolgo i dati, qualche secondo...")
    info = powershell_json(
        "$cs=Get-CimInstance Win32_ComputerSystem; $os=Get-CimInstance Win32_OperatingSystem;"
        "$cpu=(Get-CimInstance Win32_Processor | Measure-Object LoadPercentage -Average).Average;"
        "$d=Get-PSDrive C; $b=Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue;"
        "[pscustomobject]@{Marca=$cs.Manufacturer; Modello=$cs.Model; Windows=$os.Caption;"
        "RamTot=[math]::Round($os.TotalVisibleMemorySize/1MB,1);"
        "RamLibera=[math]::Round($os.FreePhysicalMemory/1MB,1); Cpu=$cpu;"
        "DiscoLibero=[math]::Round($d.Free/1GB,1); DiscoTot=[math]::Round(($d.Used+$d.Free)/1GB,1);"
        "Batteria=$b.EstimatedChargeRemaining;"
        "Acceso=[int]((Get-Date)-$os.LastBootUpTime).TotalHours}")
    if info:
        i = info[0]
        print(f"\n{i['Marca']} {i['Modello']} — {i['Windows']}")
        print(f"CPU in uso:  {i['Cpu']}%")
        print(f"RAM:         {i['RamLibera']} GB liberi su {i['RamTot']} GB")
        print(f"Disco C:     {i['DiscoLibero']} GB liberi su {i['DiscoTot']} GB")
        if i.get("Batteria") is not None:
            print(f"Batteria:    {i['Batteria']}%")
        print(f"Acceso da:   {i['Acceso']} ore")
        if i["DiscoTot"] and i["DiscoLibero"] / i["DiscoTot"] < 0.15:
            print("  ⚠ Disco quasi pieno: sotto il 15% libero Windows rallenta. Prova la voce 5.")
        if i["RamTot"] and i["RamLibera"] / i["RamTot"] < 0.15:
            print("  ⚠ RAM quasi esaurita: chiudi schede del browser e programmi in background.")
        if i["Acceso"] and i["Acceso"] > 72:
            print("  ⚠ Non viene riavviato da giorni: «Arresta» non basta, usa «Riavvia».")

    print("\n--- Programmi che usano più memoria ---")
    for p in powershell_json(
            "Get-Process | Group-Object ProcessName | ForEach-Object {[pscustomobject]@{"
            "Nome=$_.Name; MB=[int](($_.Group | Measure-Object WorkingSet64 -Sum).Sum/1MB)}}"
            " | Sort-Object MB -Descending | Select-Object -First 10"):
        print(f"  {p['Nome']:35} {p['MB']:>6} MB")

    avvio = [e for e in elementi_avvio() if e["attivo"]]
    print(f"\n--- {len(avvio)} programmi partono all'accensione ---")
    for e in avvio:
        segno = {"consigliato": "togliere", "protetto": "lasciare", "valutare": "?"}[e["classe"]]
        print(f"  {e['nome']:45} {segno}")


def menu_avvio() -> None:
    elementi = elementi_avvio()
    proposti = [e for e in elementi if e["attivo"] and e["classe"] != "protetto"]
    if not proposti:
        print("Niente da togliere dall'avvio.")
        return
    print("\n'togliere' = di solito inutile all'accensione; '?' = decidi tu.")
    print("Disattivarli non li cancella: li apri a mano quando servono.\n")
    for e in sorted(proposti, key=lambda e: e["classe"] != "consigliato"):
        segno = "togliere" if e["classe"] == "consigliato" else "?"
        if si(f"Tolgo dall'avvio {e['nome']} ({segno})?") and imposta_avvio(e, False):
            aggiungi_al_registro({"tipo": "avvio", "nome": e["nome"], "radice": e["radice"],
                                  "chiave": e["chiave"]})
            print(f"  ✓ {e['nome']} non parte più all'accensione")


def menu_app() -> None:
    print("\nCerco le app preinstallate...")
    app = [a for a in powershell_json(
        "Get-AppxPackage | Where-Object {-not $_.NonRemovable -and -not $_.IsFramework}"
        " | Select-Object Name, PackageFullName") if motivo_app(a["Name"])]
    programmi = []
    for rad, chiave in [("HKLM", r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                        ("HKLM", r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                        ("HKCU", r"Software\Microsoft\Windows\CurrentVersion\Uninstall")]:
        try:
            with winreg.OpenKey(radice(rad), chiave) as k:
                sottochiavi = [winreg.EnumKey(k, i) for i in range(winreg.QueryInfoKey(k)[0])]
        except OSError:
            continue
        for s in sottochiavi:
            nome = leggi_valore(rad, rf"{chiave}\{s}", "DisplayName")
            disinstalla = leggi_valore(rad, rf"{chiave}\{s}", "UninstallString")
            if nome and disinstalla and motivo_programma(nome) and nome not in [p[0] for p in programmi]:
                programmi.append((nome, disinstalla))

    if not app and not programmi:
        print("Nessuna app inutile trovata: il portatile è già pulito.")
        return
    print("Le app tolte si possono reinstallare dal Microsoft Store.\n")
    for a in app:
        if si(f"Disinstallo {a['Name']} ({motivo_app(a['Name'])})?"):
            powershell(f"Remove-AppxPackage -Package '{a['PackageFullName']}'")
            print(f"  ✓ {a['Name']} rimossa")
    for nome, disinstalla in programmi:
        if si(f"Disinstallo {nome} ({motivo_programma(nome)})? Si apre il suo programma di rimozione."):
            subprocess.run(disinstalla, shell=True)


def menu_annunci() -> None:
    da_fare = [(k, n, v, d) for k, n, v, d in ANNUNCI if leggi_valore("HKCU", k, n) != v]
    if not da_fare:
        print("Pubblicità e suggerimenti sono già spenti.")
        return
    print("\nSpengo:")
    for *_, d in da_fare:
        print(f"  • {d}")
    if not si("Procedo?"):
        return
    for chiave, nome, valore, _ in da_fare:
        aggiungi_al_registro({"tipo": "impostazione", "nome": nome, "radice": "HKCU", "chiave": chiave,
                              "prima": leggi_valore("HKCU", chiave, nome)})
        scrivi_valore("HKCU", chiave, nome, valore, winreg.REG_DWORD)
    print("Fatto. Alcune modifiche si vedono dopo aver riavviato il portatile.")


def dimensione(cartella: Path) -> int:
    totale = 0
    for radice_dir, _, file in os.walk(cartella):
        for f in file:
            try:
                totale += (Path(radice_dir) / f).stat().st_size
            except OSError:
                pass
    return totale


def pulizia() -> None:
    temp = Path(os.environ.get("TEMP", ""))
    if not temp.is_dir():
        return
    prima = dimensione(temp)
    print(f"File temporanei: {prima / 1024 ** 2:.0f} MB.")
    if not si("Li cancello? (quelli in uso vengono saltati)"):
        return
    for voce in temp.iterdir():
        try:
            if voce.is_dir():
                shutil.rmtree(voce, ignore_errors=True)
            else:
                voce.unlink()
        except OSError:
            pass
    print(f"  ✓ Liberati {(prima - dimensione(temp)) / 1024 ** 2:.0f} MB.")
    print("Per una pulizia più a fondo: Impostazioni → Sistema → Archiviazione → File temporanei.")


def rapporto_batteria() -> None:
    DATI.mkdir(exist_ok=True)
    file = DATI / "batteria.html"
    subprocess.run(["powercfg", "/batteryreport", "/output", str(file)], capture_output=True)
    if file.exists():
        print("Rapporto aperto nel browser. Confronta «Design capacity» con «Full charge capacity»:")
        print("se la seconda è sotto il 70% della prima, la batteria è consumata.")
        os.startfile(file)
    else:
        print("Rapporto non disponibile (forse non c'è una batteria).")


def ripristina() -> None:
    voci = leggi_registro()
    if not voci:
        print("Nessuna modifica da annullare.")
        return
    for i, v in enumerate(voci, 1):
        cosa = "avvio automatico" if v["tipo"] == "avvio" else "impostazione"
        print(f"  {i:2}. {v['nome']} ({cosa})")
    scelta = chiedi("Numero da annullare, 't' per tutte, invio per uscire: ").lower()
    if scelta == "t":
        scelte = list(voci)
    elif scelta.isdigit() and 1 <= int(scelta) <= len(voci):
        scelte = [voci[int(scelta) - 1]]
    else:
        return
    for v in scelte:
        if v["tipo"] == "avvio":
            if not imposta_avvio(v, True):
                continue
        elif v["prima"] is None:
            cancella_valore(v["radice"], v["chiave"], v["nome"])
        else:
            scrivi_valore(v["radice"], v["chiave"], v["nome"], v["prima"], winreg.REG_DWORD)
        voci.remove(v)
        print(f"  ✓ {v['nome']} ripristinato")
    scrivi_registro(voci)


MENU = """
============ PORTATILE ============
 1. Analizza (CPU, RAM, disco, avvio)
 2. Programmi all'accensione
 3. App preinstallate inutili
 4. Spegni pubblicità e suggerimenti di Windows
 5. Cancella file temporanei
 6. Rapporto sulla batteria
 7. Annulla modifiche
 0. Esci
"""


def main() -> int:
    if winreg is None:
        print("Questo programma funziona solo su Windows.")
        return 1
    azioni = {"1": analizza, "2": menu_avvio, "3": menu_app, "4": menu_annunci,
              "5": pulizia, "6": rapporto_batteria, "7": ripristina}
    while True:
        print(MENU)
        scelta = chiedi("Scelta: ")
        if scelta in ("0", ""):
            break
        if scelta in azioni:
            try:
                azioni[scelta]()
            except subprocess.TimeoutExpired:
                print("Windows non ha risposto in tempo: riprova.")
    print("Per vedere l'effetto conviene riavviare il portatile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
