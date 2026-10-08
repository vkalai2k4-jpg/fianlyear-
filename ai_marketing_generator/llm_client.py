"""
Shared LLM client for the whole app (content generation, banner text,
campaign ideas, video scripts). Talks to OpenRouter, which gives access to
Claude and other models through one OpenAI-compatible REST API.

Put your key in .env as:
    OPENROUTER_API_KEY=sk-or-v1-...
Optionally choose a model (default below):
    OPENROUTER_MODEL=anthropic/claude-sonnet-4.5
"""

import os
import requests

DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_PLACEHOLDER_KEYS = {"", "your_api_key_here", "your-key-here", "your_key_here", "changeme"}


class LLMError(Exception):
    """Raised with a user-readable message when a call to the LLM fails."""


def is_configured():
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    return key.lower() not in _PLACEHOLDER_KEYS


def _get_key():
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip().strip('"').strip("'")
    if key.lower() in _PLACEHOLDER_KEYS:
        raise LLMError(
            "OPENROUTER_API_KEY is not configured. Open the .env file in the project "
            "folder, set OPENROUTER_API_KEY=<your key from openrouter.ai/keys>, "
            "save it, and restart the app (python app.py)."
        )
    return key


def call_llm(prompt, max_tokens=800, system=None):
    """
    Sends one prompt to the configured model on OpenRouter and returns the
    reply text. Raises LLMError (with a readable message) on any problem -
    there is no silent fallback to demo content.
    """
    api_key = _get_key()
    model = (os.environ.get("OPENROUTER_MODEL") or DEFAULT_MODEL).strip()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
            timeout=60,
        )
    except requests.exceptions.ConnectionError as e:
        raise LLMError(f"Could not reach OpenRouter (check your internet connection): {e}")
    except requests.exceptions.Timeout:
        raise LLMError("OpenRouter took too long to respond. Please try again.")
    except Exception as e:
        raise LLMError(f"Unexpected error while calling OpenRouter: {e}")

    if resp.status_code == 401:
        raise LLMError(
            "OpenRouter rejected the API key (authentication failed). Check that "
            "OPENROUTER_API_KEY in your .env is correct, has no extra spaces/quotes, "
            "and that the app was restarted."
        )
    if resp.status_code == 402:
        raise LLMError("OpenRouter says your account has insufficient credits. Add credits at openrouter.ai/credits.")
    if resp.status_code == 404:
        raise LLMError(f"Model '{model}' was not found on OpenRouter. Check OPENROUTER_MODEL in .env.")
    if resp.status_code == 429:
        raise LLMError("OpenRouter rate limit reached. Please wait a moment and try again.")
    if resp.status_code >= 400:
        raise LLMError(f"OpenRouter API error {resp.status_code}: {resp.text[:300]}")

    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise LLMError(f"OpenRouter replied, but the response could not be read: {e}")
