# Security Policy

## Reporting a vulnerability

Use GitHub's private vulnerability reporting — click **"Report a vulnerability"** on the
[Security tab](https://github.com/DariuszNewecki/CORE/security/advisories/new).

Do **not** open a public issue for security vulnerabilities. Public disclosure before a fix
is ready puts every self-hosted instance at risk.

### Response timeline

| Milestone | Target |
|---|---|
| Acknowledgement | Within 7 days |
| Initial assessment (severity + scope) | Within 7 days |
| Fix or mitigation shipped | Depends on severity — see below |

Severity-based fix targets (best-effort for a solo-maintainer project):

- **Critical** (auth bypass, governance bypass, RCE) — patch within 7 days
- **High** (privilege escalation, data exposure) — patch within 14 days
- **Medium / Low** — addressed in the next regular release cycle

If a fix will take longer than these targets, I will say so in the private advisory thread
and agree a coordinated disclosure date with the reporter.

## Supported versions

CORE is in public beta. Only the current `main` branch receives security fixes. There are
no long-term-support releases yet.

## Security surface

The following areas are in scope for vulnerability reports:

> **Note:** JWT authentication, role enforcement, and SaaS delivery infrastructure were
> extracted to `core-platform` (a separate repo). CORE's API is unauthenticated at the
> runtime layer — authentication is an operator/platform responsibility. The surfaces
> below are the in-scope security boundaries within the CORE runtime itself.

| Surface | Why it matters |
|---|---|
| `ActionExecutor` governance token (`GovernanceBypassError`) | The mechanism that prevents `@atomic_action` functions from being called directly. A bypass lets code mutate the repo without governance recording. |
| `.intent/` immutability at runtime | Constitutional files must not be writable by any code path. |
| Autonomous proposal approval gate | A flaw that auto-approves `dangerous`-risk proposals without governor confirmation. |
| Commit authorship integrity (`StagingContaminationError`) | A bypass that lets an autonomous commit include files outside the declared production set. |

The following are **out of scope**:

- Vulnerabilities in the operator's own infrastructure (database, server, network config) —
  CORE is self-hosted; securing the host is an operator responsibility.
- The content of `.intent/` rules on a specific instance — governance posture is
  operator-defined, not a CORE security surface.
- Denial-of-service against a self-hosted instance (no SLA exists for availability).
- Vulnerabilities in third-party dependencies — report those upstream; CORE tracks
  dependency health via `pip-audit` in CI.
- Social engineering.

## Credit

Reporters who responsibly disclose a valid vulnerability will be credited in the release
notes and the GitHub advisory (unless they prefer to remain anonymous).

## Coordinated disclosure

I follow a coordinated disclosure model: the reporter and I agree on a disclosure date
after a fix is ready. The default embargo is 90 days from the initial report; shorter or
longer by mutual agreement. If a fix is not forthcoming within 90 days, the reporter is
free to disclose.
