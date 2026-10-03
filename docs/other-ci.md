# Audit with pre-commit or GitLab

The [GitHub Action](cold-reviewer.md) is the main way to run CORE's audit in CI. The
same offline audit also runs as a pre-commit hook and as a GitLab CI job. All three need
a repository with a `.intent/` constitution — see [Start a governed project](start-a-project.md)
or [Add a rule pack](adopt-a-pack.md).

## pre-commit

Add CORE to the repository's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/DariuszNewecki/CORE
    rev: v2.11.0          # a released tag
    hooks:
      - id: core-audit
```

```bash
pre-commit install            # run the audit before every commit
pre-commit run --all-files    # or run it now
```

The hook runs `core-admin code audit --offline` on the whole repository. A blocking
finding fails the hook and stops the commit. pre-commit installs `core-runtime` into its
own environment the first time, which takes a few minutes; later runs take seconds.

## GitLab CI

CORE ships a job template, `.gitlab-ci/CORE.gitlab-ci.yml`, that runs the offline audit
and publishes the findings as a CodeClimate report, so they appear in the merge
request's Code Quality tab. It installs the pinned `core-runtime` release at job start.

| Variable | Default | Meaning |
|---|---|---|
| `CORE_SEVERITY` | `block` | Lowest severity reported: `block`, `high`, `medium`, `low`, `info` |
| `CORE_IMAGE` | `python:3.12-slim` | Image to run in; use one with `core-runtime` preinstalled to skip the install |

Exit code 1 means blocking findings (a developer fixes the code); 2 means the
constitution could not be read or the audit could not govern (an operator fixes the
setup).

!!! warning "Not yet verified on GitLab"
    The audit command the template runs is the same one the GitHub Action and the
    pre-commit hook run, and is tested. The template itself has not been run on a GitLab
    instance. Report problems as a GitHub issue.
