"""Provider-independent cached completion client with a persistent hard budget.

Paid endpoints require explicit model and conservative per-call upper-bound
pricing via environment variables. Unknown pricing fails closed. Keys are read
only from documented provider variables and are never persisted. Failed paid
requests retain their reservation because a timeout can still be billable.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import urllib.request
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


class LLMClient:
    def __init__(self, backend="mock", model="mock", cache_dir="results/llm/cache",
                 budget_usd=5.0, base_url=None, transport=None, max_tokens=512,
                 price_input_per_million=None, price_output_per_million=None):
        self.backend, self.model = backend, model
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.budget = min(float(budget_usd), 5.0)
        self.base_url = base_url
        self.transport = transport or self._request
        self.max_tokens = max_tokens
        self.prices = (price_input_per_million, price_output_per_million)
        self.ledger = self.cache.parent / "budget.json"
        self.last = {}

    @staticmethod
    def _request(url, payload, headers, timeout=120):
        request = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json", **headers})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def _reserve(self, messages):
        if self.backend in ("mock", "ollama", "llamacpp"):
            return 0.0
        if any(p is None or p < 0 for p in self.prices):
            raise BudgetExceeded("Verified upper-bound pricing is required for paid inference")
        # UTF-8 bytes upper-bound ordinary token counts. Reject oversized input
        # rather than making an unbounded billable request.
        input_bound = len(json.dumps(messages, ensure_ascii=False).encode()) + 2048
        reservation = (input_bound * self.prices[0] + self.max_tokens * self.prices[1]) / 1e6
        state = json.loads(self.ledger.read_text()) if self.ledger.exists() else {"reserved_usd": 0.0}
        if state["reserved_usd"] + reservation > self.budget:
            raise BudgetExceeded("Hard per-paper budget cap reached before request")
        state["reserved_usd"] += reservation
        self.ledger.write_text(json.dumps(state, indent=2))
        return reservation

    def complete(self, messages, seed, temperature=0):
        request = dict(backend=self.backend, model=self.model, messages=messages,
                       seed=seed, temperature=temperature, max_tokens=self.max_tokens)
        digest = hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        path = self.cache / f"{digest}.json"
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            self.last = dict(record, cached=True)
            return record["response"]
        reservation = self._reserve(messages)
        started = time.monotonic()
        if self.backend == "mock":
            raw = {"mock": True}
            response = '{"steps": []}'
        elif self.backend == "ollama":
            raw = self.transport((self.base_url or "http://127.0.0.1:11434") + "/api/chat",
                dict(model=self.model, messages=messages, stream=False, format="json", keep_alive="5m",
                     options=dict(seed=seed, temperature=temperature, num_predict=self.max_tokens, num_ctx=4096, num_thread=2)), {})
            response = raw["message"]["content"]
        elif self.backend in ("openai", "llamacpp"):
            headers = {} if self.backend == "llamacpp" else {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]}
            raw = self.transport((self.base_url or "https://api.openai.com/v1") + "/chat/completions",
                dict(model=self.model, messages=messages, seed=seed, temperature=temperature, max_tokens=self.max_tokens), headers)
            response = raw["choices"][0]["message"]["content"]
        elif self.backend == "anthropic":
            raw = self.transport("https://api.anthropic.com/v1/messages",
                dict(model=self.model, messages=messages, temperature=temperature, max_tokens=self.max_tokens),
                {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"})
            response = "".join(c.get("text", "") for c in raw["content"])
        else:
            raise ValueError(self.backend)
        record = dict(request, response=response, raw=raw, elapsed_seconds=time.monotonic() - started,
                      reserved_usd=reservation, prompt_sha256=digest, cached=False,
                      seed_supported=self.backend != "anthropic", mock=self.backend == "mock")
        path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        self.last = record
        return response


def discover():
    """Return public availability evidence, never key values."""
    evidence = {"api_key_variables_present": [key for key in
        ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY") if os.environ.get(key)],
        "ollama_cli": shutil.which("ollama"), "llamacpp_cli": shutil.which("llama-server")}
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as response:
            evidence["ollama_models"] = json.load(response).get("models", [])
    except Exception as exc:
        evidence["ollama_error"] = str(exc)
    return evidence
