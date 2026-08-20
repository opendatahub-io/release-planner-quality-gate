"""Tests for Org Pulse–aligned description signal parsing.

Ported from Org Pulse
``modules/releases/server/planning/__tests__/description-scanner.test.js``.
"""
from scripts.description_signals import parse_description_signals


class TestEmptyInputs:
    def test_null_input(self):
        result = parse_description_signals(None)
        assert result["hasContent"] is False
        assert result["signalCount"] == 0

    def test_empty_string(self):
        result = parse_description_signals("")
        assert result["hasContent"] is False
        assert result["signalCount"] == 0

    def test_whitespace_only(self):
        result = parse_description_signals("   \n  ")
        assert result["hasContent"] is False
        assert result["signalCount"] == 0

    def test_non_adf_object(self):
        result = parse_description_signals({"type": "other"})
        assert result["hasContent"] is False
        assert result["signalCount"] == 0


class TestAcceptanceCriteria:
    def test_given_when_then(self):
        result = parse_description_signals(
            "Given a user is logged in when they click logout "
            "then they see the login page"
        )
        assert result["hasContent"] is True
        assert result["hasAcceptanceCriteria"] is True
        assert result["signalCount"] >= 1

    def test_ac_prefix(self):
        result = parse_description_signals(
            "AC: The feature must support dark mode"
        )
        assert result["hasAcceptanceCriteria"] is True

    def test_acceptance_criteria_keyword(self):
        result = parse_description_signals(
            "The acceptance criteria for this feature are as follows"
        )
        assert result["hasAcceptanceCriteria"] is True

    def test_success_criteria_section(self):
        result = parse_description_signals(
            "## Success Criteria\n"
            "- Users can log in with SSO\n"
            "- Session persists across refresh"
        )
        assert result["hasAcceptanceCriteria"] is True
        assert any(
            m["title"] == "Success Criteria" for m in result["matchedSections"]
        )

    def test_empty_acceptance_heading_does_not_pass(self):
        result = parse_description_signals(
            "## Acceptance Criteria\n\n"
            "## Other\nSome other content here that is long enough"
        )
        assert result["hasAcceptanceCriteria"] is False


class TestUseCasesAndScope:
    def test_use_case(self):
        result = parse_description_signals(
            "Use case: A developer wants to deploy their app"
        )
        assert result["hasUseCases"] is True

    def test_user_story_pattern(self):
        result = parse_description_signals(
            "As a platform admin so that I can manage users"
        )
        assert result["hasUseCases"] is True

    def test_scope_in_out(self):
        result = parse_description_signals(
            "In scope: API endpoints. Out of scope: UI changes"
        )
        assert result["hasScopeDefinition"] is True

    def test_scope_with_colon(self):
        result = parse_description_signals(
            "Scope: This feature covers the backend only"
        )
        assert result["hasScopeDefinition"] is True


class TestRequirements:
    def test_hlr(self):
        result = parse_description_signals(
            "HLR-001: The system shall support OAuth2"
        )
        assert result["hasRequirements"] is True

    def test_nfr(self):
        result = parse_description_signals(
            "NFR: Response time must be under 200ms"
        )
        assert result["hasRequirements"] is True

    def test_non_functional(self):
        result = parse_description_signals(
            "Non-functional requirement: 99.9% uptime"
        )
        assert result["hasRequirements"] is True


class TestRisks:
    def test_risk_inline(self):
        result = parse_description_signals(
            "Risk: dependency on external API availability"
        )
        assert result["hasRisks"] is True

    def test_assumption_inline(self):
        result = parse_description_signals(
            "Assumption: Users have modern browsers"
        )
        assert result["hasRisks"] is True

    def test_constraint_inline(self):
        result = parse_description_signals(
            "Constraint: Must work on RHEL 9"
        )
        assert result["hasRisks"] is True

    def test_risks_and_assumptions_heading(self):
        result = parse_description_signals(
            "## Risks and Assumptions\n"
            "- API may change\n"
            "- Team capacity limited"
        )
        assert result["hasRisks"] is True

    def test_dependencies_heading(self):
        result = parse_description_signals(
            "## Dependencies\n"
            "- Requires auth service v2\n"
            "- Needs DB migration"
        )
        assert result["hasRisks"] is True

    def test_blockers_heading(self):
        result = parse_description_signals(
            "## Blockers\n"
            "- Waiting on legal review for the release"
        )
        assert result["hasRisks"] is True

    def test_constraints_heading(self):
        result = parse_description_signals(
            "## Constraints\n"
            "- Must run on RHEL 9\n"
            "- Budget limit $50k"
        )
        assert result["hasRisks"] is True


class TestArchitectureAndUx:
    def test_technical_approach_heading(self):
        result = parse_description_signals(
            "## Technical Approach\n"
            "We will use a microservices architecture with "
            "event-driven communication"
        )
        assert result["hasArchitectureSignal"] is True

    def test_architecture_heading(self):
        result = parse_description_signals(
            "## Architecture\n"
            "Service mesh topology and API boundaries for the control plane"
        )
        assert result["hasArchitectureSignal"] is True

    def test_adr_and_design_doc(self):
        assert parse_description_signals(
            "See ADR-12 for the chosen approach"
        )["hasArchitectureSignal"] is True
        assert parse_description_signals(
            "Design doc: https://example.com/doc"
        )["hasArchitectureSignal"] is True

    def test_bare_narrative_architecture_not_signal(self):
        result = parse_description_signals(
            "The agent architecture matters for latency in production workloads"
        )
        assert result["hasArchitectureSignal"] is False

    def test_architecture_not_required(self):
        result = parse_description_signals(
            "Architecture is not required for this documentation-only change."
        )
        assert result["hasArchitectureNotRequired"] is True

    def test_na_no_ux(self):
        result = parse_description_signals(
            "N/A – no UX for this API-only feature."
        )
        assert result["hasNaNoUx"] is True


class TestCrossTeamAndAggregates:
    def test_cross_functional_dependency_language(self):
        result = parse_description_signals(
            "This feature depends on Serving API v2 and is "
            "cross-team with Model Mesh"
        )
        assert result["hasCrossFunctionalDependency"] is True

    def test_counts_multiple_signals(self):
        text = (
            "AC: Feature supports dark mode\n"
            "Use case: Developer deploys app\n"
            "Scope: Backend only\n"
            "Risk: API dependency"
        )
        result = parse_description_signals(text)
        assert result["hasContent"] is True
        assert result["hasAcceptanceCriteria"] is True
        assert result["hasUseCases"] is True
        assert result["hasScopeDefinition"] is True
        assert result["hasRisks"] is True
        assert result["signalCount"] == 4

    def test_plain_description_has_content_no_signals(self):
        result = parse_description_signals(
            "This feature adds a new button to the toolbar"
        )
        assert result["hasContent"] is True
        assert result["signalCount"] == 0
        assert result["hasAcceptanceCriteria"] is False
        assert result["hasUseCases"] is False
        assert result["hasScopeDefinition"] is False
        assert result["hasRequirements"] is False
        assert result["hasRisks"] is False


class TestAdf:
    def test_adf_heading_sections_with_body(self):
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Acceptance Criteria"}],
                },
                {
                    "type": "paragraph",
                    "content": [{
                        "type": "text",
                        "text": "The feature must work for admins and operators.",
                    }],
                },
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Use Cases"}],
                },
                {
                    "type": "paragraph",
                    "content": [{
                        "type": "text",
                        "text": "Admin manages users in the console daily.",
                    }],
                },
            ],
        }
        result = parse_description_signals(adf)
        assert result["hasContent"] is True
        assert result["hasAcceptanceCriteria"] is True
        assert result["hasUseCases"] is True
        assert result["signalCount"] >= 2

    def test_adf_empty_content(self):
        result = parse_description_signals({"type": "doc", "content": []})
        assert result["hasContent"] is False
        assert result["signalCount"] == 0

    def test_adf_empty_acceptance_heading_does_not_pass(self):
        adf = {
            "type": "doc",
            "content": [
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Acceptance Criteria"}],
                },
                {
                    "type": "heading",
                    "attrs": {"level": 2},
                    "content": [{"type": "text", "text": "Other"}],
                },
                {
                    "type": "paragraph",
                    "content": [{
                        "type": "text",
                        "text": "Some other substantive paragraph content here.",
                    }],
                },
            ],
        }
        result = parse_description_signals(adf)
        assert result["hasAcceptanceCriteria"] is False
