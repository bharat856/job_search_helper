from __future__ import annotations

import json
import time

from pydantic import BaseModel, ValidationError

from ..config import get_settings


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
