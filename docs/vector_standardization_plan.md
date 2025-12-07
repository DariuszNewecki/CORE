# Vector Service Standardization Plan
# Generated: 2025-12-06
# Context: Discovered inconsistent Qdrant interaction patterns across CORE

## Overview

This plan standardizes all Qdrant vector database interactions across CORE
following the new vector_service_standards.yaml constitutional policy.

**Current violations:**
- `pattern_vectorizer`: No hash checking, direct client access
- `policy_vectorizer`: No hash tracking, raw dict payloads
- Multiple scroll implementations without proper pagination
- No constitutional audit check keeping us honest

**Timeline:** 3 weeks (1 week per phase)

---

## Phase 1: Service Method Standardization (Week 1)

**Goal:** All Qdrant operations go through QdrantService methods

### Tasks

1. **Audit Current Usage** (Day 1)
   ```bash
   # Find all direct client access
   grep -r "\.client\." src/ | grep qdrant

   # Document each usage and required service method
   ```

2. **Add Missing Service Methods** (Day 1-2)
   - Review what methods vectorizers need
   - Add to QdrantService if missing:
     - `scroll_all_points()` - paginated scroll helper
     - `get_point_by_id()` - single point retrieval
     - `delete_points()` - bulk deletion with validation

3. **Update Symbol Vectorizer** (Day 2)
   - Already mostly compliant
   - Verify all `.client.` calls go through service

4. **Update Pattern Vectorizer** (Day 3)
   - Replace `self.qdrant.client.scroll()` with service method
   - Replace `self.qdrant.client.upsert()` with service method
   - Replace `self.qdrant.client.recreate_collection()` with service method

5. **Update Policy Vectorizer** (Day 4)
   - Same changes as pattern vectorizer
   - Ensure consistent error handling

6. **Enable Audit Check** (Day 5)
   - Add `vector_service_standards_check.py` to governance/checks/
   - Run `core-admin check audit` and verify it catches violations
   - Fix any violations found

### Success Criteria
- ✅ Zero direct `.client.` access outside QdrantService
- ✅ Constitutional audit check passes
- ✅ All vectorizers use service methods

---

## Phase 2: Hash-Based Deduplication (Week 2)

**Goal:** All vectorization checks hashes before embedding

### Tasks

1. **Add Hash Utilities** (Day 1)
   - Create `shared/utils/hash_utils.py` with:
     - `compute_content_hash(text: str) -> str`
     - `normalize_for_hashing(text: str) -> str`
   - Use in symbol_vectorizer as reference

2. **Update Pattern Vectorizer** (Day 2-3)
   ```python
   # Before vectorizing:
   normalized = normalize_for_hashing(pattern_content)
   content_hash = compute_content_hash(normalized)

   # Check if exists with same hash:
   existing_hash = await self._get_stored_hash(pattern_id)
   if existing_hash == content_hash:
       logger.debug(f"Skipping {pattern_id}, hash matches")
       return None  # Already current

   # Vectorize and store with hash:
   vector = await embed(normalized)
   await upsert(vector, {
       "content_sha256": content_hash,
       ...
   })
   ```

3. **Update Policy Vectorizer** (Day 3-4)
   - Same pattern as pattern vectorizer
   - Ensure chunk-level hashing (not document-level)

4. **Add Hash Retrieval Methods** (Day 4)
   - Add to QdrantService:
     - `get_stored_hashes() -> dict[str, str]`
     - Returns mapping of point_id -> content_sha256
   - Use scroll with `with_payload=["content_sha256"]`

5. **Test Deduplication** (Day 5)
   ```bash
   # Run vectorization twice, second should skip all
   core-admin manage vectors sync patterns
   core-admin manage vectors sync patterns  # Should skip everything

   # Verify in logs: "Skipping X items, hash matches"
   ```

### Success Criteria
- ✅ All vectors have `content_sha256` in payload
- ✅ Re-running vectorization skips unchanged content
- ✅ Hash coverage check passes in audit
- ✅ Embedding API costs reduced by 60%+

---

## Phase 3: Typed Payload Schemas (Week 3)

**Goal:** All payloads use typed classes, no raw dicts

### Tasks

1. **Define Payload Classes** (Day 1)
   Create `shared/models/vector_payloads.py`:
   ```python
   @dataclass
   class PatternVectorPayload:
       content_sha256: str
       model: str
       model_rev: str
       dim: int
       created_at: str
       # Pattern-specific
       pattern_id: str
       pattern_version: str
       section_type: str
       section_path: str

       def to_dict(self) -> dict:
           return asdict(self)

   @dataclass
   class PolicyVectorPayload:
       # Similar structure...
   ```

2. **Update Pattern Vectorizer** (Day 2)
   - Replace raw dicts with PatternVectorPayload
   - Add validation in payload creation
   - Update tests

3. **Update Policy Vectorizer** (Day 3)
   - Replace raw dicts with PolicyVectorPayload
   - Ensure consistent with pattern approach

4. **Add Payload Validation** (Day 4)
   - QdrantService validates payload has required fields
   - Raises InvalidPayloadError if missing mandatory fields
   - Type checker catches missing fields at dev time

5. **Update Tests** (Day 5)
   - Test typed payloads
   - Test validation catches bad payloads
   - Test round-trip serialization

### Success Criteria
- ✅ Zero raw dict payloads in vectorizers
- ✅ Type checker passes (mypy/pyright)
- ✅ Runtime validation catches malformed payloads
- ✅ All tests pass

---

## Rollout Strategy

### Development Environment
1. Implement changes behind feature flag initially
2. Test thoroughly in dev environment
3. Run full audit suite to catch issues

### Testing
```bash
# After each phase:
make test
make lint
core-admin check audit

# Verify vectorization:
core-admin manage vectors sync all --dry-run
core-admin manage vectors sync all
core-admin manage vectors verify
```

### Monitoring
Track these metrics through rollout:
- Direct client access violations (target: 0)
- Hash coverage percentage (target: 100%)
- Orphaned vectors (target: 0)
- Dangling links (target: 0)
- Embedding API calls saved (target: 60%+ reduction)

---

## Risk Mitigation

### Backward Compatibility
- Existing vectors remain valid
- New code reads old payloads gracefully
- Migration is additive (add hash field to existing vectors)

### Rollback Plan
- Each phase is independently reversible
- Git branches per phase for easy rollback
- Database changes are non-destructive

### Communication
- Update CHANGELOG.md after each phase
- Document breaking changes (none expected)
- Update README with new CLI commands

---

## Post-Implementation

### Documentation Updates
1. Update `.intent/charter/policies/vector_service_standards.yaml`
   - Mark migration phases as complete
   - Update status from "foundational" to "enforced"

2. Add to developer guide:
   - "How to Add a New Vectorizer"
   - Reference implementations (symbol_vectorizer)
   - Required patterns (hash checking, service methods, typed payloads)

### Continuous Enforcement
```bash
# Add to CI pipeline:
core-admin check audit  # Catches direct client access

# Add to weekly cron:
core-admin manage vectors verify  # Checks integrity
```

### Future Enhancements
- Auto-remediation: Detect orphaned vectors and auto-cleanup
- Metrics dashboard: Vector count, hash coverage, sync health
- Performance monitoring: Track embedding costs saved via deduplication

---

## Success Metrics

**Technical:**
- ✅ 100% hash coverage across all collections
- ✅ 0 direct client access violations
- ✅ 0 orphaned vectors
- ✅ 0 dangling links
- ✅ All tests passing

**Operational:**
- ✅ 60%+ reduction in embedding API costs
- ✅ Vectorization runs 3x faster (skip unchanged)
- ✅ Constitutional audit passes with zero findings

**Maintainability:**
- ✅ New developers follow standard patterns
- ✅ Code reviews catch violations early
- ✅ Documentation is authoritative

---

## Estimated Effort

- **Phase 1 (Service Methods):** 5 days
- **Phase 2 (Hash Deduplication):** 5 days
- **Phase 3 (Typed Payloads):** 5 days
- **Testing & Documentation:** Continuous
- **Buffer:** 3 days for unexpected issues

**Total:** ~18 development days (3.6 weeks @ 5 days/week)

---

## Next Steps

1. Review this plan with stakeholders
2. Create tracking issue/epic in project management
3. Begin Phase 1 implementation
4. Schedule daily standups during implementation
5. Document lessons learned after each phase

**Start Date:** TBD
**Target Completion:** TBD + 3 weeks
