"""Optional localhost-only language hint. Financial evidence never enters the request."""
import http.client
import json
import os

from src.copilot_language import LANGUAGES


def local_language_hint(question):
    model = os.getenv("FUNDCOPILOT_OLLAMA_MODEL", "").strip()
    if not model:
        return None
    connection = http.client.HTTPConnection("127.0.0.1", 11434, timeout=1)
    try:
        payload = json.dumps({
            "model": model,
            "system": "Classify the input language. Return exactly one label: en, fr, ar, darija.",
            "prompt": question[:500],
            "stream": False,
            "options": {"temperature": 0, "num_predict": 8},
        })
        connection.request("POST", "/api/generate", payload, {"Content-Type": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            return None
        body = json.loads(response.read(16384))
        label = body.get("response") if isinstance(body, dict) else None
        return label.strip().lower() if isinstance(label, str) and label.strip().lower() in LANGUAGES else None
    except (OSError, ValueError, http.client.HTTPException):
        return None
    finally:
        connection.close()
