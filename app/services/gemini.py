from __future__ import annotations

import json
import time

from pydantic import BaseModel, ValidationError

from ..config import get_settings


class GeminiConnectionError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _model_name(model) -> str:
    return str(getattr(model, "name", model)).removeprefix("models/")


def _supports_generation(model) -> bool:
    actions = (
        getattr(model, "supported_actions", None)
        or getattr(model, "supported_generation_methods", None)
        or []
    )
    actions = [str(action).lower() for action in actions]
    return bool(actions) and any("generate" in action or "content" in action for action in actions)


class GeminiService:
    def __init__(self, api_key: str | None = None, client=None):
        self.settings = get_settings()
        self.calls = 0
        if client is not None:
            self.client = client
        elif api_key or self.settings.gemini_api_key:
            from google import genai

            self.client = genai.Client(api_key=api_key or self.settings.gemini_api_key)
        else:
            self.client = None

    def structured(self, prompt: str, schema: type[BaseModel], model: str | None = None):
        if not self.client:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        if self.calls >= self.settings.max_llm_calls_per_run:
            raise RuntimeError("LLM call limit reached")
        last = None
        for attempt in range(3):
            try:
                self.calls += 1
                try:
                    from google.genai import types

                    config = types.GenerateContentConfig(
                        response_mime_type="application/json", response_schema=schema
                    )
                except ImportError:  # lightweight mocked clients in tests
                    config = None
                response = self.client.models.generate_content(
                    model=model or self.settings.gemini_model, contents=prompt, config=config
                )
                return schema.model_validate(json.loads(response.text))
            except (ValidationError, json.JSONDecodeError, Exception) as exc:
                last = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        raise RuntimeError(f"Gemini structured response failed: {last}")

    def list_models(self) -> list[dict]:
        if not self.client:
            raise GeminiConnectionError("authentication", "GEMINI_API_KEY is not configured")
        try:
            models = list(self.client.models.list())
        except Exception as exc:
            message = str(exc).lower()
            code = (
                "authentication"
                if any(
                    x in message for x in ("401", "403", "api key", "permission", "unauthenticated")
                )
                else "provider"
            )
            raise GeminiConnectionError(code, "Gemini model listing failed") from exc
        return [
            {"name": _model_name(model), "supports_generation": _supports_generation(model)}
            for model in models
        ]

    def test_connection(self, selected_model: str) -> dict:
        models = self.list_models()
        normalized = selected_model.removeprefix("models/")
        available = next((model for model in models if model["name"] == normalized), None)
        if not available:
            raise GeminiConnectionError(
                "model_not_found", f"Model '{normalized}' is not accessible to this API key"
            )
        if not available["supports_generation"]:
            raise GeminiConnectionError(
                "unsupported", f"Model '{normalized}' does not support content generation"
            )
        try:
            response = self.client.models.generate_content(
                model=normalized,
                contents="Reply with exactly: Gemini connection test successful.",
            )
            return {
                "model": normalized,
                "response_preview": str(response.text or "")[:120],
                "models": models,
            }
        except Exception as exc:
            message = str(exc).lower()
            if any(
                x in message for x in ("401", "403", "api key", "permission", "unauthenticated")
            ):
                code = "authentication"
            elif any(x in message for x in ("429", "quota", "resource_exhausted", "rate limit")):
                code = "quota"
            elif "404" in message or "not found" in message:
                code = "model_not_found"
            else:
                code = "provider"
            raise GeminiConnectionError(code, "Gemini connection test failed") from exc
