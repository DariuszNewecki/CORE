# Phase 1 Installation Checklist
# Vector Service Standardization - Day 1-4
# Generated: 2025-12-06

## Overview
This checklist guides you through installing Phase 1 updates for vector service standardization.

**Goal**: Replace direct Qdrant client access with service methods and add hash support.

**Files to update**: 3 files
**Estimated time**: 10-15 minutes
**Risk level**: Low (backward compatible)

---

## Pre-Installation Checks

- [ ] **Backup current state**
  ```bash
  cd /opt/dev/CORE
  git status  # Ensure clean working directory
  git checkout -b phase-1-vector-standardization
  ```

- [ ] **Verify test passes**
  ```bash
  poetry run python tests/services/test_qdrant_new_methods.py
  ```
  Expected: All 4 methods pass ✓

- [ ] **Check current hash coverage**
  Note the percentage shown in test output for comparison later.

---

## Step 1: Update QdrantService (5 min)

**File**: `src/services/clients/qdrant_client.py`

- [ ] **Backup original**
  ```bash
  cp src/services/clients/qdrant_client.py src/services/clients/qdrant_client.py.backup
  ```

- [ ] **Install updated version**
  ```bash
  cp qdrant_client.py src/services/clients/
  ```

- [ ] **Verify no syntax errors**
  ```bash
  poetry run python -m py_compile src/services/clients/qdrant_client.py
  ```
  Expected: No output = success

- [ ] **Quick verification**
  ```bash
  poetry run python -c "from services.clients.qdrant_client import QdrantService; print('✓ Import successful')"
  ```

---

## Step 2: Update PatternVectorizer (3 min)

**File**: `src/features/introspection/pattern_vectorizer.py`

- [ ] **Backup original**
  ```bash
  cp src/features/introspection/pattern_vectorizer.py src/features/introspection/pattern_vectorizer.py.backup
  ```

- [ ] **Install updated version**
  ```bash
  cp pattern_vectorizer.py src/features/introspection/
  ```

- [ ] **Verify no syntax errors**
  ```bash
  poetry run python -m py_compile src/features/introspection/pattern_vectorizer.py
  ```

- [ ] **Quick verification**
  ```bash
  poetry run python -c "from features.introspection.pattern_vectorizer import PatternVectorizer; print('✓ Import successful')"
  ```

---

## Step 3: Update PolicyVectorizer (3 min)

**File**: `src/will/tools/policy_vectorizer.py`

- [ ] **Backup original**
  ```bash
  cp src/will/tools/policy_vectorizer.py src/will/tools/policy_vectorizer.py.backup
  ```

- [ ] **Install updated version**
  ```bash
  cp policy_vectorizer.py src/will/tools/
  ```

- [ ] **Verify no syntax errors**
  ```bash
  poetry run python -m py_compile src/will/tools/policy_vectorizer.py
  ```

- [ ] **Quick verification**
  ```bash
  poetry run python -c "from will.tools.policy_vectorizer import PolicyVectorizer; print('✓ Import successful')"
  ```

---

## Step 4: Run Tests (5 min)

- [ ] **Test QdrantService methods**
  ```bash
  poetry run python tests/services/test_qdrant_new_methods.py
  ```
  Expected: All 4 methods pass ✓

- [ ] **Test existing test suite**
  ```bash
  poetry run pytest tests/services/test_qdrant_new_methods.py -v
  ```
  Expected: Pass (or skip if not pytest-based)

- [ ] **Quick smoke test - Pattern vectorization**
  ```bash
  # This should work without errors (may take a minute)
  poetry run python -c "
  import asyncio
  from pathlib import Path
  from services.clients.qdrant_client import QdrantService
  from will.orchestration.cognitive_service import CognitiveService
  from features.introspection.pattern_vectorizer import PatternVectorizer

  async def test():
      qdrant = QdrantService()
      cognitive = CognitiveService(repo_path=Path.cwd(), qdrant_service=qdrant)
      await cognitive.initialize()

      vectorizer = PatternVectorizer(
          qdrant_service=qdrant,
          cognitive_service=cognitive,
      )

      print('✓ PatternVectorizer initialized successfully')

  asyncio.run(test())
  "
  ```

- [ ] **Quick smoke test - Policy vectorization**
  ```bash
  # This should work without errors (may take a minute)
  poetry run python -c "
  import asyncio
  from pathlib import Path
  from services.clients.qdrant_client import QdrantService
  from will.orchestration.cognitive_service import CognitiveService
  from will.tools.policy_vectorizer import PolicyVectorizer

  async def test():
      qdrant = QdrantService()
      cognitive = CognitiveService(repo_path=Path.cwd(), qdrant_service=qdrant)
      await cognitive.initialize()

      vectorizer = PolicyVectorizer(
          repo_root=Path.cwd(),
          cognitive_service=cognitive,
          qdrant_service=qdrant,
      )

      print('✓ PolicyVectorizer initialized successfully')

  asyncio.run(test())
  "
  ```

---

## Step 5: Verify Hash Coverage (2 min)

- [ ] **Check hash coverage again**
  ```bash
  poetry run python tests/services/test_qdrant_new_methods.py | grep "Hash coverage"
  ```
  Expected: Should still be 100.0% (no change yet, Phase 2 will improve this)

- [ ] **Verify hashes are being added**
  You can manually inspect a few vectors to confirm `content_sha256` exists:
  ```bash
  poetry run python -c "
  import asyncio
  from services.clients.qdrant_client import QdrantService

  async def check():
      qdrant = QdrantService()
      points = await qdrant.scroll_all_points(with_payload=True, with_vectors=False)

      if points:
          sample = points[0]
          has_hash = 'content_sha256' in (sample.payload or {})
          print(f'Sample point has content_sha256: {has_hash}')
          if has_hash:
              print(f'Hash value: {sample.payload[\"content_sha256\"][:16]}...')
      else:
          print('No points in collection')

  asyncio.run(check())
  "
  ```

---

## Step 6: Commit Changes (2 min)

- [ ] **Review changes**
  ```bash
  git status
  git diff src/services/clients/qdrant_client.py
  git diff src/features/introspection/pattern_vectorizer.py
  git diff src/will/tools/policy_vectorizer.py
  ```

- [ ] **Commit Phase 1 updates**
  ```bash
  git add src/services/clients/qdrant_client.py
  git add src/features/introspection/pattern_vectorizer.py
  git add src/will/tools/policy_vectorizer.py
  git add tests/services/test_qdrant_new_methods.py

  git commit -m "Phase 1: Vector service standardization

  - Add 4 helper methods to QdrantService:
    - scroll_all_points() for paginated scanning
    - get_point_by_id() for single point retrieval
    - delete_points() for bulk deletion
    - get_stored_hashes() for deduplication support

  - Update PatternVectorizer:
    - Use service methods instead of direct client access
    - Add content_sha256 to all payloads
    - Prepare for Phase 2 deduplication

  - Update PolicyVectorizer:
    - Use service methods instead of direct client access
    - Add content_sha256 to all payloads
    - Prepare for Phase 2 deduplication

  - Add comprehensive test suite for new methods

  Refs: vector_service_standards.yaml"
  ```

---

## Rollback Plan (if needed)

If anything goes wrong, restore from backups:

```bash
# Restore QdrantService
cp src/services/clients/qdrant_client.py.backup src/services/clients/qdrant_client.py

# Restore PatternVectorizer
cp src/features/introspection/pattern_vectorizer.py.backup src/features/introspection/pattern_vectorizer.py

# Restore PolicyVectorizer
cp src/will/tools/policy_vectorizer.py.backup src/will/tools/policy_vectorizer.py

# Verify
poetry run python tests/services/test_qdrant_new_methods.py
```

---

## Success Criteria

✅ All checkboxes completed
✅ All tests pass
✅ No import errors
✅ Hash coverage maintained at 100%
✅ Changes committed to git

---

## What's Next?

**Phase 2** (Optional - Full Hash Deduplication):
- Implement actual hash checking before embedding
- Skip re-vectorization when content unchanged
- Reduce embedding API costs by 60%+

**Current State After Phase 1**:
- ✅ Service methods available and tested
- ✅ All new vectors include hashes
- ✅ Ready for Phase 2 deduplication
- ✅ Constitutional audit check ready to install

---

## Troubleshooting

### "Import failed" errors
- Check Python path: `echo $PYTHONPATH`
- Try: `poetry run python` instead of just `python`
- Verify virtual env: `poetry env info`

### "Collection not found" errors
- Run: `poetry run python tests/services/test_qdrant_new_methods.py`
- This will create the collection if missing

### "Qdrant connection failed"
- Check Qdrant is running: `curl http://192.168.20.22:6333/collections`
- Verify QDRANT_URL in .env matches your setup

### Tests fail after update
1. Check syntax: `poetry run python -m py_compile <file>`
2. Check imports work individually
3. Run test in verbose mode to see detailed error
4. If stuck, use rollback plan above

---

## Questions?

- Review the implementation plan: `vector_standardization_plan.md`
- Review the policy: `vector_service_standards.yaml`
- Check existing code for examples
- The test script shows usage of all new methods

---

## Completion Time

Started: __________
Completed: __________
Duration: __________

Notes:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
