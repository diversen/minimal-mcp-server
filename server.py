import json
import os
from urllib.parse import urlsplit

from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

import tools  # noqa: F401
from tools.registry import call_tool, list_tools

DEFAULT_PROTOCOL_VERSION = "2025-06-18"
SUPPORTED_PROTOCOL_VERSIONS = {
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
}
SERVER_NAME = "simple-mcp-starlette-server"
SERVER_VERSION = "0.1.0"


def _jsonrpc_error(code: int, message: str, request_id=None, data=None) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    if data is not None:
        payload["error"]["data"] = data
    return payload


def _jsonrpc_result(result: dict, request_id) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def _allowed_origins() -> set[str]:
    configured = os.getenv("MCP_ALLOWED_ORIGINS", "")
    return {origin.strip() for origin in configured.split(",") if origin.strip()}


def _protocol_error_response(request_id, detail: str) -> JSONResponse:
    return JSONResponse(
        _jsonrpc_error(-32602, "Invalid params", request_id, detail),
        status_code=400,
    )


def _build_mcp_json_response(payload: dict, protocol_version: str, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        payload,
        status_code=status_code,
        headers={"MCP-Protocol-Version": protocol_version},
    )


def _base_url(request: Request) -> str:
    split = urlsplit(str(request.url))
    return f"{split.scheme}://{split.netloc}"


def _resource_metadata_url(request: Request) -> str:
    return f"{_base_url(request)}/.well-known/oauth-protected-resource/mcp"


def _authorization_servers() -> list[str]:
    configured = os.getenv("MCP_AUTHORIZATION_SERVERS", "")
    return [server.strip() for server in configured.split(",") if server.strip()]


def _www_authenticate_header(request: Request, error: str | None = None, description: str | None = None) -> str:
    parts = [
        'Bearer realm="mcp"',
        f'resource_metadata="{_resource_metadata_url(request)}"',
    ]
    scope = os.getenv("MCP_REQUIRED_SCOPE", "").strip()
    if scope:
        parts.append(f'scope="{scope}"')
    if error:
        parts.append(f'error="{error}"')
    if description:
        parts.append(f'error_description="{description}"')
    return ", ".join(parts)


def _bearer_error(
    request: Request,
    detail: str,
    *,
    status_code: int = 401,
    error: str | None = None,
) -> JSONResponse:
    headers = {"WWW-Authenticate": _www_authenticate_header(request, error=error, description=detail)}
    return JSONResponse({"error": detail}, status_code=status_code, headers=headers)


def _negotiate_protocol_version(headers: Headers, method: str, params: dict) -> str:
    header_version = headers.get("mcp-protocol-version")
    if header_version:
        if header_version not in SUPPORTED_PROTOCOL_VERSIONS:
            raise ValueError(
                f"Unsupported MCP-Protocol-Version header: {header_version}. "
                f"Supported versions: {sorted(SUPPORTED_PROTOCOL_VERSIONS)}."
            )
        negotiated = header_version
    else:
        negotiated = DEFAULT_PROTOCOL_VERSION

    if method == "initialize":
        requested_version = (params or {}).get("protocolVersion")
        if requested_version and requested_version not in SUPPORTED_PROTOCOL_VERSIONS:
            raise ValueError(
                f"Unsupported initialize protocolVersion: {requested_version}. "
                f"Supported versions: {sorted(SUPPORTED_PROTOCOL_VERSIONS)}."
            )
        if requested_version:
            negotiated = requested_version

    return negotiated


def _tools_list_result() -> dict:
    return {"tools": list_tools()}


def _handle_mcp_method(method: str, params: dict, request_id, protocol_version: str):
    if method == "initialize":
        return _jsonrpc_result(
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
            request_id,
        )

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return _jsonrpc_result(_tools_list_result(), request_id)

    if method == "tools/call":
        try:
            name = (params or {}).get("name")
            arguments = (params or {}).get("arguments")
            result = call_tool(name, arguments)
            return _jsonrpc_result(result, request_id)
        except KeyError as exc:
            return _jsonrpc_error(-32601, str(exc), request_id)
        except ValueError as exc:
            return _jsonrpc_error(-32602, "Invalid params", request_id, str(exc))

    return _jsonrpc_error(-32601, f"Method not found: {method}", request_id)


def _auth_error(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse({"error": detail}, status_code=status_code)


def _is_authorized(request: Request) -> Response | None:
    expected_token = os.getenv("MCP_AUTH_TOKEN", "").strip()
    if not expected_token:
        return _auth_error(
            500,
            "Server is not configured: MCP_AUTH_TOKEN is missing.",
        )

    header = request.headers.get("authorization")
    if not header:
        return _bearer_error(request, "Missing Authorization header.", error="invalid_token")

    parts = header.split(" ", maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return _bearer_error(
            request,
            "Expected Authorization: Bearer <token>.",
            error="invalid_request",
        )

    incoming_token = parts[1].strip()
    if incoming_token != expected_token:
        return _bearer_error(request, "Invalid token.", error="invalid_token")

    return None


async def health(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def oauth_protected_resource_metadata(request: Request) -> JSONResponse:
    mcp_resource = f"{_base_url(request)}/mcp"
    payload = {
        "resource": mcp_resource,
        "authorization_servers": _authorization_servers(),
        "bearer_methods_supported": ["header"],
    }
    required_scope = os.getenv("MCP_REQUIRED_SCOPE", "").strip()
    if required_scope:
        payload["scopes_supported"] = [required_scope]
    docs_url = os.getenv("MCP_RESOURCE_DOCUMENTATION", "").strip()
    if docs_url:
        payload["resource_documentation"] = docs_url
    return JSONResponse(payload)


async def mcp_endpoint(request: Request) -> Response:
    allowed_origins = _allowed_origins()
    origin = request.headers.get("origin")
    if origin and allowed_origins and origin not in allowed_origins:
        return JSONResponse({"error": f"Forbidden origin: {origin}"}, status_code=403)

    auth_response = _is_authorized(request)
    if auth_response is not None:
        return auth_response

    if request.method != "POST":
        return Response(status_code=405)

    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return JSONResponse(_jsonrpc_error(-32700, "Parse error", None), status_code=400)

    if not isinstance(payload, dict):
        return JSONResponse(
            _jsonrpc_error(-32600, "Invalid Request", None, "Expected a JSON object."),
            status_code=400,
        )

    # JSON-RPC response objects are accepted as input and do not require response bodies.
    if "method" not in payload and ("result" in payload or "error" in payload):
        return Response(status_code=202)

    jsonrpc = payload.get("jsonrpc")
    method = payload.get("method")
    params = payload.get("params", {})
    request_id = payload.get("id")

    if jsonrpc != "2.0" or not isinstance(method, str):
        return JSONResponse(_jsonrpc_error(-32600, "Invalid Request", request_id), status_code=400)

    try:
        protocol_version = _negotiate_protocol_version(request.headers, method, params)
    except ValueError as exc:
        return _protocol_error_response(request_id, str(exc))

    # JSON-RPC notifications (no id) should not receive result/error payloads.
    if request_id is None:
        return Response(status_code=202, headers={"MCP-Protocol-Version": protocol_version})

    response_payload = _handle_mcp_method(method, params, request_id, protocol_version)
    if response_payload is None:
        return Response(status_code=202, headers={"MCP-Protocol-Version": protocol_version})

    return _build_mcp_json_response(response_payload, protocol_version)


app = Starlette(
    debug=False,
    routes=[
        Route("/health", health, methods=["GET"]),
        Route(
            "/.well-known/oauth-protected-resource",
            oauth_protected_resource_metadata,
            methods=["GET"],
        ),
        Route(
            "/.well-known/oauth-protected-resource/mcp",
            oauth_protected_resource_metadata,
            methods=["GET"],
        ),
        Route("/mcp", mcp_endpoint, methods=["POST"]),
    ],
)
