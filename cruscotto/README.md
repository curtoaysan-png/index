# Cruscotto

App personale e locale per tenere traccia delle decisioni già prese: progresso dei fronti (tesi,
paper, esami, candidature), avvio rapido delle sessioni di lavoro, scadenze e rinvii, calendario
degli impegni con un assistente che organizza la settimana, lista d'attesa per gli acquisti e fonti.

## Avvio rapido su Windows

1. Installa Python da python.org (nella prima schermata spunta **"Add Python to PATH"**).
2. Scarica il progetto da GitHub (**Code → Download ZIP**) ed estrailo in una cartella locale,
   non su OneDrive.
3. Apri la cartella `cruscotto` e fai doppio clic su **`avvia.bat`**.

La prima volta installa le librerie (qualche minuto) e crea i fronti iniziali; le volte successive
apre subito il Cruscotto nel browser. Per chiuderlo basta chiudere la finestra nera.

## Installazione manuale

Serve Python 3.11 o successivo.

```bash
cd cruscotto
python -m venv .venv
source .venv/bin/activate        # su Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py                   # una volta sola: crea i quattro fronti iniziali
```

## Avvio

```bash
streamlit run app.py
```

Si apre il browser su `http://localhost:8501`. Dalla home una sessione parte con un clic
("Avvia 90 minuti" / "Avvia 10 minuti", oppure i pulsanti su ogni fronte).

## Database e backup

- I dati sono salvati subito, a ogni "Aggiungi" o "Salva": chiudere la scheda o la finestra non
  cancella nulla.
- Il database sta **fuori dalla cartella dell'app**, così puoi scaricare una versione nuova e
  sostituire la cartella senza perdere nulla:
  - Windows: `C:\Users\<nome>\AppData\Local\Cruscotto\cruscotto.db` (cartella locale, non
    sincronizzata da OneDrive);
  - Mac/Linux: `~/.cruscotto/cruscotto.db`.
- Chi aveva già dei dati in `cruscotto/data/cruscotto.db` (versione precedente) li ritrova
  spostati automaticamente al primo avvio; il vecchio file resta rinominato in
  `cruscotto.db.spostato`.
- Per il backup: pagina **Preferenze e backup** → scegli la cartella (va bene anche una cartella di
  OneDrive) → **Esporta backup**. Viene salvata una copia con data e ora nel nome, ad esempio
  `cruscotto_2026-09-24_1830.db`.
- Per ripristinare un backup: chiudi l'app e copia il file al posto di `cruscotto.db` nella
  cartella dei dati.

## Assistente (facoltativo)

L'assistente usa l'API di Anthropic, che si paga a consumo, separatamente dall'abbonamento a Claude.
Serve un account su platform.claude.com con credito; un piano settimanale costa pochi centesimi.

1. Crea una chiave API su platform.claude.com.
2. Impostala come variabile d'ambiente prima di avviare l'app:

   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."                   # macOS / Linux
   setx ANTHROPIC_API_KEY "sk-ant-..."                     # Windows (poi riapri il terminale)
   ```

3. Il modello si cambia in `config.py` (`MODELLO`, predefinito `claude-sonnet-5`); il prompt in
   `prompts.py`; le regole di lavoro dalla pagina Preferenze.

Senza chiave l'app funziona in tutto il resto e i pulsanti dell'assistente spiegano cosa manca.
Nessun blocco proposto finisce in calendario senza accettazione esplicita, e i blocchi che si
sovrappongono a un impegno vengono scartati da `logica.py` prima dell'anteprima.

### Domande in stile Feynman

Nella chiusura della sessione, dopo aver scritto la spiegazione, il pulsante **Fammi domande su
questa spiegazione** chiede all'assistente 3 domande sul tuo testo (definire un termine, fare un
esempio, spiegare un passaggio più semplicemente). L'assistente fa solo domande: non dà risposte e
non riscrive né corregge il testo. Le domande vengono salvate con la sessione e riproposte all'avvio
della sessione successiva sullo stesso fronte, accanto a "Da dove riparti". Il prompt è in
`prompts.py` (`FEYNMAN`).

## Calendario e iCal

- Turni e lezioni si inseriscono una volta con "Ogni settimana" (e una data di fine facoltativa).
- Import da Google Calendar: nella pagina Calendario, sezione iCal, incolla l'indirizzo segreto in
  formato iCal (Impostazioni del calendario → "Indirizzo segreto in formato iCal") e premi
  **Aggiorna da iCal**. Vengono importati gli eventi della settimana visualizzata; l'aggiornamento
  sostituisce solo gli eventi già importati da iCal. Gli eventi di un giorno intero sono esclusi.
- Cliccando su un blocco di lavoro si apre la sessione con fronte e durata già impostati.

## Test

```bash
python -m pytest
```

## Struttura

- `app.py`: avvio e navigazione
- `db.py`: database e regole obbligatorie (chiusura sessione, motivo dei rinvii, 48 ore)
- `logica.py`: calcoli testabili (ritmo, proiezione, ricorrenze, fasce libere, verifica del piano)
- `assistente.py`, `prompts.py`: chiamata all'API
- `componenti.py`: parti di interfaccia condivise
- `pages/`: pagine Streamlit
- `tests/`: test unitari
