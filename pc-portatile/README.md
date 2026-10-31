# Portatile

Programma per rendere più veloce un portatile Windows 10/11: programmi all'accensione,
app preinstallate inutili, pubblicità di Windows e file temporanei. È il fratello di
[`tv-tcl`](../tv-tcl): stesso menu, ogni modifica si può annullare.

## Avvio

1. Installa Python da python.org (spunta **"Add Python to PATH"**).
2. Scarica il progetto da GitHub (**Code → Download ZIP**) ed estrailo.
3. Apri la cartella `pc-portatile` e fai doppio clic su **`avvia.bat`**.

Alcuni programmi all'avvio sono «di sistema» per tutti gli utenti: per toglierli serve
clic destro su `avvia.bat` → **Esegui come amministratore**. Il resto funziona senza.

## Il menu

| Voce | Cosa fa |
|---|---|
| 1. Analizza | Marca e modello, CPU, RAM, disco, batteria, programmi più pesanti e cosa parte all'accensione |
| 2. Programmi all'accensione | Propone cosa togliere (Teams, Spotify, OneDrive, Steam…), uno per uno con conferma |
| 3. App preinstallate | Candy Crush, notizie MSN, prove di McAfee/Norton, app del produttore… con conferma |
| 4. Pubblicità e suggerimenti | Spegne pubblicità nel menu Start, nella schermata di blocco, in Esplora file, ID pubblicitario e risultati di Bing |
| 5. File temporanei | Cancella la cartella TEMP (quelli in uso vengono saltati) |
| 6. Rapporto batteria | Apre il rapporto di Windows per vedere quanto è consumata la batteria |
| 7. Annulla modifiche | Ripristina avvio e impostazioni cambiati dalle voci 2 e 4 |

## Sicurezza

- **Non tocca** servizi di Windows, driver, Windows Defender né Windows Update.
- I programmi tolti dall'avvio **non vengono cancellati**: Windows li segna come disattivati,
  esattamente come fa Gestione attività → Avvio. Si riattivano dalla voce 7.
- Le impostazioni cambiate sono solo dell'utente, con il valore originale salvato in
  `data/modifiche.json`.
- Audio, touchpad, tastiera, scheda grafica e Bluetooth non vengono mai proposti.
- Le app disinstallate (voce 3) si reinstallano dal Microsoft Store.

Dopo le modifiche conviene **riavviare** (non «Arresta»: con l'avvio rapido di Windows non
azzera davvero il sistema).

## Test

```bash
pip install pytest
python -m pytest tests
```
