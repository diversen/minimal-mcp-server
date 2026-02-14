# Simple MCP Server (Starlette, streamable-http)

Minimal MCP server in Python 3.11 using Starlette with:
- `streamable-http` transport (`POST /mcp`)
- Bearer token authentication (`Authorization: Bearer <token>`) with OAuth-style challenge metadata
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
export MCP_AUTHORIZATION_SERVERS="https://auth.example.com"
export MCP_ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
export HOST="0.0.0.0"
export PORT="5000"
```

### `.env` variables reference

- `MCP_AUTH_TOKEN` (required): Fixed bearer token used by the server to authenticate requests. Must be set.
- `HOST` (optional): Bind address for Uvicorn. Default can be `0.0.0.0` for local network access.
- `PORT` (optional): Server port. Recommended default in this project is `5000`.
- `MCP_ALLOWED_ORIGINS` (optional): Comma-separated origin allowlist for browser clients. Leave unset to disable origin filtering.
- `MCP_AUTHORIZATION_SERVERS` (optional): Comma-separated OAuth authorization server URLs returned by discovery metadata. Set this only if you use real OAuth discovery.
- `MCP_REQUIRED_SCOPE` (optional): Scope name advertised in metadata/challenges. Useful for OAuth setups; leave empty for fixed-token mode.
- `MCP_RESOURCE_DOCUMENTATION` (optional): URL to docs for your protected MCP resource.

For simple fixed-token mode, only `MCP_AUTH_TOKEN` is required.

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
- Wrong token -> `401`
- Missing server token config (`MCP_AUTH_TOKEN`) -> `500`
- `401` includes `WWW-Authenticate: Bearer ... resource_metadata=".../.well-known/oauth-protected-resource/mcp"`

## OAuth Discovery Metadata

These unauthenticated endpoints are available for OAuth resource discovery:

- `GET /.well-known/oauth-protected-resource`
- `GET /.well-known/oauth-protected-resource/mcp`

They return resource metadata JSON including:
- `resource` (your MCP endpoint URL)
- `authorization_servers` (from `MCP_AUTHORIZATION_SERVERS`)
- `bearer_methods_supported`
- optional `scopes_supported` (from `MCP_REQUIRED_SCOPE`)
- optional `resource_documentation` (from `MCP_RESOURCE_DOCUMENTATION`)

Note: this project now implements OAuth-style discovery/challenge conventions, but access-token validation is still the simple fixed-token check using `MCP_AUTH_TOKEN`.

## Origin validation

- If `MCP_ALLOWED_ORIGINS` is set, requests with an `Origin` header must match one of those values.
- Non-matching origins are rejected with `403`.

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
