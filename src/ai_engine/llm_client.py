"""
LLM Client — Claude API (primary), GPT-4o (fallback)
=====================================================
Used by every module that needs AI generation:
  - paper_summariser (literature tab AI Summary button)
  - knowledge_card_gen (materials engine)
  - briefing_gen (briefing builder)
  - biocompat_predictor (regulatory engine)
  - assay_recommender (experimental design)
  - swot_generator (business intelligence)

All prompts go through here. Rate limiting, retries,
and fallback are handled centrally.

Usage:
    from ai_engine.llm_client import LLMClient
    client = LLMClient()

    # Simple call
    response = client.complete(prompt="Summarise this abstract: ...")

    # With system prompt
    response = client.complete(
        prompt="...",
        system="You are a biomaterials expert...",
        max_tokens=500
    )

    # Structured JSON output
    data = client.complete_json(
        prompt="Extract material properties as JSON...",
        system="Return only valid JSON, no markdown."
    )
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Model constants ───────────────────────────────────────────────────────────

CLAUDE_MODEL    = "claude-sonnet-4-20250514"
GPT_FALLBACK    = "gpt-4o"
MAX_RETRIES     = 3
RETRY_DELAY     = 2.0   # seconds between retries


class LLMError(Exception):
    """Raised when all LLM attempts fail."""
    pass


class LLMClient:
    """
    Central AI client. Instantiate once per module or use the
    module-level singleton get_client().

    Config is read from data_manager config at init time.
    Can also be constructed with explicit api_key for testing.
    """

    def __init__(self, api_key: Optional[str] = None,
                 fallback_key: Optional[str] = None):
        self._claude_key  = api_key      or self._load_key("ANTHROPIC_API_KEY",  "openai_api_key")
        self._openai_key  = fallback_key or self._load_key("OPENAI_API_KEY",     "openai_api_key")
        self._last_call   = 0.0
        self._min_gap     = 0.5   # seconds between calls — basic rate limit

    # ── Public API ────────────────────────────────────────────────────────────

    def complete(self,
                 prompt: str,
                 system: str = "",
                 max_tokens: int = 1000,
                 temperature: float = 0.3) -> str:
        """
        Send a prompt, return the text response.
        Tries Claude first, falls back to GPT-4o if Claude key unavailable.
        Raises LLMError if both fail.
        """
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        if self._claude_key:
            return self._call_claude(prompt, system, max_tokens, temperature)
        elif self._openai_key:
            logger.warning("No Claude key — falling back to GPT-4o")
            return self._call_openai(prompt, system, max_tokens, temperature)
        else:
            raise LLMError(
                "No API key configured. Add ANTHROPIC_API_KEY to your .env file.\n"
                "See config/.env.template for setup instructions."
            )

    def complete_json(self,
                      prompt: str,
                      system: str = "Return only valid JSON. No markdown fences, no explanation.",
                      max_tokens: int = 1500) -> Any:
        """
        Like complete() but parses the response as JSON.
        Strips markdown fences if the model adds them.
        Returns the parsed Python object (dict or list).
        """
        raw = self.complete(prompt=prompt, system=system,
                            max_tokens=max_tokens, temperature=0.1)
        return self._parse_json(raw)

    def complete_with_history(self,
                               messages: List[Dict[str, str]],
                               system: str = "",
                               max_tokens: int = 1000) -> str:
        """
        Multi-turn conversation. messages = [{"role": "user"|"assistant", "content": "..."}]
        """
        if self._claude_key:
            return self._call_claude_messages(messages, system, max_tokens)
        elif self._openai_key:
            return self._call_openai_messages(messages, system, max_tokens)
        else:
            raise LLMError("No API key configured.")

    def is_available(self) -> bool:
        """Returns True if at least one API key is configured."""
        return bool(self._claude_key or self._openai_key)

    def which_model(self) -> str:
        """Returns the model that will be used."""
        if self._claude_key:
            return CLAUDE_MODEL
        elif self._openai_key:
            return f"{GPT_FALLBACK} (fallback)"
        return "none"

    # ── Claude implementation ─────────────────────────────────────────────────

    def _call_claude(self, prompt: str, system: str,
                     max_tokens: int, temperature: float) -> str:
        messages = [{"role": "user", "content": prompt}]
        return self._call_claude_messages(messages, system, max_tokens, temperature)

    def _call_claude_messages(self, messages: List[Dict],
                               system: str, max_tokens: int,
                               temperature: float = 0.3) -> str:
        import urllib.request

        self._rate_limit()

        body: Dict[str, Any] = {
            "model":      CLAUDE_MODEL,
            "max_tokens": max_tokens,
            "messages":   messages,
        }
        if system:
            body["system"] = system

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data    = json.dumps(body).encode(),
                    headers = {
                        "Content-Type":      "application/json",
                        "x-api-key":         self._claude_key,
                        "anthropic-version": "2023-06-01",
                    },
                    method  = "POST",
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())
                    return self._extract_claude_text(data)

            except urllib.error.HTTPError as e:
                body_text = e.read().decode()
                logger.warning(f"Claude attempt {attempt} HTTP {e.code}: {body_text}")
                if e.code in (429, 529):          # rate limit / overload
                    time.sleep(RETRY_DELAY * attempt)
                elif e.code == 401:
                    raise LLMError("Invalid Claude API key. Check ANTHROPIC_API_KEY in .env")
                elif attempt == MAX_RETRIES:
                    raise LLMError(f"Claude API error {e.code}: {body_text}")
            except Exception as e:
                logger.warning(f"Claude attempt {attempt} failed: {e}")
                if attempt == MAX_RETRIES:
                    raise LLMError(f"Claude request failed: {e}")
                time.sleep(RETRY_DELAY)

        raise LLMError("Claude: max retries exceeded")

    def _extract_claude_text(self, data: Dict) -> str:
        """Pull text from Claude's response structure."""
        content = data.get("content", [])
        texts   = [block.get("text", "") for block in content
                   if block.get("type") == "text"]
        return "\n".join(texts).strip()

    # ── OpenAI fallback ───────────────────────────────────────────────────────

    def _call_openai(self, prompt: str, system: str,
                     max_tokens: int, temperature: float) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self._call_openai_messages(messages, "", max_tokens, temperature)

    def _call_openai_messages(self, messages: List[Dict],
                               system: str, max_tokens: int,
                               temperature: float = 0.3) -> str:
        import urllib.request

        self._rate_limit()

        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        body = {
            "model":       GPT_FALLBACK,
            "messages":    full_messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    "https://api.openai.com/v1/chat/completions",
                    data    = json.dumps(body).encode(),
                    headers = {
                        "Content-Type":  "application/json",
                        "Authorization": f"Bearer {self._openai_key}",
                    },
                    method  = "POST",
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())
                    return data["choices"][0]["message"]["content"].strip()

            except urllib.error.HTTPError as e:
                body_text = e.read().decode()
                logger.warning(f"OpenAI attempt {attempt} HTTP {e.code}: {body_text}")
                if e.code == 429:
                    time.sleep(RETRY_DELAY * attempt)
                elif attempt == MAX_RETRIES:
                    raise LLMError(f"OpenAI API error {e.code}: {body_text}")
            except Exception as e:
                logger.warning(f"OpenAI attempt {attempt} failed: {e}")
                if attempt == MAX_RETRIES:
                    raise LLMError(f"OpenAI request failed: {e}")
                time.sleep(RETRY_DELAY)

        raise LLMError("OpenAI: max retries exceeded")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _rate_limit(self):
        elapsed = time.time() - self._last_call
        if elapsed < self._min_gap:
            time.sleep(self._min_gap - elapsed)
        self._last_call = time.time()

    def _parse_json(self, raw: str) -> Any:
        """Strip markdown fences and parse JSON."""
        clean = raw.strip()
        # Strip ```json ... ``` or ``` ... ```
        if clean.startswith("```"):
            lines = clean.split("\n")
            # Remove first and last fence lines
            inner = [l for l in lines if not l.strip().startswith("```")]
            clean = "\n".join(inner).strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            raise LLMError(f"Model returned invalid JSON: {e}\nRaw: {raw[:300]}")

    @staticmethod
    def _load_key(env_var: str, config_field: str) -> Optional[str]:
        """Try env var first, then config file."""
        import os
        val = os.getenv(env_var)
        if val:
            return val
        try:
            from utils.config import config
            return config.get("api_keys", config_field) or None
        except Exception:
            return None


# ── Module-level singleton ────────────────────────────────────────────────────

_client: Optional[LLMClient] = None


def get_client() -> LLMClient:
    """Return the shared LLMClient instance."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client