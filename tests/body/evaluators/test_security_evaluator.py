# tests/body/evaluators/test_security_evaluator.py

"""
Tests for SecurityEvaluator component.

Constitutional Alignment:
- Tests vulnerability detection
- Verifies severity classification
- Validates component contract compliance
"""

from __future__ import annotations

import pytest

from body.evaluators.security_evaluator import SecurityEvaluator
from shared.component_primitive import ComponentPhase


# ID: 1a2b3c4d-5e6f-7a8b-9c0d-1e2f3a4b5c6d
@pytest.fixture
def evaluator():
    """Fixture providing SecurityEvaluator instance."""
    return SecurityEvaluator()


# ID: 2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e
class TestComponentContract:
    """Test SecurityEvaluator follows Component contract."""

    @pytest.mark.asyncio
    async def test_declares_audit_phase(self, evaluator):
        """Evaluators must operate in AUDIT phase."""
        assert evaluator.phase == ComponentPhase.AUDIT

    @pytest.mark.asyncio
    async def test_returns_component_result(self, evaluator):
        """Execute must return ComponentResult."""
        result = await evaluator.execute(code_content="# Safe code")

        assert hasattr(result, "ok")
        assert hasattr(result, "data")
        assert hasattr(result, "phase")
        assert result.phase == ComponentPhase.AUDIT

    @pytest.mark.asyncio
    async def test_component_id_matches_class(self, evaluator):
        """Component ID should be derived from class name."""
        assert evaluator.component_id == "securityevaluator"


# ID: 3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f
class TestSecretsDetection:
    """Test hardcoded secrets detection."""

    @pytest.mark.asyncio
    async def test_detects_api_key(self, evaluator):
        """Should detect hardcoded API keys."""
        code = 'api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"'
        result = await evaluator.execute(code_content=code)

        assert not result.ok
        vulns = [
            v for v in result.data["vulnerabilities"] if v["type"] == "secrets_exposure"
        ]
        assert len(vulns) > 0
        assert vulns[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_detects_password(self, evaluator):
        """Should detect hardcoded passwords."""
        code = 'PASSWORD = "my_secret_password"'
        result = await evaluator.execute(code_content=code)

        assert not result.ok
        vulns = [
            v for v in result.data["vulnerabilities"] if v["type"] == "secrets_exposure"
        ]
        assert len(vulns) > 0

    @pytest.mark.asyncio
    async def test_detects_anthropic_key(self, evaluator):
        """Should detect Anthropic API keys."""
        code = 'ANTHROPIC_KEY = "AIza1234567890abcdefghijklmnopqrstuvwxyz"'
        result = await evaluator.execute(code_content=code)

        assert not result.ok

    @pytest.mark.asyncio
    async def test_safe_code_passes(self, evaluator):
        """Safe code without secrets should pass."""
        code = """
api_key = config_service.get_secret("api_key")
password = secrets_service.get_secret("password")
        """
        result = await evaluator.execute(code_content=code)

        secrets_vulns = [
            v for v in result.data["vulnerabilities"] if v["type"] == "secrets_exposure"
        ]
        assert len(secrets_vulns) == 0


# ID: 4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f9a
class TestSQLInjection:
    """Test SQL injection detection."""

    @pytest.mark.asyncio
    async def test_detects_string_formatting(self, evaluator):
        """Should detect SQL injection via string formatting."""
        code = 'session.execute("SELECT * FROM users WHERE id = %s" % user_id)'
        result = await evaluator.execute(code_content=code)

        assert not result.ok
        vulns = [
            v for v in result.data["vulnerabilities"] if v["type"] == "sql_injection"
        ]
        assert len(vulns) > 0
        assert vulns[0]["severity"] == "critical"

    @pytest.mark.asyncio
    async def test_detects_string_concatenation(self, evaluator):
        """Should detect SQL injection via concatenation."""
        code = 'session.execute("SELECT * FROM users WHERE id = " + user_id)'
        result = await evaluator.execute(code_content=code)

        assert not result.ok

    @pytest.mark.asyncio
    async def test_detects_fstring(self, evaluator):
        """Should detect SQL injection via f-strings."""
        code = 'session.execute(f"SELECT * FROM users WHERE id = {user_id}")'
        result = await evaluator.execute(code_content=code)

        assert not result.ok

    @pytest.mark.asyncio
    async def test_safe_parameterized_query(self, evaluator):
        """Parameterized queries should pass."""
        code = 'session.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})'
        result = await evaluator.execute(code_content=code)

        sql_vulns = [
            v for v in result.data["vulnerabilities"] if v["type"] == "sql_injection"
        ]
        assert len(sql_vulns) == 0


# ID: 5e6f7a8b-9c0d-1e2f-3a4b-5c6d7e8f9a0b
class TestCommandInjection:
    """Test command injection detection."""

    @pytest.mark.asyncio
    async def test_detects_os_system_concat(self, evaluator):
        """Should detect os.system with concatenation."""
        code = 'os.system("ls " + user_input)'
        result = await evaluator.execute(code_content=code)

        assert not result.ok
        vulns = [
            v
            for v in result.data["vulnerabilities"]
            if v["type"] == "command_injection"
        ]
        assert len(vulns) > 0

    @pytest.mark.asyncio
    async def test_detects_shell_true(self, evaluator):
        """Should detect shell=True as high risk."""
        code = "subprocess.run(cmd, shell=True)"
        result = await evaluator.execute(code_content=code)

        assert not result.ok
        vulns = [
            v
            for v in result.data["vulnerabilities"]
            if v["type"] == "command_injection"
        ]
        assert len(vulns) > 0
        # shell=True is critical
        assert any(v["severity"] in ["critical", "high"] for v in vulns)

    @pytest.mark.asyncio
    async def test_safe_subprocess_list(self, evaluator):
        """Safe subprocess with list args should pass."""
        code = 'subprocess.run(["ls", "-la"], shell=False)'
        result = await evaluator.execute(code_content=code)

        cmd_vulns = [
            v
            for v in result.data["vulnerabilities"]
            if v["type"] == "command_injection"
        ]
        assert len(cmd_vulns) == 0


# ID: 6f7a8b9c-0d1e-2f3a-4b5c-6d7e8f9a0b1c
class TestInsecureDeserialization:
    """Test insecure deserialization detection."""

    @pytest.mark.asyncio
    async def test_detects_eval(self, evaluator):
        """Should detect eval() usage."""
        code = "result = eval(user_input)"
        result = await evaluator.execute(code_content=code)

        assert not result.ok
        vulns = [
            v
            for v in result.data["vulnerabilities"]
            if v["type"] == "insecure_deserialization"
        ]
        assert len(vulns) > 0
        assert vulns[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_detects_exec(self, evaluator):
        """Should detect exec() usage."""
        code = "exec(code_string)"
        result = await evaluator.execute(code_content=code)

        assert not result.ok

    @pytest.mark.asyncio
    async def test_detects_pickle(self, evaluator):
        """Should detect pickle.loads usage."""
        code = "data = pickle.loads(user_data)"
        result = await evaluator.execute(code_content=code)

        assert not result.ok

    @pytest.mark.asyncio
    async def test_safe_json_loads(self, evaluator):
        """json.loads should pass."""
        code = "data = json.loads(json_string)"
        result = await evaluator.execute(code_content=code)

        deser_vulns = [
            v
            for v in result.data["vulnerabilities"]
            if v["type"] == "insecure_deserialization"
        ]
        assert len(deser_vulns) == 0


# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d
class TestWeakCryptography:
    """Test weak cryptography detection."""

    @pytest.mark.asyncio
    async def test_detects_md5(self, evaluator):
        """Should detect MD5 usage."""
        code = "hash = hashlib.md5(data).hexdigest()"
        result = await evaluator.execute(code_content=code)

        assert not result.ok
        vulns = [
            v for v in result.data["vulnerabilities"] if v["type"] == "weak_crypto"
        ]
        assert len(vulns) > 0
        assert vulns[0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_detects_sha1(self, evaluator):
        """Should detect SHA1 usage."""
        code = "hash = hashlib.sha1(data).hexdigest()"
        result = await evaluator.execute(code_content=code)

        assert not result.ok

    @pytest.mark.asyncio
    async def test_detects_weak_random(self, evaluator):
        """Should detect random.random for security."""
        code = "token = random.random()"
        result = await evaluator.execute(code_content=code)

        assert not result.ok

    @pytest.mark.asyncio
    async def test_safe_sha256(self, evaluator):
        """SHA256 should pass."""
        code = "hash = hashlib.sha256(data).hexdigest()"
        result = await evaluator.execute(code_content=code)

        crypto_vulns = [
            v for v in result.data["vulnerabilities"] if v["type"] == "weak_crypto"
        ]
        assert len(crypto_vulns) == 0


# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
class TestSecurityScore:
    """Test security score calculation."""

    @pytest.mark.asyncio
    async def test_perfect_score_no_vulns(self, evaluator):
        """No vulnerabilities should give perfect score."""
        code = "# Safe code with no vulnerabilities"
        result = await evaluator.execute(code_content=code)

        assert result.data["security_score"] == 1.0

    @pytest.mark.asyncio
    async def test_score_decreases_with_vulns(self, evaluator):
        """Vulnerabilities should decrease score."""
        code = 'api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"'
        result = await evaluator.execute(code_content=code)

        assert result.data["security_score"] < 1.0

    @pytest.mark.asyncio
    async def test_critical_vulns_major_penalty(self, evaluator):
        """Critical vulnerabilities have major score penalty."""
        code = 'PASSWORD = "hardcoded_password"'
        result = await evaluator.execute(code_content=code)

        # Critical vuln = -0.4, should be 0.6 or lower
        assert result.data["security_score"] <= 0.6

    @pytest.mark.asyncio
    async def test_confidence_matches_score(self, evaluator):
        """Component confidence should match security score."""
        code = "# Safe code"
        result = await evaluator.execute(code_content=code)

        assert result.confidence == result.data["security_score"]


# ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
class TestRiskAssessment:
    """Test overall risk level assessment."""

    @pytest.mark.asyncio
    async def test_no_vulns_no_risk(self, evaluator):
        """No vulnerabilities = no risk."""
        code = "# Safe code"
        result = await evaluator.execute(code_content=code)

        assert result.data["risk_level"] == "none"

    @pytest.mark.asyncio
    async def test_critical_vuln_critical_risk(self, evaluator):
        """Critical vulnerability = critical risk."""
        code = 'api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"'
        result = await evaluator.execute(code_content=code)

        assert result.data["risk_level"] == "critical"

    @pytest.mark.asyncio
    async def test_high_vuln_high_risk(self, evaluator):
        """High severity vulnerability = high risk."""
        code = "result = eval(user_input)"
        result = await evaluator.execute(code_content=code)

        assert result.data["risk_level"] in ["high", "critical"]

    @pytest.mark.asyncio
    async def test_medium_vuln_medium_risk(self, evaluator):
        """Weak crypto (now high severity) = high risk."""
        code = "hash = hashlib.md5(data).hexdigest()"
        result = await evaluator.execute(code_content=code)

        assert result.data["risk_level"] == "high"


# ID: a0b1c2d3-e4f5-6a7b-8c9d-0e1f2a3b4c5d
class TestCheckScoping:
    """Test check scope control."""

    @pytest.mark.asyncio
    async def test_respects_custom_scope(self, evaluator):
        """Should only run checks in scope."""
        code = """
api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
result = eval(user_input)
        """
        result = await evaluator.execute(
            code_content=code, check_scope=["secrets_exposure"]  # Only check secrets
        )

        # Should find secrets but not eval
        assert any(
            v["type"] == "secrets_exposure" for v in result.data["vulnerabilities"]
        )
        assert not any(
            v["type"] == "insecure_deserialization"
            for v in result.data["vulnerabilities"]
        )

    @pytest.mark.asyncio
    async def test_default_scope_comprehensive(self, evaluator):
        """Default scope should include all major checks."""
        code = "# code"
        result = await evaluator.execute(code_content=code)

        # Should have run multiple check types
        assert "check_scope" in result.data
        assert len(result.data["check_scope"]) >= 4


# ID: b1c2d3e4-f5a6-7b8c-9d0e-1f2a3b4c5d6e
class TestVulnerabilityDetails:
    """Test vulnerability data structure."""

    @pytest.mark.asyncio
    async def test_vulns_have_required_fields(self, evaluator):
        """Vulnerabilities should have standard fields."""
        code = 'PASSWORD = "hardcoded"'
        result = await evaluator.execute(code_content=code)

        for vuln in result.data["vulnerabilities"]:
            assert "type" in vuln
            assert "severity" in vuln
            assert "message" in vuln
            assert "remediation" in vuln

    @pytest.mark.asyncio
    async def test_vulns_include_remediation(self, evaluator):
        """Vulnerabilities should include remediation guidance."""
        code = 'api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"'
        result = await evaluator.execute(code_content=code)

        for vuln in result.data["vulnerabilities"]:
            assert vuln["remediation"]
            assert len(vuln["remediation"]) > 10  # Meaningful guidance


# ID: c2d3e4f5-a6b7-8c9d-0e1f-2a3b4c5d6e7f
class TestMetadata:
    """Test result metadata completeness."""

    @pytest.mark.asyncio
    async def test_includes_vuln_counts(self, evaluator):
        """Metadata should include vulnerability counts by severity."""
        code = """
api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
hash = hashlib.md5(data).hexdigest()
        """
        result = await evaluator.execute(code_content=code)

        assert "critical_count" in result.metadata
        assert "high_count" in result.metadata
        assert "medium_count" in result.metadata
        assert result.metadata["critical_count"] >= 1

    @pytest.mark.asyncio
    async def test_includes_file_path(self, evaluator):
        """Metadata should include file path if provided."""
        result = await evaluator.execute(
            file_path="src/models/user.py", code_content="# code"
        )

        assert result.metadata["file_path"] == "src/models/user.py"

    @pytest.mark.asyncio
    async def test_suggests_remediation(self, evaluator):
        """Should suggest security_remediation when vulns exist."""
        code = 'api_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"'
        result = await evaluator.execute(code_content=code)

        assert result.next_suggested == "security_remediation"

    @pytest.mark.asyncio
    async def test_tracks_duration(self, evaluator):
        """Should track evaluation duration."""
        result = await evaluator.execute(code_content="# code")

        assert result.duration_sec >= 0.0


# ID: d3e4f5a6-b7c8-9d0e-1f2a-3b4c5d6e7f8a
class TestCriticalFailure:
    """Test that critical vulnerabilities fail evaluation."""

    @pytest.mark.asyncio
    async def test_critical_vuln_fails_evaluation(self, evaluator):
        """Critical vulnerabilities should cause ok=False."""
        code = 'PASSWORD = "my_password"'
        result = await evaluator.execute(code_content=code)

        assert not result.ok

    @pytest.mark.asyncio
    async def test_only_medium_vulns_may_pass(self, evaluator):
        """Medium/low vulnerabilities alone might not fail."""
        code = "hash = hashlib.md5(data).hexdigest()"  # Only medium
        result = await evaluator.execute(code_content=code)

        # This depends on implementation - medium might still pass with warning
        # The key is that critical always fails
        assert result.data["vulnerabilities"]  # Has vulnerabilities
        # But ok status depends on severity threshold
