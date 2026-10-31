# TV TCL

Programma per rendere più fluida una TV TCL (Android TV / Google TV): trova e disattiva
pubblicità, raccomandazioni, telemetria e app di contorno, e velocizza le animazioni.
Ogni modifica si può annullare dal menu.

## Prima, sulla TV

1. **Impostazioni → Sistema (o Preferenze dispositivo) → Info**: premi 7 volte su **Build**
   finché compare «Ora sei uno sviluppatore».
2. **Opzioni sviluppatore**: attiva **Debug USB** e, se c'è, **Debug di rete / ADB in rete**.
3. Annota l'**indirizzo IP** della TV (**Impostazioni → Rete**).

Il computer deve essere sullo **stesso Wi-Fi** della TV.

## Avvio su Windows

1. Installa Python da python.org (spunta **"Add Python to PATH"**).
2. Scarica il progetto da GitHub (**Code → Download ZIP**) ed estrailo.
3. Apri la cartella `tv-tcl` e fai doppio clic su **`avvia.bat`**.

Se ADB non è installato, il programma scarica da solo le *platform-tools* di Google.
Al primo collegamento sulla TV compare una richiesta: scegli **Consenti sempre**.

Su Mac/Linux: `python3 tv.py`.

## Il menu

| Voce | Cosa fa |
|---|---|
| 1. Analizza | Mostra il consumo di CPU e i pacchetti candidati, con il motivo |
| 2. Disattiva i consigliati | Li propone uno per uno e chiede conferma |
| 3. Disattiva un pacchetto a scelta | Per i pacchetti «da valutare a mano» |
| 4. Ripristina | Riattiva uno o tutti i pacchetti disattivati dal programma |
| 5 / 6. Animazioni | 0.5x per una TV più scattante, 1x per tornare come prima |
| 7. Salva l'elenco | Scrive `data/pacchetti.txt`, da incollare a Claude per un parere |

## Sicurezza

- I pacchetti vengono **disattivati**, non cancellati: restano nella TV e il menu 4 li riattiva.
  L'elenco è in `data/disattivati.txt`.
- Launcher, Impostazioni, tastiera, servizi Google, HDMI, sintonizzatore, telecomando e
  aggiornamenti non vengono mai proposti.
- Nel caso peggiore, un ripristino di fabbrica della TV annulla tutto.

Dopo le modifiche conviene riavviare la TV.

## Test

```bash
pip install pytest
python -m pytest tests
```
