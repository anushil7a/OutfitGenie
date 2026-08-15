"""One place the app talks to a chat model.

Everything -- the vision read, the stylist, weather picks, colour backfill --
goes through here, so switching model or provider is an .env change rather
than a hunt through six files.

Configuration (all optional except the key):

    OPENAI_API_KEY        the key
    OPENAI_BASE_URL       provider endpoint. Unset = OpenAI direct.
                          AgentRouter: https://agentrouter.org/v1
    OPENAI_MODEL          text model      (default: gpt-5.6-sol)
    OPENAI_VISION_MODEL   image model     (default: same as OPENAI_MODEL)
    OPENAI_USER_AGENT     override the User-Agent sent with every request

A note on OPENAI_USER_AGENT: AgentRouter refuses requests whose User-Agent it
doesn't recognise, answering 401 "unauthorized client detected" for any key --
valid, invalid, or empty alike. Setting this to a string it accepts is what
makes the gateway usable from this app. That is deliberately a configuration
value, not a hardcoded default, because it works around an access restriction
the provider put in place on purpose; check it's permitted by their terms
before relying on it. Unset, the SDK sends its own User-Agent.

The client is built lazily. That matters: the old code constructed it at
import time in routes/chat.py, which ran *before* app.py called load_dotenv()
and blew up whenever the key wasn't already in the shell environment.
"""

import logging
import os

from openai import OpenAI

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-5.6-sol"

_client = None
# Newer OpenAI models renamed max_tokens -> max_completion_tokens. Which one
# this provider accepts is discovered on the first call and remembered.
_token_param = None


def base_url():
    return (os.getenv("OPENAI_BASE_URL") or "").strip() or None


def chat_model():
    return (os.getenv("OPENAI_MODEL") or "").strip() or DEFAULT_MODEL


def vision_model():
    return (os.getenv("OPENAI_VISION_MODEL") or "").strip() or chat_model()


def user_agent():
    return (os.getenv("OPENAI_USER_AGENT") or "").strip() or None


def get_client():
    """The shared client. Built on first use, not at import."""
    global _client
    if _client is None:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to .env and restart the app."
            )
        kwargs = {"api_key": key}
        url = base_url()
        if url:
            kwargs["base_url"] = url
        agent = user_agent()
        if agent:
            kwargs["default_headers"] = {"User-Agent": agent}
        _client = OpenAI(**kwargs)
        logger.info("LLM client ready: %s via %s%s", chat_model(),
                    url or "api.openai.com",
                    f" (UA: {agent})" if agent else "")
    return _client


def reset_client():
    """Drop the cached client. Only needed if the environment changes at runtime."""
    global _client, _token_param
    _client, _token_param = None, None


def _looks_like_param_error(error, param):
    """True when the call failed *because of this parameter*, not the request.

    Covers both shapes: the server rejecting it ("Unsupported parameter"), and
    an older SDK not knowing it at all, which raises TypeError client-side
    with "unexpected keyword argument" before anything is sent.
    """
    text = str(error).lower()
    if param not in text:
        return False
    return any(marker in text for marker in (
        "unsupported", "not supported", "unknown", "unrecognized",
        "invalid", "unexpected keyword", "unexpected argument",
    ))


def chat(messages, model=None, max_output_tokens=None, **kwargs):
    """Call chat completions and return the assistant's text.

    Handles the max_tokens/max_completion_tokens split between model
    generations: the correct name is discovered once and reused, so a
    provider expecting either one works without configuration.
    """
    client = get_client()
    model = model or chat_model()

    def send(token_param):
        payload = dict(kwargs)
        payload["model"] = model
        payload["messages"] = messages
        if max_output_tokens is not None and token_param:
            payload[token_param] = max_output_tokens
        return client.chat.completions.create(**payload)

    global _token_param
    order = [_token_param] if _token_param else ["max_completion_tokens", "max_tokens"]

    last_error = None
    for candidate in order:
        try:
            response = send(candidate)
            _token_param = candidate
            return response.choices[0].message.content
        except Exception as error:                      # noqa: BLE001
            last_error = error
            # Only fall through when the *parameter* was the problem.
            if max_output_tokens is not None and _looks_like_param_error(error, candidate):
                logger.info("%s rejected by %s; trying the other spelling", candidate, model)
                continue
            raise

    # Both spellings rejected -- send it without any cap rather than fail.
    logger.warning("No token-limit parameter accepted by %s; sending uncapped", model)
    try:
        response = send(None)
        _token_param = None
        return response.choices[0].message.content
    except Exception:                                   # noqa: BLE001
        raise last_error
