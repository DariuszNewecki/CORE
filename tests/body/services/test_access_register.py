"""The access register against reality (ADR-068 amendment 2026-10-15, rule 5)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from body.services.access_register import (
    HostAccounts,
    check_accounts,
    check_binding,
    check_bypass,
    check_github,
    check_governed_modes,
    check_groups,
    check_host,
    check_sudo_rules,
    load_register,
    parse_sudo_rules,
)


REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def register():
    return load_register(REPO / ".intent")


def _host(**overrides) -> HostAccounts:
    accounts = {
        "root": (0, "/bin/bash", "root"),
        "core-darek": (1002, "/bin/bash", "core-darek"),
        "darek": (1004, "/bin/bash", "darek"),
        "core-claude": (1001, "/bin/bash", "core-claude"),
        "core": (1000, "/bin/bash", "core"),
        "core-law": (995, "/usr/sbin/nologin", "core-law"),
        "core-runner": (992, "/usr/sbin/nologin", "core-runner"),
        "core-build": (994, "/usr/sbin/nologin", "core-build"),
        "core-sandbox": (993, "/usr/sbin/nologin", "core-sandbox"),
        "syslog": (104, "/usr/sbin/nologin", "syslog"),
    }
    members = {
        "core-gov": frozenset({"core-darek"}),
        "core-dev": frozenset({"core", "core-darek", "core-claude"}),
        "core-producer": frozenset({"core-claude"}),
        "sudo": frozenset({"darek"}),
    }
    members.update(overrides.pop("members", {}))
    accounts.update(overrides.pop("accounts", {}))
    return HostAccounts(
        shells={n: a[1] for n, a in accounts.items()},
        uids={n: a[0] for n, a in accounts.items()},
        primary_group={n: a[2] for n, a in accounts.items()},
        members=members,
    )


def test_the_register_is_the_governors_proposal(register) -> None:
    assert register.os_accounts["core-darek"] == "principal.governor"
    assert register.account_for("principal.governor") == ["core-darek"]
    assert register.github_accounts == {
        "DariuszNewecki": "principal.governor",
        "core-claude-bot": "principal.producer",
        "erykpiotrov": "principal.producer",
    }
    assert register.host_admins == {"darek", "root"}


def test_a_host_matching_the_register_has_no_findings(register) -> None:
    host = _host()
    assert check_accounts(register, host) == []
    assert check_groups(register, host) == []


def test_an_unregistered_login_account_is_a_finding(register) -> None:
    host = _host(accounts={"eve": (1010, "/bin/bash", "eve")})
    assert [f.subject for f in check_accounts(register, host)] == ["account::eve"]


def test_a_missing_registered_account_is_a_finding(register) -> None:
    host = _host()
    del host.uids["core-runner"]
    assert [f.subject for f in check_accounts(register, host)] == [
        "account::core-runner"
    ]


def test_an_ungranted_group_of_a_registered_identity_is_a_finding(register) -> None:
    host = _host(members={"adm": frozenset({"core-claude"}), "docker": frozenset()})
    assert [f.subject for f in check_groups(register, host)] == [
        "group::adm::core-claude"
    ]


def test_the_governor_group_must_hold_exactly_the_governor(register) -> None:
    host = _host(members={"core-gov": frozenset({"darek"})})
    assert sorted(f.subject for f in check_groups(register, host)) == [
        "group::core-gov::core-darek",
        "group::core-gov::darek",
    ]


def test_a_host_administrators_own_groups_are_outside_core(register) -> None:
    host = _host(members={"users": frozenset({"darek"})})
    assert check_groups(register, host) == []


def test_the_binding_must_name_the_registers_governor(register) -> None:
    assert (
        check_binding(register, "principals:\n  core-darek: principal.governor\n") == []
    )
    wrong = check_binding(register, "principals:\n  darek: principal.governor\n")
    assert [f.subject for f in wrong] == ["binding"]
    assert "darek" in wrong[0].message


def test_sudo_rules_are_parsed_and_compared(register) -> None:
    text = (
        "Defaults:core-runner env_reset, !requiretty\n"
        "core-runner ALL=(root) NOPASSWD: /usr/local/sbin/core-deploy\n"
        'core-runner ALL=(core) NOPASSWD: /usr/local/sbin/core-sandbox-check ""\n'
        "%sudo ALL=(ALL:ALL) ALL\n"
        "darek ALL=(core-law) /opt/core/current/venv/bin/core-admin law apply *\n"
    )
    rules = parse_sudo_rules(text)
    assert ("core-runner", "root", "/usr/local/sbin/core-deploy") in rules
    assert check_sudo_rules(register, rules) == []


def test_an_unregistered_sudo_rule_for_an_identity_is_a_finding(register) -> None:
    rules = parse_sudo_rules(
        "core-runner ALL=(root) NOPASSWD: /usr/local/sbin/core-deploy\n"
        "core-runner ALL=(core) NOPASSWD: /usr/local/sbin/core-sandbox-check\n"
        "core-darek ALL=(core-law) /opt/core/current/venv/bin/core-admin law apply *\n"
    )
    found = check_sudo_rules(register, rules)
    assert [f.subject for f in found] == [
        "sudo::core-darek::core-law::/opt/core/current/venv/bin/core-admin"
    ]


def test_a_missing_registered_sudo_rule_is_a_finding(register) -> None:
    assert len(check_sudo_rules(register, [])) == 2


def test_governed_text_writable_by_others_is_a_finding(register, tmp_path) -> None:
    (tmp_path / ".intent").mkdir(mode=0o755)
    os.chmod(tmp_path / ".intent", 0o755)
    rule = tmp_path / ".intent" / "a.yaml"
    rule.write_text("x: 1\n")
    me = os.getuid()
    host = _host(accounts={"core-law": (me, "/usr/sbin/nologin", "core-law")})
    os.chmod(rule, 0o644)
    assert check_governed_modes(register, [tmp_path], host) == []
    os.chmod(rule, 0o664)
    assert [f.subject for f in check_governed_modes(register, [tmp_path], host)] == [
        f"governed::{rule}"
    ]


def test_governed_text_owned_by_another_account_is_a_finding(
    register, tmp_path
) -> None:
    (tmp_path / "CLAUDE.md").write_text("x\n")
    os.chmod(tmp_path / "CLAUDE.md", 0o644)
    host = _host(accounts={"core-claude": (os.getuid(), "/bin/bash", "core-claude")})
    found = check_governed_modes(register, [tmp_path], host)
    assert [f.subject for f in found] == [f"governed::{tmp_path / 'CLAUDE.md'}"]


def test_unregistered_github_collaborators_are_findings(register) -> None:
    people = [
        {"login": "DariuszNewecki", "role_name": "admin"},
        {"login": "core-claude-bot", "role_name": "write"},
        {"login": "erykpiotrov", "role_name": "write"},
        {"login": "someone", "role_name": "write"},
    ]
    assert [f.subject for f in check_github(register, people)] == [
        "github::collaborator::someone"
    ]


def test_a_hidden_bypass_list_is_not_evaluated_and_a_bypass_is_a_finding(
    register,
) -> None:
    found, hidden = check_bypass(register, [{"name": "main", "bypass_actors": None}])
    assert found == [] and hidden == ["main"]
    found, hidden = check_bypass(
        register,
        [
            {
                "name": "main",
                "bypass_actors": [
                    {"actor_type": "RepositoryRole", "actor_id": 5},
                    {"actor_type": "Integration", "actor_id": 42},
                ],
            }
        ],
    )
    assert [f.subject for f in found] == ["github::bypass::main::Integration:42"]
    assert hidden == []


def test_unreadable_sudoers_is_not_evaluated_never_passed(register, tmp_path) -> None:
    locked = tmp_path / "sudoers.d"
    locked.mkdir()
    (locked / "x").write_text("core ALL=(root) ALL\n")
    os.chmod(locked, 0o000)
    try:
        if os.access(locked, os.R_OK):
            pytest.skip("running as root: nothing is unreadable")
        report = check_host(
            register,
            repo_root=tmp_path,
            host=_host(),
            binding_file=tmp_path / "missing.yaml",
            sudoers=[locked],
            law_root=tmp_path / "no-law",
        )
    finally:
        os.chmod(locked, 0o755)
    assert "sudo rules" in report.not_evaluated
    assert "sudo rules" not in report.evaluated
    assert [f.subject for f in report.findings] == ["binding"]


def test_the_producer_socket_group_is_registered_before_the_host_has_it(
    register,
) -> None:
    """F1: until the host step creates core-producer, the register names a
    group the host lacks; the access check reports it (blocking)."""
    host = _host()
    del host.members["core-producer"]
    findings = check_groups(register, host)
    assert [f.subject for f in findings] == ["group::core-producer"]
