"""Shared client for structured output from a local Ollama model."""

import os
from typing import TypeVar

from dotenv import load_dotenv
from ollama import Client
from pydantic import BaseModel

DEFAULT_MODEL = "qwen2.5:3b"
DEFAULT_HOST = "http://localhost:11434"

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LocalAIError(RuntimeError):
    """Raised when the local Ollama model cannot produce structured output."""


def generate_structured(
    text: str,
    *,
    instructions: str,
    schema: type[SchemaT],
    client: Client | None = None,
    model: str | None = None,
) -> SchemaT:
    """Generate and validate a Pydantic object with a local Ollama model."""

    load_dotenv()
    selected_model = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
    selected_client = client or Client(
        host=os.getenv("OLLAMA_HOST", DEFAULT_HOST)
    )

    try:
        response = selected_client.chat(
            model=selected_model,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": text},
            ],
            format=schema.model_json_schema(),
            options={"temperature": 0},
        )
        content = response.message.content
        if not content:
            raise LocalAIError("The local model returned an empty response")
        return schema.model_validate_json(content)
    except LocalAIError:
        raise
    except Exception as error:
        raise LocalAIError(f"Local Ollama request failed: {error}") from error
