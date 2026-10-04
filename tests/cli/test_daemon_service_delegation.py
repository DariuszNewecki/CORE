"""`core-admin daemon` under service-account delegation (account split).

When ``systemctl_service_user()`` names another account, the CLI cannot run
``daemon-reload`` (the wrapper refuses it) and may not be able to read that
account's unit directory or get MainPIDs from ``systemctl show``. These
tests pin that each gap is skipped *visibly* rather than reported as a
false result: no reload attempt, "unknown" instead of "nothing enabled",
and no stray scan that would flag every managed process.
"""

from __future__ import annotations

from pathlib import Path

from cli.commands import daemon as daemon_module
from shared.utils.subprocess_utils import SubprocessResult


def test_daemon_reload_skipped_when_delegated(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(daemon_module, "systemctl_service_user", lambda: "core")
    monkeypatch.setattr(
        daemon_module,
        "run_systemctl",
        lambda *a: calls.append(a) or SubprocessResult("", "", 0),
    )
    daemon_module._daemon_reload()
    assert calls == []


def test_daemon_reload_runs_without_delegation(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(daemon_module, "systemctl_service_user", lambda: None)
    monkeypatch.setattr(
        daemon_module,
        "run_systemctl",
        lambda *a: calls.append(a) or SubprocessResult("", "", 0),
    )
    daemon_module._daemon_reload()
    assert calls == [("daemon-reload",)]


def test_enabled_template_stems_reads_wants_dir(monkeypatch, tmp_path) -> None:
    wants = tmp_path / ".config" / "systemd" / "user" / "default.target.wants"
    wants.mkdir(parents=True)
    (wants / "core-daemon-worker@audit_sensor_purity.service").touch()
    (wants / "core-daemon.service").touch()
    monkeypatch.setattr(daemon_module, "systemctl_service_user", lambda: None)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert daemon_module._enabled_template_stems() == {"audit_sensor_purity"}


def test_enabled_template_stems_missing_dir_is_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(daemon_module, "systemctl_service_user", lambda: None)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert daemon_module._enabled_template_stems() == set()


def test_enabled_template_stems_unreadable_dir_is_unknown(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(daemon_module, "systemctl_service_user", lambda: None)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    def _denied(self):
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(Path, "iterdir", _denied)
    assert daemon_module._enabled_template_stems() is None


def test_status_skips_stray_scan_when_show_fails(monkeypatch) -> None:
    def _fake_systemctl(*args: str) -> SubprocessResult:
        if args[0] == "show":
            return SubprocessResult("", "core-services: action not allowed: show", 2)
        return SubprocessResult("active", "", 0)

    def _ps_must_not_run(_spec: str) -> str:
        raise AssertionError("stray scan ran without systemd MainPIDs")

    monkeypatch.setattr(daemon_module, "run_systemctl", _fake_systemctl)
    monkeypatch.setattr(daemon_module, "list_all_processes", _ps_must_not_run)
    monkeypatch.setattr(daemon_module, "_heavy_worker_stems", lambda: [])
    monkeypatch.setattr(daemon_module, "_enabled_template_stems", lambda: None)
    daemon_module.status()
