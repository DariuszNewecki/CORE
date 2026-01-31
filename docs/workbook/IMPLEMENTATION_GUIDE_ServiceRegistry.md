# ServiceRegistry Constitutionalization - Implementation Guide

## STATUS: Week 1 Critical Path

**Goal:** Close the constitutional blind spot by making ServiceRegistry visible and bounded.

**Timeline:** 7 days

**Success Criteria:**
- [ ] Infrastructure defined in constitutional terms
- [ ] ServiceRegistry documented as infrastructure
- [ ] Audit logging added to all ServiceRegistry operations
- [ ] Enforcement rules deployed and passing
- [ ] No constitutional violations from infrastructure components

---

## Day 1: Constitutional Documentation

### Task 1.1: Add Infrastructure Paper to Constitution
```bash
# Copy the paper into your .intent/ directory
cp CORE-Infrastructure-Definition.md .intent/papers/

# Verify it's in git
git add .intent/papers/CORE-Infrastructure-Definition.md
git commit -m "constitutional: define infrastructure and ServiceRegistry authority"
```

### Task 1.2: Update Charter to Reference Infrastructure
Edit `.intent/CORE-CHARTER.md`:

```markdown
## Constitutional Documents

CORE governance is defined by:

1. **Constitution** - `.intent/constitution/CORE-CONSTITUTION-v0.md`
   - Defines the four primitives: Document, Rule, Phase, Authority

2. **Architectural Separation** - `.intent/papers/CORE-Mind-Body-Will-Separation.md`
   - Defines Mind/Body/Will layers and their boundaries

3. **Infrastructure Definition** - `.intent/papers/CORE-Infrastructure-Definition.md` **← ADD THIS**
   - Defines infrastructure category and authority boundaries
   - Documents ServiceRegistry constitutional status

4. **Enforcement Mappings** - `.intent/enforcement/mappings/**/*.yaml`
   - Machine-executable rules derived from constitutional papers
```

### Task 1.3: Update Constitution Papers Index
If you have a papers index or README, add:

```markdown
## Papers by Topic

### Foundational
- `CORE-Constitutional-Foundations.md` - What makes CORE constitutional
- `CORE-Constitution-Read-Only-Contract.md` - Mind immutability principle

### Architectural
- `CORE-Mind-Body-Will-Separation.md` - Three-layer architecture
- **`CORE-Infrastructure-Definition.md`** - Infrastructure category and boundaries **← ADD THIS**

### Governance
- `CORE-Common-Governance-Failure-Modes.md` - Prevention patterns
- `CORE-Authority-Without-Registries.md` - Authority model
```

---

## Day 2: Enforcement Mapping Deployment

### Task 2.1: Add Infrastructure Enforcement Rules
```bash
# Create the infrastructure enforcement directory
mkdir -p .intent/enforcement/mappings/infrastructure

# Copy enforcement mapping
cp authority_boundaries.yaml .intent/enforcement/mappings/infrastructure/

# Verify structure
tree .intent/enforcement/mappings/
```

Expected structure:
```
.intent/enforcement/mappings/
├── architecture/
│   ├── async_logic.yaml
│   ├── layer_separation.yaml
│   └── ...
├── code/
│   ├── purity.yaml
│   └── ...
├── infrastructure/          ← NEW
│   └── authority_boundaries.yaml
└── will/
    └── autonomy.yaml
```

### Task 2.2: Register Infrastructure Rules in System
Run constitutional audit to load new rules:

```bash
# This should load the new infrastructure rules
poetry run core-admin check audit --full

# Verify new rules are loaded
poetry run core-admin check rule --list | grep infrastructure
```

Expected output:
```
infrastructure.no_strategic_decisions          blocking    constitution
infrastructure.mandatory_audit_logging         reporting   constitution
infrastructure.constitutional_documentation    reporting   constitution
infrastructure.no_business_logic              blocking    constitution
infrastructure.service_registry.no_conditional_loading  blocking  constitution
infrastructure.service_registry.deterministic_behavior  blocking  constitution
infrastructure.no_selective_error_handling    blocking    constitution
infrastructure.health_check_required          reporting   constitution
```

### Task 2.3: Check for Immediate Violations
```bash
# Run audit focusing on infrastructure
poetry run core-admin check audit --scope infrastructure

# This will likely show violations of the new rules
# That's expected - we'll fix them in Days 3-5
```

---

## Day 3: ServiceRegistry Documentation Update

### Task 3.1: Add Constitutional Authority Docstring

Edit `src/shared/infrastructure/service_registry.py`:

```python
"""
Service Registry - Infrastructure Layer Component

CONSTITUTIONAL AUTHORITY: Infrastructure (coordination)

AUTHORITY DEFINITION:
ServiceRegistry is constitutionally classified as Infrastructure per
.intent/papers/CORE-Infrastructure-Definition.md

RESPONSIBILITIES:
- Dependency injection coordination
- Database session factory management
- Service lifecycle management
- Component wiring and instantiation

AUTHORITY LIMITS:
- Cannot decide which services to provide (services must be pre-declared)
- Cannot validate service requests semantically
- Cannot modify service behavior or inject middleware conditionally
- Cannot track usage for strategic decision-making

EXEMPTIONS:
- May import from any layer (required for dependency injection)
- Exempt from Mind/Body/Will layer restrictions
- Subject to infrastructure authority boundary rules

ENFORCEMENT:
- infrastructure.no_strategic_decisions (blocking)
- infrastructure.service_registry.no_conditional_loading (blocking)
- infrastructure.service_registry.deterministic_behavior (blocking)

See: .intent/papers/CORE-Infrastructure-Definition.md Section 5
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, ClassVar
from pathlib import Path

from shared.logger import getLogger

logger = getLogger(__name__)


class ServiceRegistry:
    """
    A singleton service locator and DI container.

    Constitutional Status: Infrastructure
    """
    # ... rest of implementation
```

### Task 3.2: Add Inline Constitutional Markers

Add comments to key methods:

```python
    @classmethod
    def prime(cls, session_factory: Callable) -> None:
        """
        Prime the registry with the DB session factory.

        CONSTITUTIONAL NOTE: Infrastructure coordination
        Authority: Mechanical wiring only, no decisions
        """
        cls._session_factory = session_factory
        logger.info(
            "INFRASTRUCTURE: service_registry_primed",
            authority="infrastructure_coordination"
        )

    @classmethod
    def session(cls):
        """
        Approved abstract factory for DB sessions.

        CONSTITUTIONAL NOTE: Infrastructure coordination
        Authority: Pass-through factory, no interpretation
        """
        if not cls._session_factory:
            raise RuntimeError("ServiceRegistry called before prime().")
        return cls._session_factory()
```

---

## Day 4: Audit Logging Implementation

### Task 4.1: Add Logging to get_service()

```python
    async def get_service(self, name: str) -> Any:
        """
        Orchestrates the lazy-loading of a service.

        CONSTITUTIONAL NOTE: Infrastructure coordination with audit trail
        """
        logger.info(
            "INFRASTRUCTURE: service_request",
            service=name,
            cached=(name in self._instances),
            authority="infrastructure_coordination",
            method="get_service"
        )

        # 1. Specialized Loaders
        if name == "qdrant":
            service = await self.get_qdrant_service()
            logger.info(
                "INFRASTRUCTURE: service_created",
                service=name,
                type="specialized_loader",
                authority="infrastructure_coordination"
            )
            return service

        if name == "cognitive_service":
            service = await self.get_cognitive_service()
            logger.info(
                "INFRASTRUCTURE: service_created",
                service=name,
                type="specialized_loader",
                authority="infrastructure_coordination"
            )
            return service

        # ... rest of method with similar logging
```

### Task 4.2: Add Logging to Specialized Loaders

```python
    async def get_qdrant_service(self) -> QdrantService:
        """Lazy loader for Qdrant infrastructure."""
        async with self._lock:
            if "qdrant" not in self._instances:
                logger.info(
                    "INFRASTRUCTURE: creating_qdrant_service",
                    url=self.qdrant_url,
                    collection=self.qdrant_collection_name,
                    authority="infrastructure_coordination"
                )
                from shared.infrastructure.clients.qdrant_client import QdrantService

                self._instances["qdrant"] = QdrantService(
                    url=self.qdrant_url,
                    collection_name=self.qdrant_collection_name
                )

                logger.info(
                    "INFRASTRUCTURE: qdrant_service_created",
                    authority="infrastructure_coordination"
                )

        return self._instances["qdrant"]
```

### Task 4.3: Add Logging to Session Operations

```python
    @classmethod
    def session(cls):
        """Approved abstract factory for DB sessions."""
        if not cls._session_factory:
            logger.error(
                "INFRASTRUCTURE: session_request_before_prime",
                authority="infrastructure_coordination"
            )
            raise RuntimeError("ServiceRegistry called before prime().")

        logger.debug(
            "INFRASTRUCTURE: session_created",
            authority="infrastructure_coordination"
        )
        return cls._session_factory()
```

---

## Day 5: Health Check Implementation

### Task 5.1: Add health_check() Method

Add this to `ServiceRegistry`:

```python
    async def health_check(self) -> dict[str, Any]:
        """
        Report infrastructure health status.

        CONSTITUTIONAL REQUIREMENT: Infrastructure must provide health checks
        See: .intent/enforcement/mappings/infrastructure/authority_boundaries.yaml

        Returns:
            Health status dictionary with component states
        """
        health = {
            "status": "healthy",
            "component": "ServiceRegistry",
            "constitutional_authority": "infrastructure",
            "checks": {}
        }

        # Check 1: Session factory availability
        health["checks"]["session_factory"] = {
            "status": "ok" if self._session_factory else "missing",
            "primed": self._session_factory is not None
        }

        # Check 2: Service registry state
        health["checks"]["service_registry"] = {
            "status": "ok" if self._initialized else "not_initialized",
            "cached_services": len(self._instances),
            "registered_services": len(self._service_map)
        }

        # Check 3: Critical services availability
        critical_services = ["cognitive_service", "auditor_context"]
        for svc in critical_services:
            try:
                instance = await self.get_service(svc)
                health["checks"][svc] = {
                    "status": "ok",
                    "available": True,
                    "type": type(instance).__name__
                }
            except Exception as e:
                health["checks"][svc] = {
                    "status": "error",
                    "available": False,
                    "error": str(e)
                }
                health["status"] = "degraded"

        return health
```

### Task 5.2: Add Health Check CLI Command

Create or update `src/body/cli/commands/infrastructure.py`:

```python
"""Infrastructure health and status commands."""

from __future__ import annotations

import asyncio
import json
from rich.console import Console
from rich.table import Table
import typer

from shared.infrastructure.service_registry import service_registry

app = typer.Typer(name="infrastructure", help="Infrastructure health and monitoring")
console = Console()


@app.command(name="health")
def health_command():
    """Check infrastructure component health."""
    asyncio.run(_health_async())


async def _health_async():
    """Async health check implementation."""
    console.print("[bold]Infrastructure Health Check[/bold]\n")

    # Check ServiceRegistry
    health = await service_registry.health_check()

    # Create status table
    table = Table(title="ServiceRegistry Health")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Details", style="green")

    # Overall status
    status_emoji = "✓" if health["status"] == "healthy" else "⚠"
    table.add_row(
        "Overall Status",
        f"{status_emoji} {health['status']}",
        f"Authority: {health['constitutional_authority']}"
    )

    # Individual checks
    for check_name, check_data in health["checks"].items():
        status = check_data.get("status", "unknown")
        status_emoji = "✓" if status == "ok" else "✗"

        details = ", ".join([
            f"{k}: {v}" for k, v in check_data.items()
            if k != "status"
        ])

        table.add_row(
            check_name,
            f"{status_emoji} {status}",
            details
        )

    console.print(table)

    # Print raw JSON for programmatic access
    console.print("\n[dim]Raw JSON:[/dim]")
    console.print(json.dumps(health, indent=2))
```

Register in main CLI:

```python
# In src/body/cli/admin_cli.py
from body.cli.commands import infrastructure

app.add_typer(infrastructure.app, name="infrastructure")
```

---

## Day 6: Verification & Testing

### Task 6.1: Run Full Constitutional Audit

```bash
# Full audit with new infrastructure rules
poetry run core-admin check audit --full > audit_report.txt

# Check for infrastructure violations
grep -A5 "infrastructure\." audit_report.txt

# Expected: 0 blocking violations, some reporting violations OK
```

### Task 6.2: Test Health Check

```bash
# Run the new health check
poetry run core-admin infrastructure health

# Expected output:
# ✓ Overall Status: healthy
# ✓ session_factory: ok
# ✓ service_registry: ok
# ✓ cognitive_service: ok
# ✓ auditor_context: ok
```

### Task 6.3: Verify Audit Logs

```bash
# Run a command that uses ServiceRegistry
poetry run core-admin check quality

# Check logs for INFRASTRUCTURE markers
tail -f logs/core.log | grep "INFRASTRUCTURE:"

# Expected:
# INFO: INFRASTRUCTURE: service_request service=auditor_context cached=False
# INFO: INFRASTRUCTURE: service_created service=auditor_context type=specialized_loader
```

### Task 6.4: Test Service Loading

Write quick test in `src/shared/infrastructure/service_registry_test.py`:

```python
"""Test ServiceRegistry constitutional compliance."""

import pytest
from shared.infrastructure.service_registry import service_registry


@pytest.mark.asyncio
async def test_service_registry_health_check():
    """Verify health check is implemented."""
    health = await service_registry.health_check()

    assert "status" in health
    assert "constitutional_authority" in health
    assert health["constitutional_authority"] == "infrastructure"
    assert "checks" in health


@pytest.mark.asyncio
async def test_service_registry_deterministic():
    """Verify same service name produces same result."""
    # Request same service twice
    service1 = await service_registry.get_service("auditor_context")
    service2 = await service_registry.get_service("auditor_context")

    # Should be exact same instance (cached)
    assert service1 is service2


def test_service_registry_constitutional_docs():
    """Verify constitutional documentation is present."""
    import inspect

    # Get module docstring
    doc = inspect.getdoc(service_registry.__class__)

    # Must declare constitutional authority
    assert "CONSTITUTIONAL AUTHORITY" in doc
    assert "Infrastructure" in doc
    assert "AUTHORITY LIMITS" in doc
```

Run tests:
```bash
poetry run pytest src/shared/infrastructure/service_registry_test.py -v
```

---

## Day 7: Documentation & Commit

### Task 7.1: Update Project Documentation

Update `README.md` or `docs/architecture.md`:

```markdown
## Constitutional Architecture

CORE implements a constitutional governance model with explicit authority boundaries:

### Architectural Layers

1. **Mind** (`.intent/`, `src/mind/`)
   - Defines law and governance rules
   - Never executes, never decides

2. **Body** (`src/body/`)
   - Executes operations without deciding strategy
   - Never evaluates rules, never chooses between alternatives

3. **Will** (`src/will/`)
   - Makes strategic decisions and orchestrates Body
   - Never implements directly, never defines law

4. **Infrastructure** (`src/shared/infrastructure/`) **← NEW SECTION**
   - Provides mechanical coordination without strategic decisions
   - Bounded by constitutional authority limits
   - See: `.intent/papers/CORE-Infrastructure-Definition.md`

### Constitutional Documents

All governance is defined in:
- `.intent/constitution/CORE-CONSTITUTION-v0.md` - Foundational primitives
- `.intent/papers/CORE-Mind-Body-Will-Separation.md` - Layer boundaries
- `.intent/papers/CORE-Infrastructure-Definition.md` - Infrastructure category **← ADD**
- `.intent/enforcement/mappings/` - Executable enforcement rules
```

### Task 7.2: Create CHANGELOG Entry

Add to `.intent/CHANGELOG.md`:

```markdown
## v0.2 — Infrastructure Constitutionalization

**Status:** Active constitutional amendment

**Intent:**
Closes governance blind spot by explicitly defining infrastructure category
and documenting ServiceRegistry constitutional authority.

### Added

* **Infrastructure Constitutional Category**
  * Defined infrastructure as bounded exemption from layer restrictions
  * Established four criteria for infrastructure classification
  * Created authority boundary enforcement rules
  * Artifact: `papers/CORE-Infrastructure-Definition.md`

* **ServiceRegistry Constitutional Documentation**
  * Declared ServiceRegistry as infrastructure component
  * Documented authority limits and exemptions
  * Added mandatory audit logging
  * Implemented health check capability
  * Artifact: Updated `src/shared/infrastructure/service_registry.py`

* **Infrastructure Enforcement Mappings**
  * Created blocking rules for strategic decision prohibition
  * Added reporting rules for audit logging requirements
  * Implemented deterministic behavior enforcement
  * Artifact: `enforcement/mappings/infrastructure/authority_boundaries.yaml`

### Impact

* All components now have explicit constitutional status
* ServiceRegistry operates with constitutional visibility
* Infrastructure authority is bounded and auditable
* No component operates without governance oversight

### Roadmap

* Phase 2 (Month 1): Promote reporting rules to blocking
* Phase 3 (Month 2-3): Split ServiceRegistry into Bootstrap + Runtime
* Phase 4 (Quarter 1): Eliminate infrastructure exemption entirely
```

### Task 7.3: Git Commit

```bash
# Stage all changes
git add .intent/papers/CORE-Infrastructure-Definition.md
git add .intent/enforcement/mappings/infrastructure/
git add .intent/CHANGELOG.md
git add .intent/CORE-CHARTER.md
git add src/shared/infrastructure/service_registry.py
git add src/body/cli/commands/infrastructure.py
git add src/body/cli/admin_cli.py  # if you registered infrastructure commands
git add README.md  # if you updated it

# Commit with constitutional tag
git commit -m "constitutional(v0.2): Define infrastructure and bound ServiceRegistry authority

BREAKING CHANGE: ServiceRegistry now subject to constitutional governance

Added:
- Infrastructure constitutional category definition
- ServiceRegistry authority boundaries and audit logging
- Infrastructure enforcement rules
- Health check capability

Closes: Constitutional blind spot in architectural review

See: .intent/papers/CORE-Infrastructure-Definition.md
See: .intent/CHANGELOG.md v0.2"

# Tag the constitutional amendment
git tag -a v0.2-constitution -m "Constitutional Amendment: Infrastructure Definition"

# Push
git push origin main
git push origin v0.2-constitution
```

---

## Success Criteria Checklist

After Day 7, verify:

- [x] Paper exists in `.intent/papers/CORE-Infrastructure-Definition.md`
- [x] Enforcement rules exist in `.intent/enforcement/mappings/infrastructure/authority_boundaries.yaml`
- [x] ServiceRegistry has constitutional authority docstring
- [x] All ServiceRegistry operations log with "INFRASTRUCTURE:" marker
- [x] ServiceRegistry has `health_check()` method
- [x] Health check is accessible via CLI: `core-admin infrastructure health`
- [x] Constitutional audit passes with 0 blocking violations
- [x] Tests verify deterministic behavior
- [x] Documentation updated (README, CHANGELOG, CHARTER)
- [x] Git commit with constitutional tag

---

## What This Achieves

**Before:**
- ServiceRegistry = shadow government, ungovernanced, unacknowledged
- Constitutional claims hollow (governance blind spot)
- No path to validate infrastructure compliance

**After:**
- ServiceRegistry = explicitly defined infrastructure with bounded authority
- Constitutional coverage complete (no blind spots)
- Clear audit trail of all infrastructure operations
- Health monitoring for infrastructure components
- Path to eliminate infrastructure exemption (Phase 4 split)

**Bottom Line:**
You can now honestly claim "CORE has complete constitutional governance" in academic papers and production pitches.

---

## Next Steps (Beyond Week 1)

### Month 1: Harden Infrastructure Rules
- Promote `mandatory_audit_logging` to blocking enforcement
- Promote `constitutional_documentation` to blocking enforcement
- Promote `health_check_required` to blocking enforcement
- Run comprehensive audit, fix any violations

### Month 2-3: Plan ServiceRegistry Split
- Design BootstrapRegistry (ungovernanced, runs once)
- Design RuntimeServiceRegistry (Body layer, fully governed)
- Create migration plan with backward compatibility
- Write `.intent/papers/CORE-ServiceRegistry-Split.md`

### Quarter 1: Execute Split
- Implement split in feature branch
- Run full constitutional audit on split version
- Validate no behavioral regressions
- Deploy as v0.3 constitutional amendment
- **Result:** Infrastructure exemption reduced to ~50 lines of bootstrap code

---

**END OF IMPLEMENTATION GUIDE**

You now have a clear 7-day path to close the constitutional blind spot.

Day 1-2: Documentation (low risk)
Day 3-5: Implementation (medium risk)
Day 6-7: Verification (high value)

After Day 7: ServiceRegistry is constitutionally compliant.
After Month 3: Infrastructure exemption nearly eliminated.
After Quarter 1: Pure Mind/Body/Will architecture achieved.
