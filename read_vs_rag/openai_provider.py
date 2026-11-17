"""Stateless OpenAI Responses adapter for the runner's shared tool loop."""

import json
import time

from .provider import ModelProvider, ProviderError


def response_input(contents):
    items = []
    for message in contents:
        if "response_items" in message:
            items.extend(message["response_items"])
            continue
        for part in message["parts"]:
            if "functionResponse" in part:
                result = part["functionResponse"]
                items.append({"type": "function_call_output", "call_id": result["id"],
                              "output": json.dumps(result["response"], ensure_ascii=False)})
            else:
                items.append({"role": message["role"], "content": part["text"]})
    return items


def response_tools(declarations):
    tools = []
    for declaration in declarations:
        parameters = declaration["parameters"]
        tools.append({
            "type": "function",
            "name": declaration["name"],
            "description": declaration["description"],
            # READ has optional filters/offsets. The runner validates tool arguments.
            "strict": False,
            "parameters": {
                **parameters,
                "type": "object",
                "properties": {name: {**spec, "type": spec["type"].lower()}
                               for name, spec in parameters["properties"].items()},
                "additionalProperties": False,
            },
        })
    return tools


class OpenAI(ModelProvider):
    key_env = "OPENAI_API_KEY"
    endpoint = "https://api.openai.com/v1/responses"

    def _post(self, action, payload):
        url = self.endpoint + ("/input_tokens" if action == "count" else "")
        return self._request(url, f"OpenAI {action}", payload, {"Authorization": f"Bearer {self.key}"})

    def generate(self, system, contents, declarations, *, tag, seed, max_input_tokens, final=False):
        # Responses has no sampling seed. The runner still tracks repeat IDs.
        request = {"model": self.model, "instructions": system, "input": response_input(contents)}
        if "reasoning_effort" in self.config:
            request["reasoning"] = {"effort": self.config["reasoning_effort"]}
        if declarations:
            request["tools"] = response_tools(declarations)
        if final:
            request["text"] = {"format": {"type": "json_object"}}
        output_cap = self.config.get("max_output_tokens", 4096)
        started = time.perf_counter()
        count = self._post("count", request)
        key = self._reserve(count.get("input_tokens"), max_input_tokens, output_cap, tag)
        response = self._post("generate", {**request, "store": False, "max_output_tokens": output_cap,
                                          "include": ["reasoning.encrypted_content"]})
        usage = response.get("usage") or {}
        inp, out, total = (usage.get(k) for k in ("input_tokens", "output_tokens", "total_tokens"))
        cached = (usage.get("input_tokens_details") or {}).get("cached_tokens", 0)
        thinking = (usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0)
        if (any(type(v) is not int or v < 0 for v in (inp, out, total, cached, thinking))
                or cached > inp or thinking > out or total != inp + out):
            raise ProviderError("Missing or inconsistent OpenAI usage; reservation retained")
        cost = ((inp - cached) * self.pricing["input_per_million"] +
                cached * self.pricing["cached_input_per_million"] +
                out * self.pricing["output_per_million"]) / 1e6
        self.ledger.settle(key, cost, total, usage)
        call = {"model": self.model, "model_version": response.get("model"),
                "input_tokens": inp, "output_tokens": out - thinking, "thinking_tokens": thinking,
                "cached_tokens": cached, "total_tokens": total, "cost_usd": cost,
                "latency_s": time.perf_counter() - started, "tag": tag,
                "finish_reason": response.get("status")}
        self.calls.append(call)
        exact = self.config.get("expected_model")
        if exact and response.get("model") != exact:
            raise ProviderError("Returned OpenAI model differs from the configured snapshot; usage recorded")
        # The server count and output allowance are checked again against billed usage.
        if inp > count["input_tokens"] or out > output_cap:
            raise ProviderError("OpenAI usage exceeded the token reservation; usage recorded, run stopped")
        parts = []
        output = response.get("output") or []
        if response.get("status") == "incomplete":
            reason = (response.get("incomplete_details") or {}).get("reason")
            raise ValueError(f"OpenAI response incomplete ({reason}); usage recorded")
        if response.get("status") != "completed":
            raise ProviderError("OpenAI response did not complete; usage recorded")
        for item in output:
            if item["type"] == "function_call":
                args = json.loads(item["arguments"])
                if not isinstance(args, dict):
                    raise ValueError("OpenAI function arguments must be a JSON object")
                parts.append({"functionCall": {"name": item["name"], "id": item["call_id"], "args": args}})
            elif item["type"] == "message":
                for content in item["content"]:
                    if content["type"] == "output_text":
                        parts.append({"text": content["text"]})
                    elif content["type"] == "refusal":
                        raise ValueError("OpenAI declined to generate an answer")
        # Replay complete output items, including encrypted reasoning, on the next turn.
        return {"role": "model", "parts": parts, "response_items": output}, call
