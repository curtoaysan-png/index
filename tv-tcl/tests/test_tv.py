import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tv  # noqa: E402


def test_pubblicita_e_telemetria_riconosciute():
    assert tv.motivo("com.tcl.ads") == "pubblicità"
    assert tv.motivo("com.tcl.advertising.service") == "pubblicità"
    assert tv.motivo("com.tcl.feedback") == "telemetria"
    assert tv.motivo("com.tcl.recommendation") == "raccomandazioni"
    assert tv.motivo("com.tcl.appmarket") == "app di contorno"


def test_parole_corte_solo_come_segmento():
    # "ad" non deve riconoscere "download" o "android"
    assert tv.motivo("com.example.downloader") is None
    assert tv.motivo("com.tcl.ad_service") == "pubblicità"


def test_pacchetti_di_sistema_mai_candidati():
    for p in ("android", "com.tcl.tvlauncher", "com.android.tv.settings", "com.google.android.gms",
              "com.tcl.tvinput", "com.android.vending", "com.tcl.channel.settings"):
        assert tv.motivo(p) is None, p
        assert not tv.da_valutare(p), p


def test_app_normali_ignorate():
    assert tv.motivo("com.netflix.ninja") is None
    assert tv.motivo("com.google.android.youtube.tv") is None


def test_tcl_sconosciuti_da_valutare():
    assert tv.da_valutare("com.tcl.misterioso")
    assert not tv.da_valutare("com.tcl.ads")


def test_registro(tmp_path, monkeypatch):
    monkeypatch.setattr(tv, "DATI", tmp_path)
    monkeypatch.setattr(tv, "REGISTRO", tmp_path / "disattivati.txt")
    tv.aggiungi_al_registro("com.tcl.ads", "disable")
    tv.aggiungi_al_registro("com.tcl.feedback", "uninstall")
    tv.aggiungi_al_registro("com.tcl.ads", "disable")
    assert tv.leggi_registro() == [("com.tcl.feedback", "uninstall"), ("com.tcl.ads", "disable")]
