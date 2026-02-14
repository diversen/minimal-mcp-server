import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.routing import Route

MCP_PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "simple-mcp-starlette-server"
SERVER_VERSION = "0.1.0"

TOOL_NAME = "get_locale_date_time"

CITY_TO_TZ = {
    "new york": "America/New_York",
    "nyc": "America/New_York",
    "copenhagen": "Europe/Copenhagen",
    "cp hagen": "Europe/Copenhagen",
}


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


def _resolve_timezone(locale: str) -> str:
    if not locale or not locale.strip():
        raise ValueError("`locale` is required.")

    candidate = locale.strip()
    lowered = candidate.lower()

    if lowered in CITY_TO_TZ:
        return CITY_TO_TZ[lowered]

    try:
        ZoneInfo(candidate)
        return candidate
    except ZoneInfoNotFoundError as exc:
        raise ValueError(
            "Unsupported locale/timezone. Try an IANA timezone like "
            "'America/New_York' or a known alias like 'Copenhagen'."
        ) from exc


def _handle_tool_call(params: dict) -> dict:
    name = params.get("name")
    arguments = params.get("arguments") or {}

    if name != TOOL_NAME:
        raise KeyError(f"Unknown tool: {name}")

    locale = arguments.get("locale")
    tz_name = _resolve_timezone(locale)
    now = datetime.now(ZoneInfo(tz_name))

    text = (
        f"Local date/time in {tz_name} is "
        f"{now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}."
    )

    return {
        "content": [
            {
                "type": "text",
                "text": text,
            }
        ],
        "structuredContent": {
            "locale": locale,
            "timezone": tz_name,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "iso": now.isoformat(),
            "offset": now.strftime("%z"),
        },
        "isError": False,
    }


def _tools_list_result() -> dict:
    return {
        "tools": [
            {
                "name": TOOL_NAME,
                "description": (
                    "Get the local date/time for a locale. "
                    "Use an IANA timezone or known city alias."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "locale": {
                            "type": "string",
                            "description": (
                                "Timezone/locale like 'America/New_York', "
                                "'Europe/Copenhagen', 'New York', or 'Copenhagen'."
                            ),
                        }
                    },
                    "required": ["locale"],
                    "additionalProperties": False,
                },
            }
        ]
    }


def _handle_mcp_method(method: str, params: dict, request_id):
    if method == "initialize":
        return _jsonrpc_result(
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
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
            result = _handle_tool_call(params or {})
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
        return _auth_error(401, "Missing Authorization header.")

    parts = header.split(" ", maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        return _auth_error(401, "Expected Authorization: Bearer <token>.")

    incoming_token = parts[1].strip()
    if incoming_token != expected_token:
        return _auth_error(403, "Forbidden: invalid token.")

    return None


async def health(_: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


async def mcp_endpoint(request: Request) -> Response:
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

    jsonrpc = payload.get("jsonrpc")
    method = payload.get("method")
    params = payload.get("params", {})
    request_id = payload.get("id")

    if jsonrpc != "2.0" or not isinstance(method, str):
        return JSONResponse(_jsonrpc_error(-32600, "Invalid Request", request_id), status_code=400)

    response_payload = _handle_mcp_method(method, params, request_id)
    if response_payload is None:
        return Response(status_code=202)

    return JSONResponse(response_payload)


app = Starlette(
    debug=False,
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/mcp", mcp_endpoint, methods=["POST"]),
    ],
)

