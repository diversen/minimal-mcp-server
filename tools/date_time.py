from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tools.registry import make_tool_text_response, register_tool

CITY_TO_TZ = {
    "new york": "America/New_York",
    "nyc": "America/New_York",
    "copenhagen": "Europe/Copenhagen",
    "cp hagen": "Europe/Copenhagen",
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


@register_tool(
    name="get_locale_date_time",
    description=(
        "Get the local date/time for a locale. "
        "Use an IANA timezone or known city alias."
    ),
    input_schema={
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
)
def get_locale_date_time(arguments: dict[str, Any]) -> dict[str, Any]:
    locale = arguments.get("locale")
    tz_name = _resolve_timezone(locale)
    now = datetime.now(ZoneInfo(tz_name))

    text = (
        f"Local date/time in {tz_name} is "
        f"{now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}."
    )

    return make_tool_text_response(
        text=text,
        structured_content={
            "locale": locale,
            "timezone": tz_name,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "iso": now.isoformat(),
            "offset": now.strftime("%z"),
        },
    )
