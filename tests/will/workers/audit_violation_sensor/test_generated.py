from typing import List, Dict, Any, Optional

class AuditViolationSensor:
    # Existing class definition from src/will/workers/audit_violation_sensor.py
    pass


def mock_normalize_audit_findings(core_context, rule_namespace, rule_ids) -> List[Dict[str, Any]]:
    """
    Mock function to simulate the normalization of audit findings.
    """
    return [
        {"rule_id": "R1", "file_path": "/path/to/file1.txt", "line_number": 42, "message": "Error message 1"},
        {"rule_id": "R2", "file_path": "/path/to/file2.txt", "line_number": 78, "message": "Error message 2"}
    ]


def mock_filter_actionable_violations(violations) -> List[Dict[str, Any]]:
    """
    Mock function to simulate filtering actionable violations.
    """
    return [
        {"rule_id": "R1", "file_path": "/path/to/file1.txt", "line_number": 42, "message": "Error message 1"}
    ]


def mock_find_cause_for_file(file_path, lookback_seconds) -> Dict[str, Any]:
    """
    Mock function to simulate finding a cause for a file.
    """
    return {"causing_proposal_id": "P1", "causing_commit_sha": "C1"}


async def test_audit_violation_sensor_run_complete():
    sensor = AuditViolationSensor()
    core_context = mock_core_context()  # Assume this function is defined elsewhere
    rule_namespace = "example_ns"

    # Mocking the methods to simulate behavior
    sensor.normalize_audit_findings = mock_normalize_audit_findings
    sensor.filter_actionable_violations = mock_filter_actionable_violations

    # Call the method that we want to test
    await sensor.run(core_context, rule_namespace)

    # Assert expected outcomes
    expected_payload = {
        "rule_namespace": "example_ns",
        "rule_ids_resolved": 2,
        "violations_found": 2,
        "filtered_unactionable": 0,
        "posted": 2,
        "skipped_duplicates": 0,
        "dry_run": False,
        "message": (
            "Run complete. 2 findings posted, "
            "0 duplicates skipped, "
            "0 unactionable filtered."
        ),
    }

    # Add assertions to test the expected outcomes
    assert core_context.registry.get_blackboard_service().fetch_active_finding_subjects_by_prefix.call_count == 1
    assert core_context.registry.get_consequence_log_service().find_cause_for_file.call_count == 2


def mock_core_context() -> Any:
    """
    Mock function to simulate the core context object.
    """
    # This is a simplified mock of what a core context might look like
    class CoreContext:
        def __init__(self, registry):
            self.registry = registry

    # Create an instance of the registry and return it with a blackboard service
    registry = MockRegistry()
    blackboard_service = MagicMock()
    registry.get_blackboard_service.return_value = blackboard_service
    return CoreContext(registry)


class MockRegistry:
    pass


def mock_get_consequence_log_service() -> Any:
    """
    Mock function to simulate the consequence log service.
    """
    class ConsequenceLogService:
        def find_cause_for_file(self, file_path, lookback_seconds):
            # Simulate finding a cause for a file
            return {"causing_proposal_id": "P1", "causing_commit_sha": "C1"}

    return ConsequenceLogService()


def mock_get_blackboard_service() -> Any:
    """
    Mock function to simulate the blackboard service.
    """
    class BlackboardService:
        def fetch_active_finding_subjects_by_prefix(self, prefix):
            # Simulate fetching finding subjects by prefix
            return {"_FINDING_SUBJECT::example_ns::/path/to/file1.txt": None}

    return BlackboardService()


if __name__ == "__main__":
    import unittest
    unittest.main()
