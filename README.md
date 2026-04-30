# Capacium Publish — GitHub Action

Submit your capability to the Capacium Exchange automatically on release.

## Usage

Add this to your release workflow:

```yaml
name: Release

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: Capacium/capacium-action-publish@v1
        with:
          github_url: ${{ github.event.repository.html_url }}
```

The action submits your repository URL to the Capacium Exchange, where it is indexed and made discoverable via `cap search` and `cap install`.

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `github_url` | No | `github.repository` | GitHub URL to submit |
| `registry_url` | No | `https://api.capacium.xyz/v2` | Exchange registry URL |
| `manifest_path` | No | `capability.yaml` | Path to capability manifest (for validation) |

## Outputs

| Output | Description |
|--------|-------------|
| `submitted` | `true` if the submission was accepted |
| `listing_name` | Canonical name (e.g. `owner/skill-name`) |
| `job_id` | Queue job ID for status tracking |
| `status` | `pending`, `completed`, `failed`, or `duplicate` |

## How It Works

1. On `release.published`, the action POSTs your repo URL to `POST /v2/submit`
2. The Exchange validates the URL and enqueues a background job
3. The queue worker clones your repo, extracts `capability.yaml` or `SKILL.md` frontmatter
4. The capability is listed as `discovered` and available via `cap search`

## Difference from `capacium-action-validate`

| | Validate | Publish |
|---|---|---|
| Purpose | CI check (manifest valid?) | Release trigger (submit to Exchange) |
| When | Every push/PR | On release |
| Blocks CI | Yes (on error) | No (warns on failure) |
| Output | `valid` (bool) | `submitted` + `listing_name` |

## Supported Manifest Formats

- `capability.yaml` at repository root
- `SKILL.md` with YAML frontmatter at repository root

## Example: Full Release Workflow

```yaml
name: Release

on:
  push:
    tags: ['v*']

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Capacium/capacium-action-validate@v1

  publish:
    needs: validate
    runs-on: ubuntu-latest
    steps:
      - uses: Capacium/capacium-action-publish@v1
```

## License

MIT — see [capacium](https://github.com/Capacium/capacium) for details.
