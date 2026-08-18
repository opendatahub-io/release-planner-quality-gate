"""Deterministic FPDoR description signals (Org Pulse port).

Faithful Python port of Org Pulse
``modules/releases/server/planning/health/description-scanner.js``
(``parseDescriptionSignals``). Scans the Jira **description** only — no
attachments. Used by ``description_criterion`` hard checks so QG1 matches
the Org Pulse dashboard without invoking Claude.
"""
from __future__ import annotations

import re
from typing import Any

MIN_BODY_CHARS = 20

AC_INLINE = re.compile(
    r"\b(given\s[\s\S]*?\b(when|then)\b|AC\s*:)",
    re.IGNORECASE,
)
USE_CASE_INLINE = re.compile(
    r"\b(use\s+case|user\s+stor|as\s+a\s+.*?\bso\s+that\b)",
    re.IGNORECASE,
)
ARCHITECTURE_INLINE = re.compile(
    r"\b(arch(?:itecture)?[\s-]?review|technical\s+(design|approach)|"
    r"system\s+design|design\s+doc|\bADR\b|\bRFC\b)\b",
    re.IGNORECASE,
)
CROSS_FUNCTIONAL_DEP_PATTERN = re.compile(
    r"\b(depends?\s+on|cross[\s-]?team|cross[\s-]?functional|"
    r"multi[\s-]?team|multi[\s-]?component)\b",
    re.IGNORECASE,
)
NA_NO_UX_PATTERN = re.compile(
    r"\bN\s*/\s*A\s*[–—-]\s*no\s+UX\b|"
    r"\bN\s*/\s*A\s*[–—-]\s*no\s+UI\b|"
    r"\bno\s+UX(?:D)?\s+required\b|"
    r"\bno\s+UI\s+required\b",
    re.IGNORECASE,
)
ARCH_NOT_REQUIRED_PATTERN = re.compile(
    r"\barchitecture\s+(is\s+)?not\s+required\b|"
    r"\bnot\s+required\s*[–—-]\s*architecture\b|"
    r"\bno\s+architecture\s+(review|alignment)\s+required\b",
    re.IGNORECASE,
)

SECTION_ALIASES: dict[str, list[re.Pattern[str]]] = {
    "acceptanceCriteria": [
        re.compile(r"^acceptance\s+criteria?$", re.IGNORECASE),
        re.compile(r"^success\s+criteria?$", re.IGNORECASE),
        re.compile(r"^definition\s+of\s+done$", re.IGNORECASE),
        re.compile(r"^acceptance$", re.IGNORECASE),
        re.compile(r"^ac$", re.IGNORECASE),
    ],
    "requirements": [
        re.compile(r"^requirements?$", re.IGNORECASE),
        re.compile(r"^problem\s+statement$", re.IGNORECASE),
        re.compile(r"^goals?$", re.IGNORECASE),
        re.compile(r"^high[\s-]?level\s+requirements?$", re.IGNORECASE),
        re.compile(r"^hlr$", re.IGNORECASE),
        re.compile(r"^nfr$", re.IGNORECASE),
        re.compile(r"^non[\s-]?functional(\s+requirements?)?$", re.IGNORECASE),
    ],
    "useCases": [
        re.compile(r"^use\s+cases?$", re.IGNORECASE),
        re.compile(r"^user\s+stor(?:y|ies)$", re.IGNORECASE),
    ],
    "scope": [
        re.compile(r"^scope$", re.IGNORECASE),
        re.compile(r"^in\s+scope$", re.IGNORECASE),
        re.compile(r"^out\s+of\s+scope$", re.IGNORECASE),
        re.compile(r"^non[\s-]?goals?$", re.IGNORECASE),
    ],
    "risks": [
        re.compile(r"^risks?$", re.IGNORECASE),
        re.compile(r"^risks?\s*(and|&)\s*assumptions?$", re.IGNORECASE),
        re.compile(r"^assumptions?$", re.IGNORECASE),
        re.compile(r"^constraints?$", re.IGNORECASE),
        re.compile(r"^dependencies$", re.IGNORECASE),
        re.compile(r"^blockers?$", re.IGNORECASE),
    ],
    "architecture": [
        re.compile(r"^architecture$", re.IGNORECASE),
        re.compile(r"^architecture\s+review$", re.IGNORECASE),
        re.compile(r"^technical\s+(design|approach)$", re.IGNORECASE),
        re.compile(r"^system\s+design$", re.IGNORECASE),
        re.compile(r"^design\s+doc$", re.IGNORECASE),
        re.compile(r"^adr$", re.IGNORECASE),
        re.compile(r"^rfc$", re.IGNORECASE),
    ],
}


def empty_signals() -> dict[str, Any]:
    return {
        "hasContent": False,
        "hasAcceptanceCriteria": False,
        "hasUseCases": False,
        "hasScopeDefinition": False,
        "hasRequirements": False,
        "hasRisks": False,
        "hasArchitectureSignal": False,
        "hasArchitectureNotRequired": False,
        "hasCrossFunctionalDependency": False,
        "hasNaNoUx": False,
        "matchedSections": [],
        "signalCount": 0,
    }


def adf_to_text(node: Any) -> str:
    """Plain text from an ADF node (Org Pulse ``adfToText``)."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text") or ""
        content = node.get("content")
        if isinstance(content, list):
            return "".join(adf_to_text(item) for item in content)
    if isinstance(node, list):
        return "".join(adf_to_text(item) for item in node)
    return ""


def normalize_heading(title: Any) -> str:
    text = str(title or "")
    text = re.sub(r"^#+\s*", "", text)
    text = re.sub(r"^\*\*|\*\*$", "", text)
    text = re.sub(r":$", "", text)
    return text.strip()


def classify_heading(title: Any) -> str | None:
    normalized = normalize_heading(title)
    if not normalized:
        return None
    for key, patterns in SECTION_ALIASES.items():
        for pattern in patterns:
            if pattern.match(normalized):
                return key
    return None


def body_has_substance(body: Any) -> bool:
    trimmed = str(body or "").strip()
    if not trimmed:
        return False
    if len(trimmed) >= MIN_BODY_CHARS:
        return True
    if re.match(r"^[-*•]", trimmed):
        return True
    return len([line for line in trimmed.split("\n") if line]) >= 2


def extract_adf_sections(doc: dict) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    nodes = (doc or {}).get("content") or []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current:
            sections.append(current)
            current = None

    for node in nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") == "heading":
            flush()
            attrs = node.get("attrs") or {}
            current = {
                "title": adf_to_text(node),
                "level": attrs.get("level") or 1,
                "body": "",
            }
            continue
        if not current:
            continue
        piece = adf_to_text(node)
        if piece:
            current["body"] += ("\n" if current["body"] else "") + piece
    flush()
    return sections


def extract_markdown_sections(text: str) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    lines = str(text or "").split("\n")
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current:
            sections.append(current)
            current = None

    for line in lines:
        md = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        bold = re.match(r"^\*\*(.+?)\*\*\s*$", line)
        stripped_for_alias = re.sub(r":$", "", line).strip()
        plain_alias = None
        if (
            classify_heading(stripped_for_alias)
            and not line.startswith("#")
            and len(line.strip()) < 80
            and not re.search(r"[.!?]$", line.strip())
        ):
            plain_alias = line.strip()

        title = None
        is_structural_heading = False
        level = 2
        if md:
            title = md.group(2)
            level = len(md.group(1))
            is_structural_heading = True
        elif bold:
            title = bold.group(1)
            is_structural_heading = bool(classify_heading(title))
        elif plain_alias:
            title = plain_alias
            is_structural_heading = True

        if title and (is_structural_heading or classify_heading(title)):
            flush()
            current = {"title": title, "level": level, "body": ""}
            continue
        if current is not None:
            current["body"] += ("\n" if current["body"] else "") + line
    flush()
    return sections


def apply_section_signals(signals: dict[str, Any], sections: list[dict]) -> None:
    for section in sections:
        kind = classify_heading(section.get("title"))
        if not kind or not body_has_substance(section.get("body")):
            continue
        matched_title = normalize_heading(section.get("title"))
        signals["matchedSections"].append({"kind": kind, "title": matched_title})
        if kind == "acceptanceCriteria":
            signals["hasAcceptanceCriteria"] = True
        elif kind == "requirements":
            signals["hasRequirements"] = True
        elif kind == "useCases":
            signals["hasUseCases"] = True
        elif kind == "scope":
            signals["hasScopeDefinition"] = True
        elif kind == "risks":
            signals["hasRisks"] = True
        elif kind == "architecture":
            signals["hasArchitectureSignal"] = True


def apply_inline_fallbacks(signals: dict[str, Any], text: str) -> None:
    body_text = re.sub(r"^#{1,6}\s+.*$", "", str(text or ""), flags=re.MULTILINE)
    body_text = re.sub(r"^\*\*[^*].*[^*]\*\*\s*$", "", body_text, flags=re.MULTILINE)

    if not signals["hasAcceptanceCriteria"] and AC_INLINE.search(body_text):
        signals["hasAcceptanceCriteria"] = True
        signals["matchedSections"].append(
            {"kind": "acceptanceCriteria", "title": "inline AC"}
        )
    if not signals["hasAcceptanceCriteria"] and re.search(
        r"\b(acceptance\s+criter|success\s+criter)", body_text, re.IGNORECASE
    ):
        signals["hasAcceptanceCriteria"] = True
        signals["matchedSections"].append(
            {"kind": "acceptanceCriteria", "title": "inline acceptance criteria"}
        )
    if not signals["hasUseCases"] and USE_CASE_INLINE.search(body_text):
        signals["hasUseCases"] = True
        signals["matchedSections"].append(
            {"kind": "useCases", "title": "inline use case"}
        )
    if not signals["hasArchitectureSignal"] and ARCHITECTURE_INLINE.search(body_text):
        signals["hasArchitectureSignal"] = True
        signals["matchedSections"].append(
            {"kind": "architecture", "title": "inline architecture"}
        )
    if not signals["hasScopeDefinition"] and re.search(
        r"\b(in\s+scope|out\s+of\s+scope|\bscope\b\s*[:=-])",
        body_text,
        re.IGNORECASE,
    ):
        signals["hasScopeDefinition"] = True
        signals["matchedSections"].append({"kind": "scope", "title": "inline scope"})
    if not signals["hasRequirements"] and re.search(
        r"\b(requirement|HLR|NFR|non[\s-]?functional|problem\s+statement)",
        body_text,
        re.IGNORECASE,
    ):
        signals["hasRequirements"] = True
        signals["matchedSections"].append(
            {"kind": "requirements", "title": "inline requirements"}
        )
    if not signals["hasRisks"] and re.search(
        r"\b(risks?\s*(and|&)\s*assumptions?|risks?\s*[:=-]|assumptions?\s*[:=-]|"
        r"constraints?\s*[:=-]|blockers?\s*[:=-])",
        body_text,
        re.IGNORECASE,
    ):
        signals["hasRisks"] = True
        signals["matchedSections"].append({"kind": "risks", "title": "inline risks"})
    if not signals["hasRisks"] and re.search(
        r"(^|\n)\s*(Risks?(?:\s*(?:and|&)\s*Assumptions?)?|Assumptions?|"
        r"Constraints?|Dependencies|Blockers?)\s*\n\s*\S",
        text,
        re.IGNORECASE,
    ):
        signals["hasRisks"] = True
        signals["matchedSections"].append({"kind": "risks", "title": "risks heading"})


def parse_description_signals(description: Any) -> dict[str, Any]:
    """Parse Org Pulse–aligned description signals from string or ADF doc."""
    if not description:
        return empty_signals()

    if isinstance(description, str):
        text = description
        sections = extract_markdown_sections(text)
    elif isinstance(description, dict) and description.get("type") == "doc":
        text = adf_to_text(description)
        sections = extract_adf_sections(description)
        if not sections:
            sections = extract_markdown_sections(text)
    else:
        return empty_signals()

    if not text.strip():
        return empty_signals()

    signals = empty_signals()
    signals["hasContent"] = True
    apply_section_signals(signals, sections)

    scrubbed_text = text
    for sec in sections:
        if classify_heading(sec.get("title")) and not body_has_substance(sec.get("body")):
            title = normalize_heading(sec.get("title"))
            if title:
                scrubbed_text = scrubbed_text.replace(title, " ")
    apply_inline_fallbacks(signals, scrubbed_text)

    signals["hasCrossFunctionalDependency"] = bool(
        CROSS_FUNCTIONAL_DEP_PATTERN.search(text)
    )
    signals["hasNaNoUx"] = bool(NA_NO_UX_PATTERN.search(text))
    signals["hasArchitectureNotRequired"] = bool(
        ARCH_NOT_REQUIRED_PATTERN.search(text)
    )

    signal_count = 0
    if signals["hasAcceptanceCriteria"]:
        signal_count += 1
    if signals["hasUseCases"]:
        signal_count += 1
    if signals["hasScopeDefinition"]:
        signal_count += 1
    if signals["hasRequirements"]:
        signal_count += 1
    if signals["hasRisks"]:
        signal_count += 1
    signals["signalCount"] = signal_count
    return signals


def matched_section_detail(signals: dict[str, Any], kinds: list[str]) -> str | None:
    for match in signals.get("matchedSections") or []:
        if match.get("kind") in kinds:
            return match.get("title") or match.get("kind")
    return None
