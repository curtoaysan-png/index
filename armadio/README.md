# Armadio

App personale per decidere cosa indossare:

1. **Armadio**: fotografi i tuoi capi, Claude li cataloga (categoria, colori, materiale, formalità, stagione, stile) e tu confermi o correggi.
2. **Outfit**: scrivi la situazione (es. «cena informale sabato sera, fa freddo») e ricevi un outfit composto solo dai tuoi capi, con la spiegazione e, se utile, uno stile alternativo.
3. **Armocromia**: stima indicativa di sottotono, stagione e palette a partire da 1-3 selfie, modificabile a mano.

## Avvio rapido su Windows

1. Installa Python da python.org (nella prima schermata spunta **"Add Python to PATH"**).
2. Scarica il progetto da GitHub (**Code → Download ZIP**) ed estrailo in una cartella locale,
   non su OneDrive (clic destro sul file → **Estrai tutto…**).
3. (Facoltativo) Nella cartella `armadio` crea un file di testo `chiave_api.txt` con dentro solo la
   chiave API (`sk-ant-...`), su una riga. Il file non finisce su GitHub.
4. Apri la cartella `armadio` e fai doppio clic su **`avvia.bat`**.

La prima volta installa le librerie (qualche minuto); le volte successive apre subito l'app nel
browser. Per chiuderla basta chiudere la finestra nera.

## Installazione manuale

Serve Python 3.11 o successivo.

```bash
cd armadio
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."   # facoltativa
streamlit run app.py
```

Si apre il browser su http://localhost:8501.

## Uso

- **Aggiungere un capo**: pagina *Armadio* → scegli una o più foto → controlla la scheda → **Salva**.
  Dal telefono il pulsante di caricamento permette anche di scattare la foto al momento.
- **Outfit**: pagina *Outfit* → scrivi per cosa ti vesti (e, se vuoi, un capo da cui partire) → **Proponi outfit**.
  Dai un giudizio (mi piace / non mi piace / indossato): gli ultimi 10 outfit con il giudizio guidano le proposte successive.
- **Armocromia**: pagina *Armocromia* → segui le istruzioni per il selfie → **Stima armocromia** → controlla e **Salva profilo**.
  Qui scrivi anche le tue preferenze di stile. Se fai una consulenza vera, inserisci i dati a mano.

## Database e backup

- I dati sono salvati subito, a ogni **Salva**: chiudere la scheda o la finestra non cancella nulla.
- Le foto (ridotte a 1024 px sul lato lungo) sono salvate **dentro il database**, insieme a tutto il resto.
- Il database sta **fuori dalla cartella dell'app**, così puoi scaricare una versione nuova e
  sostituire la cartella senza perdere nulla:
  - Windows: `C:\Users\<nome>\AppData\Local\Armadio\armadio.db` (cartella locale, non
    sincronizzata da OneDrive);
  - Mac/Linux: `~/.armadio/armadio.db`.
- Chi aveva già dei capi nella prima versione (`armadio/data/`) li ritrova spostati automaticamente
  al primo avvio, foto comprese; il vecchio file resta rinominato in `armadio.db.spostato`.
- Per il backup: pagina **Backup → Scarica backup**. È un unico file con dentro anche le foto, ad
  esempio `armadio_2026-09-26_1830.db`, da tenere dove vuoi (anche su OneDrive).
- Per ripristinare: **Backup → Ripristina da un backup** → scegli il file → spunta la conferma →
  **Ripristina**. Sostituisce tutti i dati attuali.

## Usarlo anche dal telefono (online)

L'app può girare online su **Streamlit Community Cloud** (gratuito) con i dati in un database
**Postgres su Neon** (gratuito), come il Cruscotto. Si apre da qualunque dispositivo, anche a PC
spento, ed è protetta da una password. Lo stesso codice sul PC continua a usare il file locale.

### 1. Il database (Neon)
Puoi usare **lo stesso database del Cruscotto**: le tabelle di Armadio (`capi`, `profilo`, `outfit`)
hanno nomi diversi da quelle del Cruscotto e non si toccano, nemmeno con backup e ripristino.
Ti serve solo la stessa connection string (inizia con `postgresql://`), che trovi su **neon.tech**
→ il tuo progetto → **Connect**.

In alternativa crea un progetto nuovo: **neon.tech → New project**, nome `armadio`, regione
**Europe (Frankfurt)**, poi **Connect** e copia la connection string.

Il piano gratuito di Neon offre 0,5 GB per progetto: bastano per circa duemila foto.

### 2. Pubblica l'app (Streamlit Community Cloud)
1. Vai su **share.streamlit.io** e accedi con GitHub.
2. **Create app** → *Deploy a public app from GitHub*:
   - Repository: `curtoaysan-png/index`
   - Branch: `main`
   - Main file path: `armadio/app.py`
   - App URL: un nome a scelta, ad esempio `armadio-tuonome`
3. Apri **Advanced settings**:
   - Python version: **3.12**
   - **Secrets**: incolla, con i tuoi valori tra virgolette:
     ```toml
     DATABASE_URL = "postgresql://...la stringa copiata da Neon..."
     ARMADIO_PASSWORD = "una password che scegli tu"
     ANTHROPIC_API_KEY = "sk-ant-..."   # facoltativa, per analisi foto, outfit e armocromia
     ```
4. **Deploy**. Dopo qualche minuto l'app è online all'indirizzo scelto.

Se mancano `DATABASE_URL` o `ARMADIO_PASSWORD`, l'app online resta bloccata e lo dice: senza database
le foto andrebbero perse a ogni riavvio, e senza password l'armadio sarebbe visibile a chiunque.
I secrets restano su Streamlit, non finiscono su GitHub; si cambiano da
**Manage app → Settings → Secrets**.

### 3. Porta online i dati che hai sul PC
1. Sul PC (app avviata con `avvia.bat`): **Backup → Scarica backup**.
2. Nell'app online: **Backup → Ripristina da un backup** → scegli il file → spunta la conferma →
   **Ripristina**.

### 4. Sul telefono
1. Apri l'indirizzo dell'app e inserisci la password.
2. Dopo l'accesso l'indirizzo contiene `?accesso=...`: aggiungi **quella** pagina alla schermata
   Home (iPhone/Safari: **Condividi → Aggiungi alla schermata Home**; Android/Chrome:
   **⋮ → Aggiungi a schermata Home**). Aprendola da lì non serve riscrivere la password.
   Quel collegamento vale come la password: non condividerlo.

### Da sapere
- Da quando usi l'app online, usa **solo quella** (anche dal PC, nel browser). La versione avviata
  con `avvia.bat` ha un database separato: i dati non si sincronizzano tra le due.
- Se l'app online non viene aperta per un po', Streamlit la mette in pausa: alla riapertura
  compare un pulsante per risvegliarla (circa un minuto). Anche il database Neon si "addormenta":
  il primo caricamento è un po' più lento.
- Cambiare la password: modifica `ARMADIO_PASSWORD` nei secrets; il vecchio collegamento sulla
  schermata Home smette di funzionare e va ricreato.

## Chiave API e costi

L'analisi delle foto, gli outfit e l'armocromia usano l'API di Anthropic, che si paga a consumo,
separatamente dall'abbonamento a Claude. Serve un account su platform.claude.com con credito.
Il modello si cambia in `config.py` (`MODELLO`, predefinito `claude-sonnet-5`).

- Le foto vengono ridotte a 1024 px sul lato lungo prima di essere inviate.
- Per gli outfit si inviano solo i dati testuali dei capi, non le foto.
- L'assistente usa solo capi presenti nell'armadio: gli id inesistenti vengono scartati e la proposta viene rigenerata una volta.
- La stima di armocromia da foto è indicativa: affidabilità al massimo «media».

Senza chiave l'armadio funziona comunque: i campi di ogni capo si compilano a mano.

## Test

```bash
python -m pytest
# anche su Postgres:
ARMADIO_TEST_PG="postgresql://..." python -m pytest
```

## Struttura

- `app.py`: avvio, password e navigazione
- `db.py`: database (SQLite sul PC, Postgres online), foto, backup e ripristino
- `ai.py`: chiamate a Claude e prompt
- `ui.py`: parti di interfaccia condivise
- `pages/`: pagine Streamlit
- `tests/`: test unitari
