# src/body/services/access_register.py
"""The access register against reality (ADR-068 amendment 2026-10-15, rule 5).

The register in ``.intent/taxonomies/principal_roles.yaml`` names every
identity, the role it holds, the groups and sudo rules the roles need, and
who administers the host. Rule 5: any account, group, sudo rule or GitHub
collaborator not in the register is a blocking finding. This module compares
the register with what the host and GitHub actually grant, read-only:

- accounts: every login account and every ``core*`` account is a registered
  identity or a host administrator; every registered OS identity exists;
- groups: a registered identity belongs only to its own group and the groups
  the register gives it; a registered group has exactly its registered
  members;
- the governor binding (``/etc/core/principals.yaml``) binds exactly the
  register's Governor account;
- sudo rules naming a registered identity are the registered ones;
- governed text (``.intent``, ``.specs``, ``CLAUDE.md`` in the repository and
  in ``/opt/core/law``) is owned by the Custodian or root and writable by
  nobody else through group or other bits;
- GitHub collaborators are registered GitHub identities, the branch
  rulesets' bypass list holds nobody but the Governor and the bypasses the
  register grants (``github_grants.ruleset_bypass``), and the repository has
  exactly the registered number of write deploy keys
  (``github_grants.write_deploy_keys``): a DeployKey bypass names no single
  key, so a second write key would bypass too.

What cannot be read (sudoers as a non-root account, GitHub without a token
that can see collaborators) is reported as **not evaluated**, never as
passed.
"""

from __future__ import annotations

import grp
import pwd
import re
import stat
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


REGISTER_FILE = Path("taxonomies/principal_roles.yaml")
BINDING_FILE = Path("/etc/core/principals.yaml")
SUDOERS_FILES = (Path("/etc/sudoers"), Path("/etc/sudoers.d"))
LAW_ROOT = Path("/opt/core/law")
GOVERNED_NAMES = (".intent", ".specs", "CLAUDE.md")
GOVERNOR = "principal.governor"
CUSTODIAN = "principal.custodian"
LOGIN_SHELLS_EXCLUDED = ("/usr/sbin/nologin", "/sbin/nologin", "/bin/false")
# First uid of an ordinary (human) account on Debian and Ubuntu.
FIRST_LOGIN_UID = 1000
LAST_LOGIN_UID = 59999
_SUDO_RULE = re.compile(
    r"^(?P<who>\S+)\s+\S+\s*=\s*\((?P<as>[^)]*)\)\s*(?:\w+:\s*)*(?P<command>\S+)"
)


@dataclass(frozen=True)
# ID: a0d883f5-da2e-4565-a1a2-3e0774c3d628
class AccessFinding:
    """One difference between the register and reality (blocking, rule 5)."""

    subject: str
    message: str


@dataclass
# ID: ba3e37ce-8571-40ca-9b8e-0cb1c0b0cf95
class AccessReport:
    """Findings, and the checks that could not be performed."""

    findings: list[AccessFinding] = field(default_factory=list)
    not_evaluated: dict[str, str] = field(default_factory=dict)
    evaluated: list[str] = field(default_factory=list)

    # ID: ce9bfa52-a5aa-40d6-9ab4-289fa0701bc1
    def as_dict(self) -> dict[str, Any]:
        """JSON shape for the CLI and the sensor's report."""
        return {
            "findings": [f.__dict__ for f in self.findings],
            "not_evaluated": dict(self.not_evaluated),
            "evaluated": list(self.evaluated),
        }


@dataclass(frozen=True)
# ID: 84c2c04b-ae41-46da-8b76-776a443a7f78
class Register:
    """The parts of principal_roles.yaml this check reads."""

    os_accounts: dict[str, str]
    github_accounts: dict[str, str]
    host_admins: frozenset[str]
    groups: dict[str, frozenset[str]]
    sudo_rules: frozenset[tuple[str, str, str]]
    bypass_grants: frozenset[tuple[str, str, Any]] = frozenset()
    write_deploy_keys: int | None = None

    # ID: fa21671a-6562-4111-808a-02cfeab35905
    def account_for(self, role: str) -> list[str]:
        """The OS accounts bound to *role*."""
        return sorted(a for a, r in self.os_accounts.items() if r == role)


# ID: 5ae4e4da-3479-4cfe-9749-52aa154f2f5d
def load_register(intent_root: Path) -> Register:
    """Read the register from ``<intent_root>/taxonomies/principal_roles.yaml``."""
    data = yaml.safe_load((intent_root / REGISTER_FILE).read_text(encoding="utf-8"))
    identities = data.get("identities") or {}
    grants = data.get("host_grants") or {}
    github = data.get("github_grants") or {}
    return Register(
        os_accounts=dict(identities.get("os_accounts") or {}),
        github_accounts=dict(identities.get("github_accounts") or {}),
        host_admins=frozenset(
            (data.get("host_administration") or {}).get("os_accounts") or []
        ),
        groups={
            name: frozenset(spec.get("members") or [])
            for name, spec in (grants.get("groups") or {}).items()
        },
        sudo_rules=frozenset(
            (r["who"], r["as"], r["command"]) for r in grants.get("sudo_rules") or []
        ),
        bypass_grants=frozenset(
            (str(b["ruleset"]), str(b["actor_type"]), b.get("actor_id"))
            for b in github.get("ruleset_bypass") or []
        ),
        write_deploy_keys=(github.get("write_deploy_keys") or {}).get("count"),
    )


@dataclass(frozen=True)
# ID: 7fe9dc8c-3306-460c-917a-ec7aff2d2a09
class HostAccounts:
    """passwd and group, as plain data (tests build it by hand)."""

    shells: dict[str, str]
    uids: dict[str, int]
    primary_group: dict[str, str]
    members: dict[str, frozenset[str]]

    # ID: 670919fe-aabe-44b1-8cc8-827d62f3513e
    def groups_of(self, account: str) -> set[str]:
        """Supplementary groups of *account*, without its primary group."""
        return {g for g, m in self.members.items() if account in m}


# ID: a5bcc716-1e02-48e7-93a4-16ded56104e1
def read_host_accounts() -> HostAccounts:
    """The host's passwd and group databases."""
    gid_names = {g.gr_gid: g.gr_name for g in grp.getgrall()}
    users = pwd.getpwall()
    return HostAccounts(
        shells={u.pw_name: u.pw_shell for u in users},
        uids={u.pw_name: u.pw_uid for u in users},
        primary_group={u.pw_name: gid_names.get(u.pw_gid, "") for u in users},
        members={g.gr_name: frozenset(g.gr_mem) for g in grp.getgrall()},
    )


def _in_scope(name: str, uid: int, shell: str) -> bool:
    """A CORE account, or an account a person can log in to."""
    if name.startswith("core"):
        return True
    return (
        FIRST_LOGIN_UID <= uid <= LAST_LOGIN_UID and shell not in LOGIN_SHELLS_EXCLUDED
    )


# ID: ef455d82-65fd-48ac-9eb9-a5436eb694e1
def check_accounts(register: Register, host: HostAccounts) -> list[AccessFinding]:
    """Accounts outside the register, and registered accounts that are missing."""
    findings = []
    known = set(register.os_accounts) | register.host_admins
    for name, uid in sorted(host.uids.items()):
        if name in known or not _in_scope(name, uid, host.shells[name]):
            continue
        findings.append(
            AccessFinding(
                f"account::{name}",
                f"account {name} (uid {uid}) is not in the register",
            )
        )
    for name in sorted(set(register.os_accounts) - set(host.uids)):
        findings.append(
            AccessFinding(
                f"account::{name}",
                f"registered account {name} ({register.os_accounts[name]}) does not exist",
            )
        )
    return findings


# ID: 49c62a61-3aa7-43ea-9bf1-cc163e2bc665
def check_groups(register: Register, host: HostAccounts) -> list[AccessFinding]:
    """Group memberships the register does not grant, or does but are missing."""
    findings = []
    for account in sorted(register.os_accounts):
        if account not in host.uids:
            continue
        granted = {g for g, members in register.groups.items() if account in members}
        extra = host.groups_of(account) - granted - {host.primary_group[account]}
        for group in sorted(extra):
            findings.append(
                AccessFinding(
                    f"group::{group}::{account}",
                    f"{account} is a member of {group}, which the register does not grant",
                )
            )
    for group, wanted in sorted(register.groups.items()):
        actual = host.members.get(group)
        if actual is None:
            findings.append(
                AccessFinding(
                    f"group::{group}", f"registered group {group} does not exist"
                )
            )
            continue
        for account in sorted(wanted - actual):
            findings.append(
                AccessFinding(
                    f"group::{group}::{account}",
                    f"{account} is not in {group}, which the register grants it",
                )
            )
        for account in sorted(actual - wanted - set(register.os_accounts)):
            findings.append(
                AccessFinding(
                    f"group::{group}::{account}",
                    f"{account} is a member of {group}, which the register does not grant",
                )
            )
    return findings


# ID: c5ffa587-b3bd-4cd0-98d2-364a21ab4cda
def check_binding(register: Register, text: str) -> list[AccessFinding]:
    """The governor binding names exactly the register's Governor account."""
    try:
        data = yaml.safe_load(text) or {}
        bound = {
            str(a) for a, r in (data.get("principals") or {}).items() if r == GOVERNOR
        }
    except (yaml.YAMLError, AttributeError) as exc:
        return [AccessFinding("binding", f"{BINDING_FILE} is not valid: {exc}")]
    wanted = set(register.account_for(GOVERNOR))
    if bound == wanted:
        return []
    return [
        AccessFinding(
            "binding",
            f"{BINDING_FILE} binds {sorted(bound) or 'nobody'} to {GOVERNOR}; "
            f"the register names {sorted(wanted) or 'nobody'}",
        )
    ]


# ID: eb061337-366c-47b8-9dd2-5298c4981f28
def parse_sudo_rules(text: str) -> list[tuple[str, str, str]]:
    """(who, as, command) for each user rule; Defaults, aliases and comments skipped."""
    rules = []
    for raw in text.replace("\\\n", " ").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith(("Defaults", "@", "User_Alias", "Cmnd_Alias")):
            continue
        if line.startswith(("Host_Alias", "Runas_Alias")):
            continue
        match = _SUDO_RULE.match(line)
        if match:
            target = match["as"].split(":", 1)[0].strip() or "root"
            rules.append((match["who"], target, match["command"].rstrip(",")))
    return rules


# ID: 2a517b49-b8d2-499d-8c10-2ef125301969
def check_sudo_rules(
    register: Register, rules: Iterable[tuple[str, str, str]]
) -> list[AccessFinding]:
    """Sudo rules for a registered identity, or a %group, that the register lacks."""
    findings = []
    seen = set()
    for who, target, command in rules:
        if who in register.host_admins or (
            who.startswith("%") and who[1:] in ("sudo", "admin", "wheel")
        ):
            # Host administration: outside CORE (rule 6). Membership of these
            # groups by a registered identity is a group finding.
            continue
        if who.startswith("%"):
            if not (register.groups.get(who[1:]) or set()) & set(register.os_accounts):
                continue
        elif who not in register.os_accounts:
            continue
        rule = (who, target, command)
        seen.add(rule)
        if rule not in register.sudo_rules:
            findings.append(
                AccessFinding(
                    f"sudo::{who}::{target}::{command}",
                    f"sudo rule {who} -> ({target}) {command} is not in the register",
                )
            )
    for who, target, command in sorted(register.sudo_rules - seen):
        findings.append(
            AccessFinding(
                f"sudo::{who}::{target}::{command}",
                f"registered sudo rule {who} -> ({target}) {command} is not installed",
            )
        )
    return findings


# ID: 0fc8e9b2-5187-4cf2-a0a7-2574999e54cb
def read_sudo_rules(
    paths: Iterable[Path] = SUDOERS_FILES,
) -> list[tuple[str, str, str]]:
    """Every rule in sudoers and sudoers.d; raises OSError when unreadable."""
    rules = []
    for path in paths:
        files = (
            sorted(p for p in path.iterdir() if p.is_file())
            if path.is_dir()
            else [path]
        )
        for file in files:
            rules.extend(parse_sudo_rules(file.read_text(encoding="utf-8")))
    return rules


# ID: 3ce77c9e-eb68-45ab-be97-df93ddf8fe93
def check_governed_modes(
    register: Register, roots: Iterable[Path], host: HostAccounts
) -> list[AccessFinding]:
    """Governed text owned by the Custodian or root, with no group/other write."""
    owners = {"root", *register.account_for(CUSTODIAN)}
    names = {uid: name for name, uid in host.uids.items()}
    findings = []
    for root in roots:
        for name in GOVERNED_NAMES:
            top = root / name
            if not top.exists():
                continue
            paths = [top, *top.rglob("*")] if top.is_dir() else [top]
            for path in paths:
                info = path.lstat()
                owner = names.get(info.st_uid, str(info.st_uid))
                writable = info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
                if owner in owners and not writable:
                    continue
                findings.append(
                    AccessFinding(
                        f"governed::{path}",
                        f"{path} is owned by {owner}, mode "
                        f"{stat.S_IMODE(info.st_mode):o}: only the Custodian or root "
                        "may own governed text, and nobody else may write it",
                    )
                )
    return findings


# ID: 061f3251-07d3-414c-83e1-b2e3d50411b0
def check_github(
    register: Register,
    collaborators: list[dict[str, Any]],
) -> list[AccessFinding]:
    """Repository collaborators that are not registered GitHub identities."""
    findings = []
    logins = set()
    for person in collaborators:
        login = str(person.get("login") or "")
        logins.add(login)
        if login not in register.github_accounts:
            role = person.get("role_name") or "unknown"
            findings.append(
                AccessFinding(
                    f"github::collaborator::{login}",
                    f"GitHub collaborator {login} ({role}) is not in the register",
                )
            )
    for login in sorted(set(register.github_accounts) - logins):
        findings.append(
            AccessFinding(
                f"github::collaborator::{login}",
                f"registered GitHub account {login} is not a collaborator",
            )
        )
    return findings


# ID: 97f629a3-1dc7-4e11-a73f-7993faadc198
def check_bypass(
    register: Register, rulesets: list[dict[str, Any]]
) -> tuple[list[AccessFinding], list[str]]:
    """Ruleset bypass actors other than the Governor; and rulesets not readable."""
    findings = []
    unreadable = []
    governors = {
        login for login, role in register.github_accounts.items() if role == GOVERNOR
    }
    for ruleset in rulesets:
        name = str(ruleset.get("name") or ruleset.get("id"))
        actors = ruleset.get("bypass_actors")
        if actors is None:
            unreadable.append(name)
            continue
        for actor in actors:
            kind = actor.get("actor_type")
            # The repository admin role (id 5) is held by the Governor alone.
            if kind == "RepositoryRole" and governors and actor.get("actor_id") == 5:
                continue
            if (name, kind, actor.get("actor_id")) in register.bypass_grants:
                continue
            findings.append(
                AccessFinding(
                    f"github::bypass::{name}::{kind}:{actor.get('actor_id')}",
                    f"ruleset {name} lets {kind} {actor.get('actor_id')} bypass it; "
                    "the register allows no bypass but the Governor's",
                )
            )
    return findings, unreadable


# ID: 2bd200d0-07c4-40f2-8c6c-95aa7648360c
def check_deploy_keys(
    register: Register, keys: list[dict[str, Any]]
) -> list[AccessFinding]:
    """The repository's write deploy keys against the registered count. A
    DeployKey bypass names no single key, so a second write key would move
    ``live`` too."""
    if register.write_deploy_keys is None:
        return []
    writable = [k for k in keys if not k.get("read_only", True)]
    if len(writable) == register.write_deploy_keys:
        return []
    titles = ", ".join(str(k.get("title") or k.get("id")) for k in writable) or "none"
    return [
        AccessFinding(
            "github::write_deploy_keys",
            f"the repository has {len(writable)} write deploy key(s) ({titles}); "
            f"the register allows {register.write_deploy_keys}",
        )
    ]


# ID: cb49619e-e5c4-4210-a563-faadc7b7ad69
def check_host(
    register: Register,
    *,
    repo_root: Path,
    host: HostAccounts | None = None,
    binding_file: Path = BINDING_FILE,
    sudoers: Iterable[Path] = SUDOERS_FILES,
    law_root: Path = LAW_ROOT,
) -> AccessReport:
    """Everything the register says about this host, read-only."""
    report = AccessReport()
    host = host or read_host_accounts()
    report.findings += check_accounts(register, host)
    report.findings += check_groups(register, host)
    report.evaluated += ["accounts", "groups"]
    try:
        report.findings += check_binding(register, binding_file.read_text())
        report.evaluated.append("binding")
    except FileNotFoundError:
        report.findings.append(AccessFinding("binding", f"{binding_file} is missing"))
        report.evaluated.append("binding")
    except OSError as exc:
        report.not_evaluated["binding"] = f"{binding_file} unreadable: {exc}"
    try:
        report.findings += check_sudo_rules(register, read_sudo_rules(sudoers))
        report.evaluated.append("sudo rules")
    except OSError as exc:
        report.not_evaluated["sudo rules"] = (
            f"sudoers unreadable by this account ({exc.strerror or exc}); run the "
            "check as root to evaluate them"
        )
    roots = [repo_root, *([law_root] if law_root.is_dir() else [])]
    try:
        report.findings += check_governed_modes(register, roots, host)
        report.evaluated.append("governed text")
    except OSError as exc:
        report.not_evaluated["governed text"] = f"unreadable: {exc}"
    return report


# ID: 731b2e08-6737-4f84-ba03-5254a78e838a
async def check_github_access(register: Register, report: AccessReport) -> None:
    """Add the GitHub checks to *report*; what cannot be read is not evaluated."""
    import httpx

    from body.infrastructure.thesis_config import thesis_config
    from body.services.thesis.github import GitHub, GitHubUnavailable

    config = thesis_config()
    if not config.token:
        report.not_evaluated["github"] = "no CORE_GITHUB_TOKEN"
        return
    async with httpx.AsyncClient() as client:
        github = GitHub(config.repo, config.token, client)
        try:
            people = await github.get_pages(
                "collaborators?affiliation=all&per_page=100"
            )
            report.findings += check_github(register, people)
            report.evaluated.append("github collaborators")
        except GitHubUnavailable as exc:
            report.not_evaluated["github collaborators"] = str(exc)
        try:
            listed = await github.get_pages("rulesets?per_page=100")
            rulesets = [await github.get(f"rulesets/{r['id']}") for r in listed]
            found, unreadable = check_bypass(register, rulesets)
            report.findings += found
            if unreadable:
                report.not_evaluated["ruleset bypass list"] = (
                    "hidden from this token (needs admin): " + ", ".join(unreadable)
                )
            else:
                report.evaluated.append("ruleset bypass list")
        except GitHubUnavailable as exc:
            report.not_evaluated["ruleset bypass list"] = str(exc)
        try:
            keys = await github.get_pages("keys?per_page=100")
            report.findings += check_deploy_keys(register, keys)
            report.evaluated.append("write deploy keys")
        except GitHubUnavailable as exc:
            report.not_evaluated["write deploy keys"] = (
                f"needs a token with administration read: {exc}"
            )
