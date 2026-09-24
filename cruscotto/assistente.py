"""Chiamata all'API di Anthropic per il piano settimanale."""
import json
import os

import config
import logica
import prompts


class ErroreAssistente(Exception):
    """Errore da mostrare così com'è all'utente."""


def chiave_presente() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())


def _client(client):
    if client is not None:
        return client
    if not chiave_presente():
        raise ErroreAssistente(
            "Assistente non disponibile: manca la variabile d'ambiente ANTHROPIC_API_KEY. "
            "Il resto dell'app funziona normalmente."
        )
    import anthropic
    return anthropic.Anthropic()


def _richiedi_json(client, sistema, contenuto, estrai, max_tokens=16000):
    """Chiede una risposta JSON. Se non è valida fa un solo nuovo tentativo."""
    messaggi = [{"role": "user", "content": contenuto}]
    for tentativo in range(2):
        risposta = _chiama(client, sistema, messaggi, max_tokens)
        testo = "".join(b.text for b in risposta.content if b.type == "text")
        try:
            return estrai(testo)
        except ValueError:
            if tentativo == 1:
                break
            messaggi += [{"role": "assistant", "content": testo or "(vuoto)"},
                         {"role": "user", "content": prompts.RIPROVA}]
    raise ErroreAssistente("La risposta dell'assistente non era JSON valido, anche dopo un nuovo tentativo.")


def chiedi_piano(dati: dict, client=None) -> dict:
    """Invia i dati e restituisce la proposta già estratta dal JSON."""
    contenuto = prompts.RICHIESTA.format(dati=json.dumps(dati, ensure_ascii=False, indent=1))
    return _richiedi_json(_client(client), prompts.SISTEMA, contenuto, logica.estrai_json)


def chiedi_domande(fronte: str, spiegazione: str, client=None) -> list[str]:
    """Tre domande in stile Feynman sulla spiegazione. Nessuna risposta, nessun testo riscritto."""
    contenuto = prompts.RICHIESTA_FEYNMAN.format(fronte=fronte, spiegazione=spiegazione.strip())
    return _richiedi_json(_client(client), prompts.FEYNMAN, contenuto, logica.estrai_domande,
                          max_tokens=4000)


def _chiama(client, sistema, messaggi, max_tokens):
    import anthropic

    try:
        risposta = client.messages.create(
            model=config.MODELLO,
            max_tokens=max_tokens,
            system=sistema,
            messages=messaggi,
        )
    except anthropic.AuthenticationError:
        raise ErroreAssistente("Chiave API non valida (ANTHROPIC_API_KEY).") from None
    except anthropic.RateLimitError:
        raise ErroreAssistente("Troppe richieste all'API: riprova tra qualche minuto.") from None
    except anthropic.APIStatusError as e:
        messaggio = str(e).lower()
        if e.status_code == 402 or "credit balance" in messaggio or "billing" in messaggio:
            raise ErroreAssistente(
                "Credito API esaurito: ricarica il credito su platform.claude.com."
            ) from None
        raise ErroreAssistente(f"Errore dell'API ({e.status_code}): {e.message}") from None
    except anthropic.APIConnectionError:
        raise ErroreAssistente("Connessione all'API non riuscita: controlla la rete.") from None
    if risposta.stop_reason == "refusal":
        raise ErroreAssistente("L'assistente non ha prodotto un piano per questa richiesta.")
    return risposta
