import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pc  # noqa: E402


def test_avvio_pesanti_da_togliere():
    assert pc.classifica_avvio("com.squirrel.Teams.Teams", r'"C:\Users\x\AppData\Local\Microsoft\Teams\Update.exe"') == "consigliato"
    assert pc.classifica_avvio("Spotify", r'"C:\Users\x\AppData\Roaming\Spotify\Spotify.exe" /background') == "consigliato"
    assert pc.classifica_avvio("MicrosoftEdgeAutoLaunch_ABC123", "") == "consigliato"
    assert pc.classifica_avvio("OneDrive", "") == "consigliato"


def test_avvio_protetti():
    assert pc.classifica_avvio("SecurityHealth", r"%windir%\system32\SecurityHealthSystray.exe") == "protetto"
    assert pc.classifica_avvio("RtkAudUService", r'"C:\Windows\System32\RtkAudUService64.exe" -background') == "protetto"
    assert pc.classifica_avvio("ETDCtrl", r"C:\Program Files\Elantech\ETDCtrl.exe") == "protetto"


def test_avvio_sconosciuti_da_valutare():
    assert pc.classifica_avvio("QualcosaDiStrano", r"C:\x\strano.exe") == "valutare"


def test_parole_corte_solo_intere():
    # "fn" e "amd" non devono proteggere nomi che li contengono per caso
    assert pc.classifica_avvio("Steam", r"C:\Program Files\Steam\steam.exe -silent") == "consigliato"


def test_app_inutili():
    assert pc.motivo_app("king.com.CandyCrushSaga") is not None
    assert pc.motivo_app("Microsoft.BingNews") == "Notizie (MSN)"
    assert pc.motivo_app("Microsoft.WindowsCalculator") is None
    assert pc.motivo_app("Microsoft.WindowsStore") is None


def test_programmi_inutili():
    assert pc.motivo_programma("McAfee LiveSafe") is not None
    assert pc.motivo_programma("Google Chrome") is None


def test_annunci_validi():
    assert len({(k, n) for k, n, *_ in pc.ANNUNCI}) == len(pc.ANNUNCI)
    assert all(k.startswith("Software\\") for k, *_ in pc.ANNUNCI)


def test_registro_tiene_il_valore_originale(tmp_path, monkeypatch):
    monkeypatch.setattr(pc, "DATI", tmp_path)
    monkeypatch.setattr(pc, "REGISTRO", tmp_path / "modifiche.json")
    voce = {"tipo": "impostazione", "nome": "Enabled", "radice": "HKCU", "chiave": "K", "prima": 1}
    pc.aggiungi_al_registro(voce)
    pc.aggiungi_al_registro({**voce, "prima": 0})
    assert pc.leggi_registro() == [voce]
