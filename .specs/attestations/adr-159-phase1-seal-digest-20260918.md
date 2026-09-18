# ADR-159 Phase-1 Seal — Digest Attestation (2026-09-18)

**Status:** Custody record. Filed under `.specs/attestations/` per ADR-159 D9 and the Trial 0
Apparatus Design §7 as amended by the ADR-159 Note of 2026-09-18 (seal recovery ruling). This
file attests the **digest, size, timestamp and provenance** of the Phase-1 seal. It does not
contain the seal, any of its rows, or the name or content of the benchmark it was derived from.
The seal itself remains outside the CORE host, outside Git and outside every published evidence
bundle, by ruling.

**Ruling reference:** `.specs/decisions/ADR-159-autonomy-thesis-acceptance-boundary.md`, Note
*2026-09-18 — Governor ruling: recovered Phase-1 seal accepted as authoritative for Trial 0*.

---

## 1. Attested artefacts

| file | SHA-256 | size | mtime |
|---|---|---|---|
| `phase1-benchmark-SEALED.json` | `71835d8b7e905ff8cb1d899b51b6996e2d57f24e01331898de6268c0775d4dd4` | 9421 bytes | 2026-08-27 21:38:31 +02:00 (19:38:31Z) |
| `seal_manifest.py` | `a4d5b6d3ac7b9afedc6db9651cc7491851b8583049819f66115ffc4a64a68d7e` | 13061 bytes | 2026-08-27 21:38:26 +02:00 (19:38:26Z) |

Both files sit in the recovered `work/external-validation/` directory of the pre-rebuild CORE
working tree. Anyone holding a candidate copy verifies it by recomputing SHA-256 and comparing to
the values above; a match with the recorded size is the integrity check D9 requires.

## 2. Provenance

- **Recovery date:** 2026-09-16.
- **Recovery source:** the read-only VM-100 backup of 2026-08-30 (`vzdump-qemu-100-2026_08_30-19_25_47.vma.zst`),
  the last backup of that VM that completed with data. The archive was extracted read-only; the
  original was not modified.
- **Custody:** two byte-identical copies under separate custody — one on the Governor
  workstation, one on the Proxmox recovery host. Both must remain unchanged. Neither is on the
  CORE host, in Git, or in any path the Trial 0 runner can reach.
- **Recovery manifest:** the recovery produced a per-file SHA-256 manifest of the whole extracted
  working tree (4,647 entries; manifest file sha256
  `b2270d09ca866a4e8ddefa87436cc6716ee6f93d6e75b090148915d68c9405b8`). On 2026-09-18 it was
  re-verified against both copies: **4,647 OK, 0 failures** on each.

## 3. Limitation (must be disclosed by Trial 0)

Approximately 71 hours separate the sealing event (seal mtime 2026-08-27 21:38 +02:00) from the
backup that preserved it (2026-08-30 19:25 +02:00). No externally recorded digest of the seal
exists from inside that interval. Provenance is therefore strong — a read-only backup taken by an
unattended job, extracted without modification, verified file-by-file — but **cryptographic
continuity to the exact moment of sealing cannot be proven**. Trial 0 must disclose this
limitation and may not claim stronger historical authenticity than this record supports.

## 4. Verification record

| item | value |
|---|---|
| Verification date | 2026-09-18 |
| Verifier | Claude Code session (Opus 5) acting under the Governor's operator grant — custodial role only, excluded from every scoring role (Apparatus Design §6 pt 6) |
| Method | `sha256sum` / `shasum -a 256` and `stat` on both copies; `sha256sum -c` of the recovery manifest on both copies; no file content opened, parsed, printed or copied |
| Result | both copies byte-identical (all four digests, sizes and timestamps equal); manifest 4,647/4,647 OK on both |
| Accepted by | Governor ruling, ADR-159 Note 2026-09-18 |

## 5. What this record does not do

It does not publish the seal. It does not expand Trial 0's authorized scope. It does not
certify Trial 0 evidence — that follows the custody procedure at the external Trial 0 staging root
and lands under this directory in its own commit when the Governor certifies it.
