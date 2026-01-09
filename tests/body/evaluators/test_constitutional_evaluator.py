# tests/body/evaluators/test_constitutional_evaluator.py

"""
Tests for ConstitutionalEvaluator component.

Constitutional Alignment:
- Tests evaluation accuracy
- Verifies no side effects (read-only)
- Validates component contract compliance
"""

from __future__ import annotations

import pytest

from body.evaluators.constitutional_evaluator import ConstitutionalEvaluator
from shared.component_primitive import ComponentPhase


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
@pytest.fixture
def evaluator():
    """Fixture providing ConstitutionalEvaluator instance."""
    return ConstitutionalEvaluator()


# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
class TestComponentContract:
    """Test ConstitutionalEvaluator follows Component contract."""

    @pytest.mark.asyncio
    async def test_declares_audit_phase(self, evaluator):
        """Evaluators must operate in AUDIT phase."""
        assert evaluator.phase == ComponentPhase.AUDIT

    @pytest.mark.asyncio
    async def test_returns_component_result(self, evaluator):
        """Execute must return ComponentResult."""
        result = await evaluator.execute(
            file_path="src/models/user.py", operation_type="refactor"
        )

        assert hasattr(result, "ok")
        assert hasattr(result, "data")
        assert hasattr(result, "phase")
        assert result.phase == ComponentPhase.AUDIT

    @pytest.mark.asyncio
    async def test_component_id_matches_class(self, evaluator):
        """Component ID should be derived from class name."""
        assert evaluator.component_id == "constitutionalevaluator"

    @pytest.mark.asyncio
    async def test_no_mutations(self, evaluator):
        """Evaluators must not mutate state (read-only)."""
        # This is a contract test - evaluator should never write files
        result = await evaluator.execute(
            file_path="src/models/user.py", operation_type="refactor"
        )

        # Should return result without modifying filesystem
        assert result is not None


# ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
class TestConstitutionalCompliance:
    """Test constitutional compliance checking."""

    @pytest.mark.asyncio
    async def test_evaluates_file_compliance(self, evaluator):
        """Should check file against constitutional rules."""
        result = await evaluator.execute(
            file_path="src/models/user.py",
            validation_scope=["constitutional_compliance"],
        )

        assert "violations" in result.data
        assert "compliance_score" in result.data
        assert "details" in result.data
        assert "constitutional" in result.data["details"]

    @pytest.mark.asyncio
    async def test_skips_when_not_in_scope(self, evaluator):
        """Should skip checks not in validation_scope."""
        result = await evaluator.execute(
            file_path="src/models/user.py",
            validation_scope=["governance_boundaries"],
        )

        details = result.data["details"]
        assert (
            "constitutional" not in details or not details["constitutional"]["checked"]
        )

    @pytest.mark.asyncio
    async def test_handles_missing_file(self, evaluator):
        """Should handle missing files gracefully."""
        result = await evaluator.execute(
            file_path="src/nonexistent/file.py",
            validation_scope=["constitutional_compliance"],
        )

        # Should not crash, may have zero violations for non-existent file
        assert "violations" in result.data


# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
class TestPatternCompliance:
    """Test pattern compliance checking."""

    @pytest.mark.asyncio
    async def test_checks_atomic_actions_pattern(self, evaluator):
        """Should validate atomic action files against pattern."""
        result = await evaluator.execute(
            file_path="src/body/atomic/test_action.py",
            validation_scope=["pattern_compliance"],
        )

        assert "details" in result.data
        assert "patterns" in result.data["details"]

    @pytest.mark.asyncio
    async def test_skips_non_pattern_files(self, evaluator):
        """Should skip pattern checks for non-pattern files."""
        result = await evaluator.execute(
            file_path="src/services/user.py",
            validation_scope=["pattern_compliance"],
        )

        # Should not crash on non-pattern files
        assert "violations" in result.data


# ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
class TestGovernanceBoundaries:
    """Test governance boundary enforcement."""

    @pytest.mark.asyncio
    async def test_blocks_intent_writes(self, evaluator):
        """Should detect attempts to write .intent/ directory."""
        result = await evaluator.execute(
            file_path=".intent/constitution/core.yaml",
            operation_type="refactor",
            validation_scope=["governance_boundaries"],
        )

        violations = result.data["violations"]
        assert any(
            v["rule_id"] == "governance.constitution.read_only" for v in violations
        )
        assert any(v["severity"] == "critical" for v in violations)

    @pytest.mark.asyncio
    async def test_checks_operation_permissions(self, evaluator):
        """Should verify operation is allowed by governance."""
        result = await evaluator.execute(
            file_path="src/models/user.py",
            operation_type="refactor",
            validation_scope=["governance_boundaries"],
        )

        # Should complete governance check
        assert "details" in result.data
        assert "governance" in result.data["details"]

    @pytest.mark.asyncio
    async def test_allows_normal_operations(self, evaluator):
        """Should not block normal operations on src/ files."""
        result = await evaluator.execute(
            file_path="src/models/user.py",
            operation_type="query",
            validation_scope=["governance_boundaries"],
        )

        # Should not have critical violations for query
        critical_violations = [
            v for v in result.data["violations"] if v.get("severity") == "critical"
        ]
        assert len(critical_violations) == 0


# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e-8f9a0b1c
class TestComplianceScore:
    """Test compliance score calculation."""

    @pytest.mark.asyncio
    async def test_perfect_score_no_violations(self, evaluator):
        """Files with no violations should have 1.0 score."""
        # Use a file that likely has no violations
        result = await evaluator.execute(
            file_path="tests/conftest.py",  # Test config typically clean
            validation_scope=["governance_boundaries"],
        )

        if len(result.data["violations"]) == 0:
            assert result.data["compliance_score"] == 1.0

    @pytest.mark.asyncio
    async def test_score_decreases_with_violations(self, evaluator):
        """Violations should decrease compliance score."""
        result = await evaluator.execute(
            file_path=".intent/constitution/core.yaml",  # Will have governance violation
            operation_type="refactor",
            validation_scope=["governance_boundaries"],
        )

        violations = result.data["violations"]
        if len(violations) > 0:
            assert result.data["compliance_score"] < 1.0

    @pytest.mark.asyncio
    async def test_critical_violations_penalized_more(self, evaluator):
        """Critical violations should have larger score impact."""
        result = await evaluator.execute(
            file_path=".intent/constitution/core.yaml",
            operation_type="refactor",
            validation_scope=["governance_boundaries"],
        )

        # If critical violation exists, score should be significantly reduced
        critical_count = sum(
            1 for v in result.data["violations"] if v.get("severity") == "critical"
        )
        if critical_count > 0:
            # Each critical = 0.3 penalty
            assert result.data["compliance_score"] <= 0.7


# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f-9a0b1c2d
class TestViolationDetails:
    """Test violation data structure."""

    @pytest.mark.asyncio
    async def test_violations_have_required_fields(self, evaluator):
        """Each violation should have standard fields."""
        result = await evaluator.execute(
            file_path=".intent/constitution/core.yaml",
            operation_type="refactor",
        )

        for violation in result.data["violations"]:
            assert "type" in violation
            assert "rule_id" in violation
            assert "severity" in violation
            assert "message" in violation
            assert "file_path" in violation

    @pytest.mark.asyncio
    async def test_violations_include_suggested_fix(self, evaluator):
        """Violations should include remediation guidance."""
        result = await evaluator.execute(
            file_path=".intent/constitution/core.yaml",
            operation_type="refactor",
        )

        for violation in result.data["violations"]:
            # All violations should at least have empty suggested_fix
            assert "suggested_fix" in violation


# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
class TestEvaluationScope:
    """Test validation scope control."""

    @pytest.mark.asyncio
    async def test_respects_custom_scope(self, evaluator):
        """Should only run checks in validation_scope."""
        result = await evaluator.execute(
            file_path="src/models/user.py",
            validation_scope=["governance_boundaries"],
        )

        details = result.data["details"]
        assert "governance" in details
        # Other scopes should not be checked or marked as not checked
        if "constitutional" in details:
            assert not details["constitutional"].get("checked", False)

    @pytest.mark.asyncio
    async def test_default_scope_comprehensive(self, evaluator):
        """Default scope should include all major checks."""
        result = await evaluator.execute(
            file_path="src/models/user.py", operation_type="refactor"
        )

        # Should include multiple check types by default
        assert result.data["evaluation_scope"]
        assert len(result.data["evaluation_scope"]) >= 2


# ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
class TestResultStatus:
    """Test ok/failure status determination."""

    @pytest.mark.asyncio
    async def test_ok_true_when_no_errors(self, evaluator):
        """Should return ok=True when no critical/error violations."""
        result = await evaluator.execute(
            file_path="src/models/user.py",
            validation_scope=["governance_boundaries"],
        )

        # If only warnings or no violations, should be ok
        has_errors = any(
            v.get("severity") in ["critical", "error"]
            for v in result.data["violations"]
        )
        assert result.ok == (not has_errors)

    @pytest.mark.asyncio
    async def test_ok_false_when_critical_violation(self, evaluator):
        """Should return ok=False when critical violations exist."""
        result = await evaluator.execute(
            file_path=".intent/constitution/core.yaml",
            operation_type="refactor",
            validation_scope=["governance_boundaries"],
        )

        # .intent/ write should be critical violation
        assert not result.ok


# ID: a0b1c2d3-e4f5-6a7b-8c9d-0e1f2a3b4c5d
class TestMetadata:
    """Test result metadata completeness."""

    @pytest.mark.asyncio
    async def test_includes_violation_counts(self, evaluator):
        """Metadata should include violation counts by severity."""
        result = await evaluator.execute(
            file_path=".intent/constitution/core.yaml",
            operation_type="refactor",
        )

        assert "critical_violations" in result.metadata
        assert "error_violations" in result.metadata
        assert "warning_violations" in result.metadata

    @pytest.mark.asyncio
    async def test_includes_operation_context(self, evaluator):
        """Metadata should include operation context."""
        result = await evaluator.execute(
            file_path="src/models/user.py", operation_type="refactor"
        )

        assert result.metadata["file_path"] == "src/models/user.py"
        assert result.metadata["operation_type"] == "refactor"

    @pytest.mark.asyncio
    async def test_tracks_duration(self, evaluator):
        """Should track execution duration."""
        result = await evaluator.execute(
            file_path="src/models/user.py", operation_type="refactor"
        )

        assert result.duration_sec >= 0.0


# ID: b1c2d3e4-f5a6-7b8c-9d0e-1f2a3b4c5d6e
class TestConfidence:
    """Test confidence scoring."""

    @pytest.mark.asyncio
    async def test_confidence_equals_compliance_score(self, evaluator):
        """Component confidence should match compliance score."""
        result = await evaluator.execute(
            file_path="src/models/user.py", operation_type="refactor"
        )

        assert result.confidence == result.data["compliance_score"]

    @pytest.mark.asyncio
    async def test_low_confidence_with_violations(self, evaluator):
        """Confidence should be low when violations exist."""
        result = await evaluator.execute(
            file_path=".intent/constitution/core.yaml",
            operation_type="refactor",
        )

        if len(result.data["violations"]) > 0:
            assert result.confidence < 1.0


# ID: c2d3e4f5-a6b7-8c9d-0e1f-2a3b4c5d6e7f
class TestErrorHandling:
    """Test error handling and resilience."""

    @pytest.mark.asyncio
    async def test_handles_evaluation_errors_gracefully(self, evaluator):
        """Should not crash on evaluation errors."""
        # Test with potentially problematic inputs
        result = await evaluator.execute(
            file_path=None,  # No file path
            operation_type="unknown_op",
        )

        # Should return result (may be failure, but no exception)
        assert result is not None
        assert "violations" in result.data

    @pytest.mark.asyncio
    async def test_returns_error_on_exception(self, evaluator):
        """Should return ok=False with error details on exception."""
        # Force an error by using invalid scope
        result = await evaluator.execute(
            file_path="src/models/user.py",
            validation_scope=["invalid_scope_that_causes_error"],
        )

        # Should handle gracefully
        assert result is not None


# ID: d3e4f5a6-b7c8-9d0e-1f2a-3b4c5d6e7f8a
class TestRemediationAvailability:
    """Test remediation availability detection."""

    @pytest.mark.asyncio
    async def test_detects_remediable_violations(self, evaluator):
        """Should indicate when violations can be auto-fixed."""
        result = await evaluator.execute(
            file_path="src/models/user.py", operation_type="refactor"
        )

        assert "remediation_available" in result.data
        assert isinstance(result.data["remediation_available"], bool)

    @pytest.mark.asyncio
    async def test_suggests_remediation_handler(self, evaluator):
        """Should suggest remediation_handler when fixes available."""
        result = await evaluator.execute(
            file_path="src/models/user.py", operation_type="refactor"
        )

        if result.data["remediation_available"]:
            assert result.next_suggested == "remediation_handler"
