from dataclasses import dataclass
from typing import Any, Callable

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler

    def as_mcp_tool(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


_TOOL_REGISTRY: dict[str, ToolDefinition] = {}


def register_tool(name: str, description: str, input_schema: dict[str, Any]):
    def decorator(func: ToolHandler) -> ToolHandler:
        if name in _TOOL_REGISTRY:
            raise RuntimeError(f"Tool already registered: {name}")

        _TOOL_REGISTRY[name] = ToolDefinition(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=func,
        )
        return func

    return decorator


def list_tools() -> list[dict[str, Any]]:
    return [_TOOL_REGISTRY[name].as_mcp_tool() for name in sorted(_TOOL_REGISTRY.keys())]


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    if name not in _TOOL_REGISTRY:
        raise KeyError(f"Unknown tool: {name}")

    return _TOOL_REGISTRY[name].handler(arguments or {})


def make_tool_text_response(text: str, structured_content: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "structuredContent": structured_content,
        "isError": False,
    }
