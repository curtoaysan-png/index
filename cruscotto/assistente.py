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


def chiedi_piano(dati: dict, client=None) -> dict:
    """Invia i dati e restituisce la proposta già estratta dal JSON.

    Se il JSON non è valido fa un solo nuovo tentativo, poi solleva ErroreAssistente.
    """
    if client is None:
        if not chiave_presente():
            raise ErroreAssistente(
                "Assistente non disponibile: manca la variabile d'ambiente ANTHROPIC_API_KEY. "
                "Il resto dell'app funziona normalmente."
            )
        import anthropic
        client = anthropic.Anthropic()

    messaggi = [{"role": "user", "content": prompts.RICHIESTA.format(
        dati=json.dumps(dati, ensure_ascii=False, indent=1))}]
    for tentativo in range(2):
        risposta = _chiama(client, messaggi)
        testo = "".join(b.text for b in risposta.content if b.type == "text")
        try:
            return logica.estrai_json(testo)
        except ValueError:
            if tentativo == 1:
                break
            messaggi += [{"role": "assistant", "content": testo or "(vuoto)"},
                         {"role": "user", "content": prompts.RIPROVA}]
    raise ErroreAssistente("La risposta dell'assistente non era JSON valido, anche dopo un nuovo tentativo.")


def _chiama(client, messaggi):
    import anthropic

    try:
        risposta = client.messages.create(
            model=config.MODELLO,
            max_tokens=16000,
            system=prompts.SISTEMA,
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
