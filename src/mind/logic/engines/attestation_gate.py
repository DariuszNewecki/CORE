# src/mind/logic/engines/attestation_gate.py

"""
Attestation gate — the honest third outcome (ADR-113).

Some requirements cannot be settled by any automated method: "controls are
*appropriate* to the risk", "management has *reviewed* this". No deterministic
gate and no AI judgment can honestly decide them. Rather than fake a verdict or
silently drop the requirement, this engine emits a first-class
"requires human attestation" finding that states exactly what a human reviewer
must decide.

This is the mechanism behind the `attested` evidence class: the engine declares
`evidence_class = ATTESTED`, so `rule_executor` stamps every finding it produces
as attested. The finding is SURFACED, never skipped (ADR-113 D4) — silent
omission is precisely the dishonesty CORE's GRC gap-analysis is sold against.

The engine is context-level: an attestation requirement is about the corpus /
the organization, not a single file, so it emits one finding per requirement.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from .base import BaseEngine, EngineResult, EvidenceClass


if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


logger = getLogger(__name__)


# ID: 32bc579f-6dcb-49cc-80a9-ec7dd3d98007
class AttestationGateEngine(BaseEngine):
    """Emits a 'requires human attestation' finding for irreducibly-human rules.

    Params (from the rule mapping):
        prompt: str — what the reviewer must decide / confirm. Required;
            an attestation rule with no prompt cannot tell the human what to
            attest to, so the engine emits a configuration finding instead.
        reference: str | None — optional citation of the source clause the
            attestation discharges (surfaced in the evidence trail).
    """

    engine_id = "attestation_gate"
    evidence_class = EvidenceClass.ATTESTED  # ADR-113: cannot be settled automatically

    @classmethod
    # ID: 0651c611-3de6-4317-836b-0cc8f4479be7
    def is_context_level_for(cls, check_type: str | None) -> bool:
        """Always context-level: an attestation requirement is about the corpus,
        not a per-file fact. Dispatched once per rule, not once per file."""
        return True

    # ID: f9fe367a-ed35-4dbf-a59d-f46b51c767ec
    async def verify(self, file_path: Path, params: dict[str, Any]) -> EngineResult:
        """Per-file path is a no-op — this engine only runs context-level.

        Present to satisfy the BaseEngine contract; the rule extractor routes
        attestation rules through ``verify_context`` (see ``is_context_level_for``).
        """
        return EngineResult(
            ok=True,
            message="attestation_gate is context-level; per-file verify is a no-op.",
            violations=[],
            engine_id=self.engine_id,
        )

    # ID: bce2b978-fae7-44dd-93f6-51bd70217b2c
    async def verify_context(
        self, context: AuditorContext, params: dict[str, Any]
    ) -> list[AuditFinding]:
        """Emit one finding stating what a human must attest to.

        The finding is always emitted — an attestation requirement is unresolved
        until a human signs it, so the gap report must show it (ADR-113 D4). The
        ``evidence_class`` is stamped ATTESTED by ``rule_executor`` from this
        engine's declared class; severity comes from the rule's enforcement.
        """
        prompt = params.get("prompt")
        if not prompt:
            # A misconfigured attestation rule (no prompt) is a config bug, not a
            # silent pass: surface it so the omission is visible.
            return [
                AuditFinding(
                    check_id=self.engine_id,
                    severity=AuditSeverity.HIGH,
                    message=(
                        "attestation_gate rule is missing a 'prompt' param — "
                        "cannot tell the reviewer what to attest to. Add "
                        "params.prompt to the rule's enforcement mapping."
                    ),
                    file_path=None,
                    context={
                        "finding_type": "ATTESTATION_MISCONFIGURED",
                        "engine_id": self.engine_id,
                    },
                )
            ]

        reference = params.get("reference")
        return [
            AuditFinding(
                check_id=self.engine_id,
                severity=AuditSeverity.MEDIUM,
                message=f"HUMAN ATTESTATION REQUIRED — {prompt}",
                file_path=None,
                context={
                    "finding_type": "REQUIRES_ATTESTATION",
                    "engine_id": self.engine_id,
                    "attestation_prompt": prompt,
                    "reference": reference,
                },
            )
        ]
