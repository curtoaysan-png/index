# Armadio

App personale e locale per decidere cosa indossare:

1. **Armadio**: fotografi i tuoi capi, Claude li cataloga (categoria, colori, materiale, formalità, stagione, stile) e tu confermi o correggi.
2. **Outfit**: scrivi la situazione (es. «cena informale sabato sera, fa freddo») e ricevi un outfit composto solo dai tuoi capi, con la spiegazione e, se utile, uno stile alternativo.
3. **Armocromia**: stima indicativa di sottotono, stagione e palette a partire da 1-3 selfie, modificabile a mano.

## Avvio rapido su Windows (senza terminale)

1. Scarica il progetto: su https://github.com/curtoaysan-png/index clicca **Code → Download ZIP**,
   poi clic destro sul file → **Estrai tutto…**.
2. Apri la cartella estratta, poi la cartella `armadio`.
3. (Facoltativo) Crea un file di testo `chiave_api.txt` con dentro solo la chiave API (`sk-ant-...`).
4. Doppio clic su **`avvia.bat`**: la prima volta installa le librerie, poi apre l'app nel browser.

## Installazione (da terminale)

Serve Python 3.11 o successivo.

```bash
cd armadio
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Chiave API (facoltativa)

Per l'analisi automatica delle foto, gli outfit e l'armocromia serve una chiave Anthropic:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."      # Windows (PowerShell): $env:ANTHROPIC_API_KEY="sk-ant-..."
```

Senza chiave l'armadio funziona comunque: i campi di ogni capo si compilano a mano.
Il modello si cambia in `config.py` (`MODELLO`, predefinito `claude-sonnet-5`).

## Avvio

```bash
streamlit run app.py
```

Si apre il browser su http://localhost:8501.

## Uso

- **Aggiungere un capo**: pagina *Armadio* → scegli una o più foto → controlla la scheda → **Salva**.
- **Outfit**: pagina *Outfit* → scrivi per cosa ti vesti (e, se vuoi, un capo da cui partire) → **Proponi outfit**.
  Dai un giudizio (mi piace / non mi piace / indossato): gli ultimi 10 outfit con il giudizio guidano le proposte successive.
- **Armocromia**: pagina *Armocromia* → segui le istruzioni per il selfie → **Stima armocromia** → controlla e **Salva profilo**.
  Qui scrivi anche le tue preferenze di stile. Se fai una consulenza vera, inserisci i dati a mano.

## Dati e costi

- Tutto resta sul tuo computer: database in `data/armadio.db`, foto in `data/foto/` (esclusi da git).
- Le foto vengono ridotte a 1024 px sul lato lungo prima di essere salvate e inviate.
- Per gli outfit si inviano solo i dati testuali dei capi, non le foto.
- L'assistente usa solo capi presenti nell'armadio: gli id inesistenti vengono scartati e la proposta viene rigenerata una volta.
- La stima di armocromia da foto è indicativa: affidabilità al massimo «media».

## Test

```bash
python -m pytest
```
