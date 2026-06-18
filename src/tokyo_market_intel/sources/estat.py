"""e-Stat API client.

This module is responsible for *access only*: reading credentials, building a
request, and returning the parsed JSON payload. It performs no analytical
transformation — that lives in `tokyo_market_intel.ingestion`.

Security rules enforced here:

- The application ID is read from the ``ESTAT_APP_ID`` environment variable.
- The application ID is never returned in a URL that is logged, and never placed
  in an exception message. Use :func:`redact` before logging anything that could
  contain it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

# e-Stat API 3.0 JSON endpoint for retrieving statistical data values.
GET_STATS_DATA_URL = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsData"

APP_ID_ENV = "ESTAT_APP_ID"
STATS_DATA_ID_ENV = "ESTAT_STATS_DATA_ID"


class EstatConfigError(RuntimeError):
    """Raised when required e-Stat configuration is missing."""


class EstatApiError(RuntimeError):
    """Raised when the e-Stat API call fails or returns an error status."""


def get_app_id() -> str:
    """Return the e-Stat application ID from the environment.

    Raises :class:`EstatConfigError` with an actionable, secret-free message if it
    is not set. The error never echoes any value.
    """

    app_id = os.environ.get(APP_ID_ENV, "").strip()
    if not app_id:
        raise EstatConfigError(
            f"{APP_ID_ENV} is not set. Register for a free e-Stat application ID at "
            "https://www.e-stat.go.jp/api/ and export it as an environment variable "
            f"(see .env.example). It must never be committed."
        )
    return app_id


def get_stats_data_id() -> str:
    """Return the configured e-Stat ``statsDataId`` from the environment."""

    stats_data_id = os.environ.get(STATS_DATA_ID_ENV, "").strip()
    if not stats_data_id:
        raise EstatConfigError(
            f"{STATS_DATA_ID_ENV} is not set. Pin the e-Stat table you want to ingest "
            "(see docs/data_sources.md for the recommended table) and export its "
            "statsDataId (see .env.example)."
        )
    return stats_data_id


def redact(text: str, app_id: str | None = None) -> str:
    """Return ``text`` with the application ID masked, for safe logging.

    If ``app_id`` is not provided, it is read from the environment when present.
    """

    secret = app_id if app_id is not None else os.environ.get(APP_ID_ENV, "")
    if secret:
        text = text.replace(secret, "***REDACTED***")
    return text


def build_params(
    stats_data_id: str,
    *,
    area_codes: list[str] | None = None,
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build the query parameters for ``getStatsData`` (without the appId)."""

    params: dict[str, str] = {"statsDataId": stats_data_id}
    if area_codes:
        # e-Stat accepts a comma-separated list of area codes via cdArea.
        params["cdArea"] = ",".join(area_codes)
    if extra:
        params.update(extra)
    return params


def fetch_stats_data(
    stats_data_id: str,
    *,
    app_id: str | None = None,
    area_codes: list[str] | None = None,
    extra: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> dict:
    """Call the e-Stat ``getStatsData`` API and return the parsed JSON payload.

    The application ID is added only at request time and is never logged. Network
    and decode failures are wrapped in :class:`EstatApiError` with secret-free
    messages.
    """

    resolved_app_id = app_id or get_app_id()
    params = build_params(stats_data_id, area_codes=area_codes, extra=extra)
    query = urllib.parse.urlencode({"appId": resolved_app_id, **params})
    url = f"{GET_STATS_DATA_URL}?{query}"

    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise EstatApiError(
            f"e-Stat API returned HTTP {exc.code} for statsDataId={stats_data_id}."
        ) from None
    except urllib.error.URLError as exc:
        # Reason can be an OS error; keep it but never include the URL (has appId).
        raise EstatApiError(
            f"Could not reach the e-Stat API ({exc.reason})."
        ) from None

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EstatApiError(f"e-Stat API returned non-JSON content: {exc}.") from None
