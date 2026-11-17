"""Model providers and durable reservations before generation calls.

No hidden retries. Ambiguous network failures retain their reserved upper estimate.
Prices are user-supplied estimates, not a provider-side billing guarantee.
"""

import json
import math
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import date
from pathlib import Path

from .io import append_jsonl, load_jsonl, utcnow


class BudgetExceeded(RuntimeError):
    def __init__(self, message, scope="question"):
        super().__init__(message)
        self.scope = scope


class ProviderError(RuntimeError):
    pass


class Ledger:
    def __init__(self, path, max_cost, max_tokens):
        self.path, self.max_cost, self.max_tokens = Path(path), max_cost, max_tokens
        if max_cost <= 0 or max_tokens <= 0:
            raise ValueError("Positive run cost/token limits required")
        self.entries = {}
        if self.path.exists():
            for event in load_jsonl(self.path):
                if event["event"] == "reserve":
                    self.entries[event["id"]] = event
                elif event["event"] == "settle" and event["id"] in self.entries:
                    self.entries[event["id"]] = event
                else:
                    raise ValueError("Malformed budget ledger")

    @property
    def spent(self):
        return sum(e["cost_usd"] for e in self.entries.values())

    @property
    def tokens(self):
        return sum(e["tokens"] for e in self.entries.values())

    def reserve(self, cost, tokens, tag):
        if cost < 0 or tokens < 0:
            raise ValueError("Invalid reservation")
        if self.spent + cost > self.max_cost or self.tokens + tokens > self.max_tokens:
            raise BudgetExceeded("Run budget reached before issuing the next model request", scope="run")
        event = {"event": "reserve", "id": uuid.uuid4().hex, "at": utcnow(), "tag": tag,
                 "cost_usd": cost, "tokens": tokens}
        append_jsonl(self.path, event)
        self.entries[event["id"]] = event
        return event["id"]

    def settle(self, key, cost, tokens, usage):
        if key not in self.entries:
            raise ValueError("Unknown reservation")
        event = {**self.entries[key], "event": "settle", "at": utcnow(), "cost_usd": cost,
                 "tokens": tokens, "usage": usage}
        append_jsonl(self.path, event)
        self.entries[key] = event


class ModelProvider:
    key_env = ""

    def __init__(self, config, ledger):
        self.config, self.ledger = config, ledger
        key_env = config.get("api_key_env", self.key_env)
        self.key = os.environ.get(key_env)
        if not self.key:
            raise ValueError(f"Set {key_env} locally; never commit the key")
        self.model = config["model"]
        if not self.model or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._" for c in self.model):
            raise ValueError("Invalid model identifier")
        self.pricing = config["pricing"]
        for k in ("input_per_million", "output_per_million", "cached_input_per_million"):
            rate = self.pricing[k]
            if type(rate) not in (int, float) or not math.isfinite(rate) or rate < 0:
                raise ValueError(f"Invalid token price: {k}")
        if self.pricing["cached_input_per_million"] > self.pricing["input_per_million"]:
            raise ValueError("Cached input price exceeds standard input price")
        output_cap = config.get("max_output_tokens", 4096)
        if type(output_cap) is not int or output_cap <= 0:
            raise ValueError("max_output_tokens must be a positive integer")
        self.calls = []

    def _request(self, url, action, payload, headers):
        request = urllib.request.Request(url,
                                         data=json.dumps(payload).encode(),
                                         headers={"Content-Type": "application/json", **headers},
                                         method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.config.get("timeout_s", 90)) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            # Do not log response bodies, request headers, or credentials.
            raise ProviderError(f"{action} returned HTTP {exc.code}; no automatic retry") from None
        except (OSError, ValueError) as exc:
            raise ProviderError(f"{action} failed ({type(exc).__name__}); no automatic retry") from None

    def _reserve(self, input_count, max_input_tokens, output_cap, tag):
        if type(input_count) is not int or input_count < 0:
            raise ProviderError("Provider token count missing or invalid")
        cap = min(max_input_tokens, self.pricing.get("input_tier_limit", max_input_tokens))
        if input_count > cap:
            raise BudgetExceeded(f"Input is {input_count} tokens, above per-call/tariff cap {cap}")
        cost = (input_count * self.pricing["input_per_million"] +
                output_cap * self.pricing["output_per_million"]) / 1e6
        return self.ledger.reserve(cost, input_count + output_cap, tag)


class Gemini(ModelProvider):
    key_env = "GEMINI_API_KEY"

    def __init__(self, config, ledger):
        super().__init__(config, ledger)
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/models/" + self.model
        if not self.pricing.get("valid_through") or date.today() > date.fromisoformat(self.pricing["valid_through"]):
            raise ValueError("Pricing/model validity date expired; verify availability/rates and create a new config")

    def _post(self, action, payload):
        return self._request(self.endpoint + ":" + action, f"Gemini {action}", payload, {"x-goog-api-key": self.key})

    def generate(self, system, contents, declarations, *, tag, seed, max_input_tokens, final=False):
        config = {"temperature": self.config.get("temperature", 0.),
                  "maxOutputTokens": self.config.get("max_output_tokens", 4096), "seed": seed}
        if "thinking_budget" in self.config:
            config["thinkingConfig"] = {"thinkingBudget": self.config["thinking_budget"], "includeThoughts": False}
        if final:
            config["responseMimeType"] = "application/json"
        request = {"contents": contents, "systemInstruction": {"parts": [{"text": system}]},
                   "generationConfig": config}
        if declarations:
            request["tools"] = [{"functionDeclarations": declarations}]
        started = time.perf_counter()
        # Exact server-side input count, including function declarations and history.
        count = self._post("countTokens", {"generateContentRequest": {"model": "models/" + self.model, **request}})
        key = self._reserve(count.get("totalTokens"), max_input_tokens, config["maxOutputTokens"], tag)
        response = self._post("generateContent", request)
        usage = response.get("usageMetadata", {})
        if "promptTokenCount" not in usage or "totalTokenCount" not in usage:
            raise ProviderError("Missing usage metadata; pessimistic reservation retained")
        inp = usage["promptTokenCount"]
        out = usage.get("candidatesTokenCount", 0)
        thinking = usage.get("thoughtsTokenCount", 0)
        cached = usage.get("cachedContentTokenCount", 0)
        tool_prompt = usage.get("toolUsePromptTokenCount", 0)
        cost = ((inp - cached + tool_prompt) * self.pricing["input_per_million"] +
                cached * self.pricing["cached_input_per_million"] +
                (out + thinking) * self.pricing["output_per_million"]) / 1e6
        self.ledger.settle(key, cost, usage["totalTokenCount"], usage)
        call = {"model": self.model, "model_version": response.get("modelVersion"),
                "input_tokens": inp, "output_tokens": out, "thinking_tokens": thinking,
                "tool_use_prompt_tokens": tool_prompt,
                "cached_tokens": cached, "total_tokens": usage["totalTokenCount"],
                "cost_usd": cost, "latency_s": time.perf_counter() - started, "tag": tag}
        self.calls.append(call)
        expected = self.config.get("expected_model_prefix")
        if expected and not str(response.get("modelVersion", "")).startswith(expected):
            raise ProviderError("Provider modelVersion differs from expected prefix; billed call recorded, stopping drift")
        candidates = response.get("candidates", [])
        if not candidates or "content" not in candidates[0]:
            raise ProviderError("Model returned no candidate (blocked or empty); billed usage recorded")
        call["finish_reason"] = candidates[0].get("finishReason")
        return candidates[0]["content"], call


def make_provider(config, ledger):
    name = config.get("name", "gemini")
    if name == "gemini":
        return Gemini(config, ledger)
    if name == "openai":
        from .openai_provider import OpenAI
        return OpenAI(config, ledger)
    raise ValueError(f"Unknown model provider: {name}")
