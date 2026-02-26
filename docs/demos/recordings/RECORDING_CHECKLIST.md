# Recording Checklist
1. [ ] Clear terminal (Ctrl+L)
2. [ ] Ensure DB is up (docker compose up -d)
3. [ ] Verify current model: 'core-admin inspect status' (or custom query)
4. [ ] Run failing test first to prove it fails: 'pytest tests/target_test.py'
5. [ ] Start recording: 'asciinema rec demos/v2.0.0/battle_round_X_model_Y.cast'
