# capacium-action-publish

**Official GitHub Action for publishing AI capabilities to the [Capacium Exchange](https://capacium.xyz).**

One step — validate, package, and publish. Designed for tag-push workflows.

## Quick Start

```yaml
# .github/workflows/publish.yml
name: Publish to Capacium Exchange

on:
  push:
    tags: ["v*"]

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4

      - uses: Capacium/capacium-action-publish@v1
        with:
          api_token: ${{ secrets.CAPACIUM_API_TOKEN }}
```

That's it. The action will:
1. Validate your `capability.yaml`
2. Package it into a `.tar.gz`
3. Publish to the Exchange
4. Post a job summary with the Exchange URL and quality score

## Trusted Publishing (OIDC)

To publish without a long-lived API token, enable OIDC and grant the job
`id-token: write`:

```yaml
jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: Capacium/capacium-action-publish@v1
        with:
          use_oidc: "true"
```

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `api_token` | ✅ | — | Exchange API token. Store as `CAPACIUM_API_TOKEN` secret. |
| `use_oidc` | ❌ | `false` | Use GitHub Actions OIDC trusted publishing. Requires `id-token: write`. |
| `capability_path` | ❌ | `./capability.yaml` | Path to `capability.yaml` or a directory containing one. |
| `registry_url` | ❌ | `https://api.capacium.xyz` | Exchange API URL. Override for self-hosted registries. |
| `python_version` | ❌ | `3.11` | Python version for installing the Capacium CLI. |
| `capacium_version` | ❌ | `capacium` (latest) | Pip spec for the Capacium CLI. Pin for reproducibility. |
| `fail_on_quality_below` | ❌ | `0` (disabled) | Fail the workflow if the quality score is below this threshold (0–100). |

## Outputs

| Output | Description |
|--------|-------------|
| `exchange_url` | Exchange listing URL for the published capability. |
| `quality_score` | Quality score returned by the Exchange (0–100). |
| `trust_state` | Trust state: `discovered` → `audited` → `verified`. |
| `canonical_name` | Canonical capability identifier (`owner/name`). |

## Examples

### Pin to a specific Capacium version

```yaml
- uses: Capacium/capacium-action-publish@v1
  with:
    api_token: ${{ secrets.CAPACIUM_API_TOKEN }}
    capacium_version: "capacium==1.0.0"
```

### Capability in a subdirectory

```yaml
- uses: Capacium/capacium-action-publish@v1
  with:
    api_token: ${{ secrets.CAPACIUM_API_TOKEN }}
    capability_path: ./my-skill/capability.yaml
```

### Fail if quality score is too low

```yaml
- uses: Capacium/capacium-action-publish@v1
  with:
    api_token: ${{ secrets.CAPACIUM_API_TOKEN }}
    fail_on_quality_below: "40"   # Must reach 'audited' threshold
```

### Publish to a self-hosted Exchange

```yaml
- uses: Capacium/capacium-action-publish@v1
  with:
    api_token: ${{ secrets.MY_REGISTRY_TOKEN }}
    registry_url: https://exchange.mycompany.internal
```

### Use Exchange URL and quality score in later steps

```yaml
- uses: Capacium/capacium-action-publish@v1
  id: cap_publish
  with:
    api_token: ${{ secrets.CAPACIUM_API_TOKEN }}

- name: Announce
  run: |
    echo "Published: ${{ steps.cap_publish.outputs.canonical_name }}"
    echo "URL: ${{ steps.cap_publish.outputs.exchange_url }}"
    echo "Score: ${{ steps.cap_publish.outputs.quality_score }}/100"
    echo "Trust: ${{ steps.cap_publish.outputs.trust_state }}"
```

## Setup

### 1. Create an API token

Log in to [capacium.xyz](https://capacium.xyz) → **Settings → API Tokens → Generate**.

### 2. Add the token as a repository secret

In your GitHub repository: **Settings → Secrets and variables → Actions → New repository secret**.

Name: `CAPACIUM_API_TOKEN`  
Value: *(paste your token)*

### 3. Ensure your repository has `capability.yaml`

Run `cap init --template skill` (or `mcp-server` / `bundle`) to scaffold one:

```bash
pip install capacium
cap init --template skill --name my-skill
```

See [docs/publishing.md](https://github.com/Capacium/capacium/blob/main/docs/publishing.md) for the full publisher guide.

## Quality Score

The Exchange computes a quality score (0–100) from 5 factors immediately after publish:

| Factor | Max | Signals |
|--------|-----|---------|
| Schema completeness | 30 | Required fields present, kind set |
| Maintenance | 25 | Recent commits, version > 0.1.0 |
| Community | 15 | GitHub stars, watchers |
| Documentation | 5 | README/SKILL.md present |
| Security | 25 | Signed, no known CVEs |

- Score ≥ 40 → `audited` trust state
- Score ≥ 70 → `verified` trust state

Use `fail_on_quality_below: "40"` to enforce a minimum quality gate in CI.

## Troubleshooting

**`capability.yaml` not found**  
Set `capability_path` to the correct path relative to the repository root.

**`cap publish failed (exit 1)`**  
Check that `CAPACIUM_API_TOKEN` is set and valid. Run `cap registry login` locally to verify.

**Quality score is 0**  
Score computation is async. Check the Exchange listing a few minutes after publish. Add a description, README, and repository URL to improve it.

**Self-hosted registry SSL errors**  
Ensure your registry has a valid TLS certificate. For development registries, set `registry_url` to the HTTP endpoint and configure `pip` trust settings as needed.

## License

Apache 2.0 — see [LICENSE](LICENSE).
