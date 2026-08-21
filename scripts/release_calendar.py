"""Resolve Target Version names from the release calendar.

Calendar / Product Pages use bare ``3.*`` cycle names (not obsolete
``rhoai-3.x``). Jira Target Version picklist values for those cycles look
like ``3.6 EA1 RHOAI RELEASE``.

QG1 discovery intentionally uses each event's ``codeFreeze`` (not
``planningFreeze``) as the cutoff: Features remain in the planning-ready
population until that event's code freeze date. Expansion emits only
events whose own freeze is still in the future (``>= as_of``), so an
already-frozen EA1 is not kept merely because EA2/GA are still open.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date

# Bare major.minor (optional patch): 3.5, 3.6, 3.6.1
_BARE_VERSION_RE = re.compile(r"^\d+\.\d+(?:\.\d+)?$")

# Current Jira TV naming: "{version} {event} {product} RELEASE"
_PRODUCT_FAMILIES = ("RHOAI", "RHAII", "RHELAI")
_DEFAULT_EVENTS = ("EA1", "EA2", "GA")

# Obsolete prefixes that must never enter discovery JQL.
_OBSOLETE_PREFIX_RE = re.compile(
    r"^(rhoai|rhaiis|rhaii|rhelai|rhai)-",
    re.IGNORECASE,
)


def load_calendar(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def default_calendar_path() -> str:
    return os.path.join(
        os.path.dirname(__file__), "..", "config", "release-calendar.json"
    )


def is_bare_version(name: str) -> bool:
    return bool(_BARE_VERSION_RE.match(str(name or "").strip()))


def is_obsolete_version_name(name: str) -> bool:
    """True for legacy ``rhoai-3.x`` / ``rhai-3.x`` style names."""
    return bool(_OBSOLETE_PREFIX_RE.match(str(name or "").strip()))


def _parse_code_freeze(raw) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def versions_with_future_code_freeze(
    calendar: dict,
    as_of: date | None = None,
) -> list[str]:
    """Return sorted bare version names with at least one future code freeze.

    Prefer ``expand_jira_names_for_future_events`` for discovery JQL — that
    filters per event so a frozen EA1 is not emitted when EA2 is still open.
    """
    as_of = as_of or date.today()
    selected = {
        version
        for version, _event, cf in _iter_bare_calendar_events(calendar)
        if cf >= as_of
    }
    return sorted(selected, key=lambda v: tuple(int(p) for p in v.split(".")))


def _iter_bare_calendar_events(calendar: dict):
    """Yield ``(version, event_label, code_freeze)`` for valid bare rows."""
    for event in calendar.get("events") or []:
        version = str(event.get("version") or "").strip()
        if not version or not _BARE_VERSION_RE.match(version):
            continue
        label = str(event.get("event") or "").strip()
        if not label:
            continue
        cf = _parse_code_freeze(event.get("codeFreeze"))
        if cf is None:
            continue
        yield version, label, cf


def calendar_events_for_version(
    calendar: dict,
    version: str,
    as_of: date | None = None,
) -> list[str]:
    """Return event labels for ``version``.

    When ``as_of`` is set, only labels whose own ``codeFreeze >= as_of``
    are returned. When unset, all calendar labels for the version are
    returned (used for explicit ``target_versions`` overrides).
    """
    events = []
    seen = set()
    for ver, label, cf in _iter_bare_calendar_events(calendar):
        if ver != version:
            continue
        if as_of is not None and cf < as_of:
            continue
        if label in seen:
            continue
        seen.add(label)
        events.append(label)
    if events:
        return events
    if as_of is None:
        return list(_DEFAULT_EVENTS)
    return []


def expand_jira_target_version_names(
    bare_versions: list[str],
    calendar: dict | None = None,
    as_of: date | None = None,
) -> list[str]:
    """Expand bare cycles to Jira Target Version picklist names.

    Example: ``3.6`` → ``3.6 EA1 RHOAI RELEASE``, ``3.6 EA1 RHAII RELEASE``, …
    Obsolete ``rhoai-3.x`` names are never produced.

    When ``as_of`` is provided, only events with ``codeFreeze >= as_of``
    are expanded.
    """
    calendar = calendar or {}
    names: list[str] = []
    seen: set[str] = set()
    for version in bare_versions:
        version = str(version).strip()
        if not is_bare_version(version):
            continue
        for event in calendar_events_for_version(calendar, version, as_of=as_of):
            for product in _PRODUCT_FAMILIES:
                name = f"{version} {event} {product} RELEASE"
                if name not in seen:
                    seen.add(name)
                    names.append(name)
    return names


def expand_jira_names_for_future_events(
    calendar: dict,
    as_of: date | None = None,
) -> list[str]:
    """Expand only calendar events whose own code freeze is still future."""
    as_of = as_of or date.today()
    names: list[str] = []
    seen: set[str] = set()
    for version, event, cf in _iter_bare_calendar_events(calendar):
        if cf < as_of:
            continue
        for product in _PRODUCT_FAMILIES:
            name = f"{version} {event} {product} RELEASE"
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _load_configured_calendar(jql_cfg: dict) -> dict:
    path = jql_cfg.get("calendar_path") or default_calendar_path()
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(__file__), "..", path)
    return load_calendar(path)


def resolve_discovery_target_versions(
    config: dict,
    as_of: date | None = None,
) -> list[str]:
    """Jira Target Version names for discovery JQL from config and/or calendar.

    Returns expanded picklist-style names (``3.6 EA1 RHOAI RELEASE``, …),
    never obsolete ``rhoai-3.x`` names. Bare ``3.*`` entries in
    ``jql.target_versions`` are expanded the same way.

    Missing calendar files raise ``OSError`` / ``FileNotFoundError``.
    """
    jql_cfg = config.get("jql") or {}
    explicit = jql_cfg.get("target_versions")
    if explicit:
        bare: list[str] = []
        already: list[str] = []
        for raw in explicit:
            name = str(raw).strip()
            if not name or is_obsolete_version_name(name):
                continue
            if is_bare_version(name):
                bare.append(name)
            elif name[0].isdigit():
                # Already a 3.*-style picklist value.
                already.append(name)
        if bare:
            calendar = _load_configured_calendar(jql_cfg)
            already.extend(expand_jira_target_version_names(bare, calendar))
        # Preserve order, drop dupes.
        out: list[str] = []
        seen: set[str] = set()
        for name in already:
            if name not in seen:
                seen.add(name)
                out.append(name)
        return out

    if not jql_cfg.get("target_versions_from_calendar", True):
        return []

    calendar = _load_configured_calendar(jql_cfg)
    return expand_jira_names_for_future_events(calendar, as_of=as_of)
