# Simple MCP Server (Starlette, streamable-http)

Minimal MCP server in Python 3.11 using Starlette with:
- `streamable-http` transport (`POST /mcp`)
- Bearer token authentication (`Authorization: Bearer <token>`)
- One tool: `get_locale_date_time`

## Requirements

- Python `3.11+`

## Setup

```bash
git clone https://github.com/diversen/minimal-mcp-server.git
cd minimal-mcp-server
uv sync
```

Set environment variables:

```bash
cp .env.example .env
export MCP_AUTH_TOKEN="your-very-secret-token"
export HOST="0.0.0.0"
export PORT="5000"
```

## Run

```bash
uv run uvicorn server:app --host "${HOST}" --port "${PORT}"
```

For development (auto-reload on `.py` changes):

```bash
uv run uvicorn server:app --host "${HOST}" --port "${PORT}" --reload
```

## MCP flow example

### 1) `initialize`

```bash
curl -s -X POST "http://127.0.0.1:5000/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-very-secret-token" \
  -d '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"initialize",
    "params":{
      "protocolVersion":"2025-06-18",
      "capabilities":{},
      "clientInfo":{"name":"demo-client","version":"0.1.0"}
    }
  }'
```

### 2) `tools/list`

```bash
curl -s -X POST "http://127.0.0.1:5000/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-very-secret-token" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

### 3) `tools/call`

```bash
curl -s -X POST "http://127.0.0.1:5000/mcp" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-very-secret-token" \
  -d '{
    "jsonrpc":"2.0",
    "id":3,
    "method":"tools/call",
    "params":{
      "name":"get_locale_date_time",
      "arguments":{"locale":"Copenhagen"}
    }
  }'
```

## Auth behavior

- Missing/invalid auth header -> `401`
- Wrong token -> `403`
- Missing server token config (`MCP_AUTH_TOKEN`) -> `500`

## Notes

- Use `POST /mcp` for streamable-http requests.
- This starter intentionally keeps scope small (`tools` only).

## Adding new tools

Tools are split into modules under `tools/` and registered with `@register_tool(...)`.

1. Create a new file under `tools/` (example: `tools/echo.py`).
2. Define `name`, `description`, and `input_schema`.
3. Return MCP tool output with `content` and optional `structuredContent`.
4. Import the module in `tools/__init__.py` so registration runs at startup.

Example:

```python
from typing import Any

from tools.registry import register_tool

@register_tool(
    name="echo",
    description="Echo a string.",
    input_schema={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
        "additionalProperties": False,
    },
)
def echo(arguments: dict[str, Any]) -> dict[str, Any]:
    text = arguments["text"]
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": {"text": text},
        "isError": False,
    }
```

No changes are needed in `server.py` when adding tools through this registry flow.
