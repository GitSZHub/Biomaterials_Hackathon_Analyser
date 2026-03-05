"""
LLM Client -- Claude primary, GPT-4o fallback.

Design principles:
- Never blocks the UI thread. All calls go through StreamWorker (QThread).
- Prompts are passed in by the caller -- this module is pure infrastructure.
- Graceful degradation: if no API key is present, returns a clear error string
  rather than raising. The UI can display this without crashing.
- Streaming: chunks are emitted via Qt signals so the UI updates progressively.
"""

from __future__ import annotations

import os
from typing import Generator, Optional

from PyQt6.QtCore import QThread, pyqtSignal


def _get_anthropic():
    try:
        import anthropic
        return anthropic
    except ImportError:
        return None

def _get_openai():
    try:
        import openai
        return openai
    except ImportError:
        return None


class LLMClient:
    """
    Thin wrapper around the Claude (and optionally GPT-4o) APIs.

    Usage (non-streaming, for quick calls):
        client = LLMClient(anthropic_key="sk-...")
        text = client.complete(system_prompt, user_prompt)

    Usage (streaming, via QThread):
        worker = client.stream_worker(system_prompt, user_prompt, tag="strategy")
        worker.chunk.connect(my_slot)
        worker.finished.connect(my_done_slot)
        worker.error.connect(my_error_slot)
        worker.start()
    """

    CLAUDE_MODEL = "claude-sonnet-4-6"
    GPT_MODEL = "gpt-4o"
    MAX_TOKENS = 4096

    def __init__(
        self,
        anthropic_key: Optional[str] = None,
        openai_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.anthropic_key = anthropic_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.openai_key = openai_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or self.CLAUDE_MODEL

    @property
    def claude_available(self) -> bool:
        return bool(self.anthropic_key) and _get_anthropic() is not None

    @property
    def openai_available(self) -> bool:
        return bool(self.openai_key) and _get_openai() is not None

    @property
    def any_available(self) -> bool:
        return self.claude_available or self.openai_available

    def status_message(self) -> str:
        if self.claude_available:
            return f"Claude ({self.model})"
        if self.openai_available:
            return "GPT-4o (fallback -- Claude key missing)"
        return "No LLM available -- set ANTHROPIC_API_KEY or OPENAI_API_KEY"

    # ------------------------------------------------------------------
    # Synchronous completion (call from a worker thread, not the UI thread)
    # ------------------------------------------------------------------

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if self.claude_available:
            return self._claude_complete(system_prompt, user_prompt)
        if self.openai_available:
            return self._openai_complete(system_prompt, user_prompt)
        return "[ERROR] No LLM API key configured. Set ANTHROPIC_API_KEY in your environment."

    def _claude_complete(self, system_prompt: str, user_prompt: str) -> str:
        anthropic = _get_anthropic()
        try:
            client = anthropic.Anthropic(api_key=self.anthropic_key)
            message = client.messages.create(
                model=self.model,
                max_tokens=self.MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return message.content[0].text
        except Exception as e:
            return f"[ERROR] Claude API call failed: {e}"

    def _openai_complete(self, system_prompt: str, user_prompt: str) -> str:
        openai = _get_openai()
        try:
            client = openai.OpenAI(api_key=self.openai_key)
            response = client.chat.completions.create(
                model=self.GPT_MODEL,
                max_tokens=self.MAX_TOKENS,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[ERROR] OpenAI API call failed: {e}"

    # ------------------------------------------------------------------
    # Streaming -- returns a ready-to-start QThread worker
    # ------------------------------------------------------------------

    def stream_worker(
        self,
        system_prompt: str,
        user_prompt: str,
        tag: str = "",
    ) -> "StreamWorker":
        """
        Returns a StreamWorker. Connect signals before calling .start().

        Signals:
            chunk(tag, text_chunk)  -- each streamed token
            finished(tag, full_text) -- on completion
            error(tag, message)      -- on failure
        """
        return StreamWorker(self, system_prompt, user_prompt, tag)

    def _claude_stream(self, system_prompt: str, user_prompt: str) -> Generator[str, None, None]:
        anthropic = _get_anthropic()
        client = anthropic.Anthropic(api_key=self.anthropic_key)
        with client.messages.stream(
            model=self.model,
            max_tokens=self.MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    def _openai_stream(self, system_prompt: str, user_prompt: str) -> Generator[str, None, None]:
        openai = _get_openai()
        client = openai.OpenAI(api_key=self.openai_key)
        stream = client.chat.completions.create(
            model=self.GPT_MODEL,
            max_tokens=self.MAX_TOKENS,
            stream=True,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class StreamWorker(QThread):
    """
    QThread that streams an LLM response and emits Qt signals.

    Connect chunk/finished/error signals before calling .start().
    tag is a free-form string the caller uses to route signals to the right UI widget.
    """

    chunk = pyqtSignal(str, str)      # (tag, text_chunk)
    finished = pyqtSignal(str, str)   # (tag, full_text)
    error = pyqtSignal(str, str)      # (tag, error_message)

    def __init__(
        self,
        client: LLMClient,
        system_prompt: str,
        user_prompt: str,
        tag: str = "",
    ):
        super().__init__()
        self._client = client
        self._system = system_prompt
        self._user = user_prompt
        self._tag = tag

    def run(self):
        if not self._client.any_available:
            self.error.emit(self._tag, self._client.status_message())
            return

        accumulated = []
        try:
            if self._client.claude_available:
                gen = self._client._claude_stream(self._system, self._user)
            else:
                gen = self._client._openai_stream(self._system, self._user)

            for text in gen:
                accumulated.append(text)
                self.chunk.emit(self._tag, text)

            self.finished.emit(self._tag, "".join(accumulated))

        except Exception as e:
            self.error.emit(self._tag, str(e))
