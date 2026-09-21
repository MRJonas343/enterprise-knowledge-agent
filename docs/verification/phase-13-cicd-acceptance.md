# Phase 13 CI/CD Acceptance

| Field | Value |
| --- | --- |
| Status | **Accepted** |
| Date | 2026-09-20 |
| Phase | Phase 13, CI/CD |
| Environment | GitHub Actions, `ubuntu-latest`; the same commands verified locally first |
| Subscription | redacted deliberately; not part of the record |

## What this gate certifies

The Phase 13 exit criteria, as revised for this project:

> Changes are validated automatically before merge, a failure names the layer
> that broke, and the pipeline needs no credentials and holds no repository
> write access.

The original roadmap row asked for more than this. The phase was trimmed to the
one part that applies, and the trim is recorded here rather than left as an
absence.

## Scope

`.github/workflows/ci.yml` runs on every push to `main` and on every pull
request. Three independent jobs, so a failing run names the layer that broke:

| Job | Steps |
| --- | --- |
| `python` | `uv sync --frozen`, then `uv run pytest -q` |
| `frontend` | `npm ci`, `npm run lint`, `npm test`, `npm run build` |
| `terraform` | `terraform fmt -check -recursive`, `terraform init -backend=false`, `terraform validate` |

The workflow declares `permissions: contents: read` and uses a concurrency group
with `cancel-in-progress`, so a superseded run stops instead of queueing. Every
job has a bounded timeout. No secret is referenced anywhere in the file.

The frontend build is included because it is the only step that type-checks the
frontend: `eslint` and `vitest` both pass on a tree that `next build` rejects.

## What is deliberately not included

| Item | Why not |
| --- | --- |
| Terraform plan gate | **Planning needs the state, and the state is local.** The repository declares no `backend` block and the state is one git-ignored file on the operator's machine, so CI has no state and a plan there would propose creating every resource from scratch. A plan that reports the whole estate as new on every pull request is worse than no plan. Making it work needs a remote state backend, a federated identity and its role assignments — judged disproportionate here. Planning remains a local step performed by an authenticated operator, and a green run must not be read as "the plan is safe". |
| Artifact provenance | There is no artifact. Nothing is packaged or deployed: no Dockerfile, no compose file, no deployment manifest. |
| Environment promotion | There is one environment, the operator's machine. There is nothing to promote between. |
| Controlled deployment approvals | Nothing is deployed, so an approval gate would guard nothing. |

## Evidence

### 1. The workflow is well formed

Parsed as YAML and inspected:

```text
jobs: ['python', 'frontend', 'terraform']
permissions: {'contents': 'read'}
concurrency cancel-in-progress: True
triggers: ['push', 'pull_request']
frontend steps: ['Check out the repository', 'Set up Node',
                 'Install dependencies from the lockfile', 'Lint',
                 'Run the test suite', 'Build']
```

### 2. The same commands pass locally

Run before the workflow ever executed, so the pipeline is not green by accident:

```text
uv run pytest -q                    -> 48 passed, 1 warning
frontend: npm run lint              -> exit 0
frontend: npm test                  -> 2 files, 24 tests passed
frontend: npm run build             -> exit 0, TypeScript checked
terraform fmt -check -recursive     -> exit 0
terraform init -backend=false       -> exit 0
terraform validate                  -> Success! The configuration is valid.
```

The frontend build was additionally verified with `NEXT_PUBLIC_API_TOKEN`
absent, which is the CI condition, and it still exits 0. The application treats
a missing token as "send no Authorization header".

### 3. Action versions were verified, not assumed

Every pinned tag was checked against the action's own repository rather than
guessed. This mattered: **`astral-sh/setup-uv` stopped publishing moving major
tags at v8.0.0**, so no `v10` tag exists. Pinning `@v10` would have failed on
the workflow's first run. It is pinned to the immutable `v10.1.0` instead.

| Action | Pinned | Verified |
| --- | --- | --- |
| `actions/checkout` | `v7` | moving major tag exists (`v7.0.1`) |
| `astral-sh/setup-uv` | `v10.1.0` | **no moving `v10` tag exists**; pinned to the release tag |
| `actions/setup-node` | `v7` | moving major tag exists (`v7.0.0`) |
| `hashicorp/setup-terraform` | `v4` | moving major tag exists (`v4.0.1`) |

### 4. Terraform initializes on the runner's platform

The dependency lock file previously recorded checksums for `windows_amd64`
only, which would fail `terraform init` on the Linux runner. It now records
both platforms: four `h1:` entries, one per provider per platform.

## Known limitations and open items

- **The workflow has not been observed running on GitHub.** Every command it
  runs was verified locally and every action tag was verified against its own
  repository, but the first real execution is the first push that carries it.
- **The Terraform job checks formatting and configuration validity only.** It
  cannot detect a change that is valid but wrong.
- **No dependency or security scanning.** No Dependabot, no CodeQL, no image or
  manifest scanning.
- **No caching beyond what the setup actions provide** for uv and npm.
- **The Python side has no lint or type check.** There is no ruff, mypy or
  equivalent configured in this repository, so CI runs the tests and nothing
  else.

## What this gate does not cover

- **No deployment.** Nothing is built into an artifact, published or hosted.
- **No evaluation of answer quality.** The grounding probes are not run in CI
  because they need live Azure. Phase 11.
- **No observability signals.** Phase 12.
- **No environment promotion or release management.**

## Acceptance

The Phase 13 exit criteria, as revised, are met. Every pull request and every
push to `main` is validated across the three layers of this repository; a
failure identifies which layer broke; and the pipeline holds no credentials and
no write access, so it cannot alter anything it inspects.

Four items from the original row are recorded above as deliberately not
applicable rather than deferred, with the reason for each. The plan gate is the
only one that was genuinely achievable, and it was declined because its real
prerequisite — moving the state off a single local file — was judged
disproportionate to the value it would add here.
