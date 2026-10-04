# src/shared/infrastructure/principal_binding.py
"""
Principal binding loader: OS account -> principal role (ADR-068 Layer 2).

ADR-132 D10.2: for a local caller, the binding from OS account to principal
role lives in a deployment file outside the repository
(``/etc/core/principals.yaml``), owned by root and not writable by the
services account or the coding assistant. A binding the assistant could
edit would bind nothing, so the file's custody is checked here, not
assumed.

Fail-closed by design: a missing, unreadable, malformed or badly-owned file
yields an empty binding carrying the reason. Nobody is ``principal.governor``
under an empty binding. The loader never raises and never falls back to a
permissive default.

File shape::

    principals:
      core-darek: principal.governor

Keys are OS account names, resolved to uids at load time. ADR-068: at most
one account is bound to ``principal.governor``.
"""

from __future__ import annotations

import pwd
import stat
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from shared.logger import getLogger


logger = getLogger(__name__)

PRINCIPAL_BINDING_PATH = Path("/etc/core/principals.yaml")
GOVERNOR = "principal.governor"


@dataclass(frozen=True)
# ID: a403e5de-b662-4cda-933a-dcf23ca694d4
class PrincipalBinding:
    """uid -> principal role, or empty with the reason it is empty."""

    roles_by_uid: dict[int, str] = field(default_factory=dict)
    accounts_by_uid: dict[int, str] = field(default_factory=dict)
    error: str | None = None

    # ID: 875e0c60-78bc-487c-9d27-3269174c53c5
    def role_for(self, uid: int) -> str | None:
        """The principal role bound to *uid*, or None."""
        return self.roles_by_uid.get(uid)


def _refuse(reason: str) -> PrincipalBinding:
    logger.warning("Principal binding unavailable (fail closed): %s", reason)
    return PrincipalBinding(error=reason)


def _custody_problem(path: Path, trusted_owner_uid: int) -> str | None:
    """Why *path* (or its directory) is not trustworthy custody, or None."""
    for target in (path, path.parent):
        st = target.stat()
        if st.st_uid != trusted_owner_uid:
            return f"{target} is owned by uid {st.st_uid}, not {trusted_owner_uid}"
        if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            return f"{target} is writable by group or others"
    return None


# ID: 2796b734-192b-4a75-896c-fa2270829ea4
def load_principal_binding(
    path: Path = PRINCIPAL_BINDING_PATH,
    *,
    trusted_owner_uid: int = 0,
) -> PrincipalBinding:
    """Load the binding at *path*; on any problem return an empty binding.

    *trusted_owner_uid* is the only owner accepted for the file and its
    directory: root in deployment. Tests pass their own uid.
    """
    try:
        if not path.is_file():
            return _refuse(f"{path} does not exist")
        problem = _custody_problem(path, trusted_owner_uid)
        if problem:
            return _refuse(problem)
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return _refuse(f"cannot read {path}: {exc}")

    if not isinstance(document, dict) or not isinstance(
        document.get("principals"), dict
    ):
        return _refuse(f"{path}: expected a top-level 'principals:' mapping")

    roles_by_uid: dict[int, str] = {}
    accounts_by_uid: dict[int, str] = {}
    for account, role in document["principals"].items():
        if not isinstance(account, str) or not isinstance(role, str):
            return _refuse(f"{path}: entries must be 'account: principal.<role>'")
        if not role.startswith("principal."):
            return _refuse(f"{path}: {account!r} has non-principal role {role!r}")
        try:
            uid = pwd.getpwnam(account).pw_uid
        except KeyError:
            return _refuse(f"{path}: no OS account named {account!r}")
        roles_by_uid[uid] = role
        accounts_by_uid[uid] = account

    governors = [uid for uid, role in roles_by_uid.items() if role == GOVERNOR]
    if len(governors) > 1:
        return _refuse(f"{path}: more than one account bound to {GOVERNOR}")

    return PrincipalBinding(roles_by_uid=roles_by_uid, accounts_by_uid=accounts_by_uid)
