# src/body/evaluators/security_evaluator.py

"""
SecurityEvaluator - Identifies security risks and vulnerabilities.

Constitutional Alignment:
- Phase: AUDIT (Quality assessment and pattern detection)
- Authority: POLICY (Enforces data.security.no_raw_secrets and security rules)
- Purpose: Evaluate security posture of code and operations
- Boundary: Read-only analysis, no mutations

This component EVALUATES security, does not FIX vulnerabilities.
Remediation happens in subsequent phases based on evaluation results.

Security Dimensions:
1. **Secrets**: API keys, passwords, tokens in code
2. **Injection**: SQL injection, command injection risks
3. **Authentication**: Auth bypass, weak credentials
4. **Authorization**: Permission checks, access control
5. **Data**: Sensitive data exposure, encryption

Usage:
    evaluator = SecurityEvaluator()
    result = await evaluator.execute(
        file_path="src/services/user.py",
        code_content=code
    )

    if not result.ok:
        print(f"Security issues: {result.data['vulnerabilities']}")
"""

from __future__ import annotations

import re
import time
from typing import Any, ClassVar

from shared.component_primitive import Component, ComponentPhase, ComponentResult
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 38cbc2dd-3201-428c-bd8a-9001d5236768
class SecurityEvaluator(Component):
    """
    Evaluates security posture and identifies vulnerabilities.

    Security Checks:
    - secrets_exposure: Hardcoded API keys, passwords
    - sql_injection: Unsafe SQL query construction
    - command_injection: Unsafe shell command construction
    - path_traversal: Directory traversal vulnerabilities
    - insecure_deserialization: Pickle, eval() usage
    - weak_crypto: MD5, SHA1, weak algorithms
    - sensitive_data_logging: PII in logs

    Severity Levels:
    - critical: Immediate security risk (secrets exposure, SQL injection)
    - high: Significant risk (command injection, weak crypto)
    - medium: Potential risk (insecure patterns)
    - low: Security concern (missing validations)

    Output provides:
    - Binary security status (ok: True/False)
    - List of vulnerabilities with severity
    - Security score (0.0-1.0)
    - Risk assessment
    - Remediation guidance
    """

    # Regex patterns for security checks
    PATTERNS: ClassVar[dict[str, list[str]]] = {
        "api_keys": [
            r"(sk-[a-zA-Z0-9]{32,})",  # Generic API key
            r"(AI[a-zA-Z0-9]{32,})",  # Anthropic/Ollama pattern
            r"(ghp_[a-zA-Z0-9]{36})",  # GitHub token
            r"(xox[baprs]-[a-zA-Z0-9-]{10,})",  # Slack token
        ],
        "passwords": [
            r"PASSWORD\s*=\s*['\"][^'\"]+['\"]",
            r"password\s*:\s*['\"][^'\"]+['\"]",
            r"pwd\s*=\s*['\"][^'\"]+['\"]",
        ],
        "sql_unsafe": [
            r"execute\([^)]*%[^)]*\)",  # String formatting in execute
            r"execute\([^)]*\+[^)]*\)",  # String concatenation
            r"execute\([^)]*f['\"]",  # F-string in execute
        ],
        "command_unsafe": [
            r"os\.system\([^)]*\+",  # String concat in os.system
            r"subprocess\.(run|call|Popen)\([^)]*\+",  # Unsafe subprocess
            r"shell=True",  # Shell=True without validation
        ],
        "eval_usage": [
            r"\beval\(",
            r"\bexec\(",
            r"pickle\.loads?\(",
        ],
        "weak_crypto": [
            r"hashlib\.md5\(",
            r"hashlib\.sha1\(",
            r"random\.random\(",  # Weak random for security
        ],
    }

    @property
    # ID: d5e82c82-62ff-41b5-abc2-d97a45e6e411
    def phase(self) -> ComponentPhase:
        """SecurityEvaluator operates in AUDIT phase."""
        return ComponentPhase.AUDIT

    # ID: 486b01bb-c6e6-493f-a19a-bf0d7a0ed3d8
    async def execute(
        self,
        file_path: str | None = None,
        code_content: str | None = None,
        check_scope: list[str] | None = None,
        **kwargs: Any,
    ) -> ComponentResult:
        """
        Evaluate security posture of code.

        Args:
            file_path: Path to file being evaluated
            code_content: Code to analyze (if not reading from file)
            check_scope: Specific checks to run (default: all)
            **kwargs: Additional context

        Returns:
            ComponentResult with security assessment
        """
        start_time = time.time()

        # Default to all checks
        scope = check_scope or [
            "secrets_exposure",
            "sql_injection",
            "command_injection",
            "insecure_deserialization",
            "weak_crypto",
        ]

        # Collect vulnerabilities
        vulnerabilities = []

        if code_content:
            if "secrets_exposure" in scope:
                vulnerabilities.extend(self._check_secrets(code_content, file_path))

            if "sql_injection" in scope:
                vulnerabilities.extend(
                    self._check_sql_injection(code_content, file_path)
                )

            if "command_injection" in scope:
                vulnerabilities.extend(
                    self._check_command_injection(code_content, file_path)
                )

            if "insecure_deserialization" in scope:
                vulnerabilities.extend(
                    self._check_insecure_deserialization(code_content, file_path)
                )

            if "weak_crypto" in scope:
                vulnerabilities.extend(self._check_weak_crypto(code_content, file_path))

        # Calculate security score
        security_score = self._calculate_score(vulnerabilities)

        # Determine if security is acceptable
        # Critical or High vulnerabilities = fail
        blocking_vulns = [
            v for v in vulnerabilities if v["severity"] in ["critical", "high"]
        ]
        ok = len(blocking_vulns) == 0

        logger.info(
            "SecurityEvaluator: %s (score: %.2f, %d vulnerabilities)",
            "PASS" if ok else "FAIL",
            security_score,
            len(vulnerabilities),
        )

        return ComponentResult(
            component_id=self.component_id,
            ok=ok,
            phase=self.phase,
            data={
                "vulnerabilities": vulnerabilities,
                "security_score": security_score,
                "risk_level": self._assess_risk(vulnerabilities),
                "check_scope": scope,
            },
            confidence=security_score,
            next_suggested="security_remediation" if vulnerabilities else None,
            metadata={
                "file_path": file_path,
                "critical_count": len(
                    [v for v in vulnerabilities if v["severity"] == "critical"]
                ),
                "high_count": len(
                    [v for v in vulnerabilities if v["severity"] == "high"]
                ),
                "medium_count": len(
                    [v for v in vulnerabilities if v["severity"] == "medium"]
                ),
            },
            duration_sec=time.time() - start_time,
        )

    # ID: 33fc128d-2634-4561-8930-3459a8d757cc
    def _check_secrets(self, code: str, file_path: str | None) -> list[dict[str, Any]]:
        """Check for hardcoded secrets (API keys, passwords)."""
        vulnerabilities = []

        # Check API keys
        for pattern in self.PATTERNS["api_keys"]:
            matches = re.finditer(pattern, code)
            for match in matches:
                vulnerabilities.append(
                    {
                        "type": "secrets_exposure",
                        "severity": "critical",
                        "message": "Hardcoded API key detected",
                        "file_path": file_path,
                        "pattern": pattern,
                        "matched_text": match.group(0)[:10] + "...",  # Redact
                        "remediation": "Store secrets in database using SecretsService",
                    }
                )

        # Check passwords
        for pattern in self.PATTERNS["passwords"]:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                vulnerabilities.append(
                    {
                        "type": "secrets_exposure",
                        "severity": "critical",
                        "message": "Hardcoded password detected",
                        "file_path": file_path,
                        "pattern": pattern,
                        "remediation": "Use SecretService.get_secret() for password retrieval",
                    }
                )

        return vulnerabilities

    # ID: 6dcecf50-1498-4274-87c5-a804d273fe1b
    def _check_sql_injection(
        self, code: str, file_path: str | None
    ) -> list[dict[str, Any]]:
        """Check for SQL injection vulnerabilities."""
        vulnerabilities = []

        for pattern in self.PATTERNS["sql_unsafe"]:
            matches = re.finditer(pattern, code)
            for match in matches:
                vulnerabilities.append(
                    {
                        "type": "sql_injection",
                        "severity": "critical",
                        "message": "Potential SQL injection vulnerability",
                        "file_path": file_path,
                        "pattern": pattern,
                        "code_snippet": match.group(0),
                        "remediation": "Use parameterized queries with text() binding or ORM methods",
                    }
                )

        return vulnerabilities

    # ID: 78cc9f10-458f-4b1b-935e-4d273b1ffbb5
    def _check_command_injection(
        self, code: str, file_path: str | None
    ) -> list[dict[str, Any]]:
        """Check for command injection vulnerabilities."""
        vulnerabilities = []

        for pattern in self.PATTERNS["command_unsafe"]:
            matches = re.finditer(pattern, code)
            for match in matches:
                severity = "critical" if "shell=True" in match.group(0) else "high"
                vulnerabilities.append(
                    {
                        "type": "command_injection",
                        "severity": severity,
                        "message": "Potential command injection vulnerability",
                        "file_path": file_path,
                        "pattern": pattern,
                        "code_snippet": match.group(0),
                        "remediation": "Use list arguments instead of string concatenation; avoid shell=True",
                    }
                )

        return vulnerabilities

    # ID: 5c43ccb9-1e8b-4c61-b74b-fb92395896f8
    def _check_insecure_deserialization(
        self, code: str, file_path: str | None
    ) -> list[dict[str, Any]]:
        """Check for insecure deserialization (eval, exec, pickle)."""
        vulnerabilities = []

        for pattern in self.PATTERNS["eval_usage"]:
            matches = re.finditer(pattern, code)
            for match in matches:
                func_name = match.group(0).split("(")[0]
                vulnerabilities.append(
                    {
                        "type": "insecure_deserialization",
                        "severity": "high",
                        "message": f"Unsafe deserialization using {func_name}",
                        "file_path": file_path,
                        "pattern": pattern,
                        "code_snippet": match.group(0),
                        "remediation": f"Avoid {func_name}; use safe alternatives like ast.literal_eval or json",
                    }
                )

        return vulnerabilities

    # ID: 23ef335e-2536-46b4-9bdd-44b3bb300180
    def _check_weak_crypto(
        self, code: str, file_path: str | None
    ) -> list[dict[str, Any]]:
        """Check for weak cryptographic algorithms."""
        vulnerabilities = []

        for pattern in self.PATTERNS["weak_crypto"]:
            matches = re.finditer(pattern, code)
            for match in matches:
                algo = match.group(0)
                vulnerabilities.append(
                    {
                        "type": "weak_crypto",
                        "severity": "high",  # Weak crypto is a real security issue
                        "message": f"Weak cryptographic algorithm: {algo}",
                        "file_path": file_path,
                        "pattern": pattern,
                        "code_snippet": match.group(0),
                        "remediation": "Use SHA256 or better; use secrets.token_bytes() for random",
                    }
                )

        return vulnerabilities

    # ID: ad6da84d-5870-4c55-ae35-5c18f895587d
    def _calculate_score(self, vulnerabilities: list[dict[str, Any]]) -> float:
        """
        Calculate security score (0.0-1.0).

        Score decreases based on vulnerability severity:
        - critical: -0.4 per vuln
        - high: -0.2 per vuln
        - medium: -0.1 per vuln
        - low: -0.05 per vuln
        """
        score = 1.0

        severity_penalties = {
            "critical": 0.4,
            "high": 0.2,
            "medium": 0.1,
            "low": 0.05,
        }

        for vuln in vulnerabilities:
            penalty = severity_penalties.get(vuln["severity"], 0.1)
            score -= penalty

        return max(0.0, round(score, 2))

    # ID: e0a92afc-1159-479c-a204-6324a0197a91
    def _assess_risk(self, vulnerabilities: list[dict[str, Any]]) -> str:
        """
        Assess overall risk level.

        Returns: "critical" | "high" | "medium" | "low" | "none"
        """
        if not vulnerabilities:
            return "none"

        severities = [v["severity"] for v in vulnerabilities]

        if "critical" in severities:
            return "critical"
        if "high" in severities:
            return "high"
        if "medium" in severities:
            return "medium"
        return "low"
