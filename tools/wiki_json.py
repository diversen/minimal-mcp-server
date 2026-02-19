import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tools.registry import make_tool_text_response, register_tool


def _resolve_language(language: str | None) -> str:
    if not language:
        return "en"

    normalized = language.strip().lower()
    if not normalized:
        return "en"

    allowed = set("abcdefghijklmnopqrstuvwxyz-")
    if any(char not in allowed for char in normalized):
        raise ValueError("`language` must be a valid Wikipedia language code, e.g. 'en'.")

    return normalized


@register_tool(
    name="get_wikipedia_pages_json",
    description=(
        "Fetch plain-text article content from Wikipedia and return only "
        "the API `query.pages` JSON payload."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Wikipedia article title, e.g. 'Earth'.",
            },
            "language": {
                "type": "string",
                "description": "Wikipedia language code, e.g. 'en'. Defaults to 'en'.",
            },
        },
        "required": ["title"],
        "additionalProperties": False,
    },
)
def get_wikipedia_pages_json(arguments: dict[str, Any]) -> dict[str, Any]:
    title = arguments.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("`title` is required and must be a non-empty string.")

    language = _resolve_language(arguments.get("language"))

    params = {
        "action": "query",
        "prop": "extracts",
        "titles": title.strip(),
        "explaintext": "1",
        "redirects": "1",
        "format": "json",
        "formatversion": "2",
    }
    url = f"https://{language}.wikipedia.org/w/api.php?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "simple-mcp-starlette-server/0.1"})

    try:
        with urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise ValueError(f"Wikipedia request failed with HTTP {exc.code}.") from exc
    except URLError as exc:
        raise ValueError(f"Wikipedia request failed: {exc.reason}.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("Wikipedia response was not valid JSON.") from exc

    query = payload.get("query", {})
    pages = query.get("pages")
    if not isinstance(pages, list):
        raise ValueError("Wikipedia response did not include a valid `query.pages` payload.")

    return make_tool_text_response(
        text=json.dumps(pages, ensure_ascii=False),
        structured_content={"pages": pages},
    )
