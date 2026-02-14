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
uvicorn server:app --host "${HOST}" --port "${PORT}"
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
