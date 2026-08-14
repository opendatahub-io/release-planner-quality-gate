"""Resolve Target Version names from the release calendar.

Calendar / Product Pages use bare ``3.*`` cycle names (not obsolete
``rhoai-3.x``). Jira Target Version picklist values for those cycles look
like ``3.6 EA1 RHOAI RELEASE``.

A cycle is in discovery scope when any of its calendar events has
``codeFreeze >= as_of`` (inclusive). Discovery JQL then uses the expanded
Jira picklist names for that cycle (RHOAI / RHAII / RHELAI × EA1/EA2/GA).
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


def versions_with_future_code_freeze(
    calendar: dict,
    as_of: date | None = None,
) -> list[str]:
    """Return sorted bare version names with at least one future code freeze."""
    as_of = as_of or date.today()
    by_version: dict[str, list[date]] = {}
    for event in calendar.get("events") or []:
        version = str(event.get("version") or "").strip()
        if not version or not _BARE_VERSION_RE.match(version):
            continue
        raw = event.get("codeFreeze")
        if not raw:
            continue
        try:
            cf = date.fromisoformat(str(raw)[:10])
        except ValueError:
            continue
        by_version.setdefault(version, []).append(cf)

    selected = [
        version
        for version, freezes in by_version.items()
        if any(cf >= as_of for cf in freezes)
    ]
    return sorted(selected, key=lambda v: tuple(int(p) for p in v.split(".")))


def calendar_events_for_version(calendar: dict, version: str) -> list[str]:
    """Return event labels (EA1/EA2/GA) listed for ``version`` in the calendar."""
    events = []
    seen = set()
    for event in calendar.get("events") or []:
        if str(event.get("version") or "").strip() != version:
            continue
        label = str(event.get("event") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        events.append(label)
    return events or list(_DEFAULT_EVENTS)


def expand_jira_target_version_names(
    bare_versions: list[str],
    calendar: dict | None = None,
) -> list[str]:
    """Expand bare cycles to Jira Target Version picklist names.

    Example: ``3.6`` → ``3.6 EA1 RHOAI RELEASE``, ``3.6 EA1 RHAII RELEASE``, …
    Obsolete ``rhoai-3.x`` names are never produced.
    """
    calendar = calendar or {}
    names: list[str] = []
    seen: set[str] = set()
    for version in bare_versions:
        version = str(version).strip()
        if not is_bare_version(version):
            continue
        for event in calendar_events_for_version(calendar, version):
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
            try:
                calendar = _load_configured_calendar(jql_cfg)
            except OSError:
                calendar = {}
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
    bare = versions_with_future_code_freeze(calendar, as_of=as_of)
    return expand_jira_target_version_names(bare, calendar)
