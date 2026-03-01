# Stargazer Setup Guide

Stargazer is a CLI tool that auto-organizes your GitHub starred repos using Claude AI. It fetches your stars, classifies them into a taxonomy, publishes up to 32 GitHub Lists, and generates an awesome-list style README.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A [GitHub personal access token](https://github.com/settings/tokens) with `user` scope (needed for GitHub Lists)
- An [Anthropic API key](https://console.anthropic.com/settings/keys)

## Fork & Setup

1. **Fork this repo** on GitHub, then clone your fork:

```bash
git clone https://github.com/YOUR_USERNAME/stargazer.git
cd stargazer
```

2. **Install dependencies:**

```bash
uv sync
```

3. **Create a `.env` file** with your API keys:

```bash
cp .env.example .env
# Edit .env with your keys
```

Your `.env` should contain:

```
ANTHROPIC_API_KEY=sk-ant-api03-...
GH_TOKEN=ghp_...
```

> **GitHub token:** You can use `gh auth token` if you have the GitHub CLI installed. Make sure the token has the `user` scope — run `gh auth refresh -h github.com -s user` to add it.

## Usage

Stargazer has three commands that run in sequence:

### 1. Fetch your stars

```bash
uv run stargazer fetch
```

Downloads all your starred repos via the GitHub GraphQL API. Results are cached in `data/stars.json`.

Options:
- `--delay 1.0` — seconds between API requests (default: 1.0)
- `--full` — ignore cache, re-fetch everything

### 2. Classify repos

```bash
uv run stargazer classify
```

Uses Claude AI to generate a taxonomy from your stars, then classifies every repo into categories.

On first run, it generates a taxonomy and asks for your approval. Edit `data/taxonomy.json` if you want to customize categories before classifying.

Options:
- `--batch-size 20` — repos per Claude API call (default: 20)
- `--delay 2.0` — seconds between API calls (default: 2.0)

### 3. Publish

```bash
uv run stargazer publish
```

Creates GitHub Lists (top 32 categories) and generates the README.

Options:
- `--delay 3.0` — seconds between GitHub mutations (default: 1.0, recommend 3.0 for large collections)
- `--skip-lists` — only regenerate the README, skip GitHub Lists
- `--resume` — reuse existing lists, only re-assign repos (useful if a previous run was interrupted)
- `--readme-path README.md` — output path for the README

## Incremental Updates

Stargazer supports incremental updates. When you star new repos:

```bash
uv run stargazer fetch           # Only fetches new stars (stops when it hits known ones)
uv run stargazer classify        # Only classifies repos not yet in classifications.json
uv run stargazer publish --skip-lists  # Regenerate README without touching GitHub Lists
```

To also update GitHub Lists:

```bash
uv run stargazer publish --resume     # Assigns new repos to existing lists
```

## Manual Updates via GitHub Actions

This repo includes a GitHub Actions workflow (`.github/workflows/update.yml`) that you can trigger manually to update your stars from the GitHub UI.

### Setup

Add these secrets to your fork's repository settings (**Settings > Secrets and variables > Actions**):

| Secret | Value |
|--------|-------|
| `GH_TOKEN` | A GitHub token with `user` scope |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |

### How it works

Go to **Actions > Update Stars > Run workflow** to trigger an update. The workflow:

1. Restores cached data from previous runs
2. Fetches new stars incrementally
3. Classifies any unclassified repos using Claude API
4. Regenerates the README
5. Commits and pushes if there are changes

> **Note:** The first run has no cache, so it fetches and classifies all your stars from scratch. Subsequent runs are incremental — only new stars are processed.

## Customizing Your Taxonomy

The taxonomy is stored in `data/taxonomy.json`. You can edit it to:

- Rename categories
- Merge or split categories
- Add/remove subcategories
- Change descriptions

After editing, re-run `classify` and `publish` to apply changes:

```bash
uv run stargazer classify
uv run stargazer publish --skip-lists
```

## Data Files

| File | Versioned | Description |
|------|-----------|-------------|
| `data/stars.json` | No (.gitignored) | Cached star data from GitHub |
| `data/classifications.json` | No (.gitignored) | Repo-to-category mappings |
| `data/taxonomy.json` | Yes | Category tree definition |
| `README.md` | Yes | Generated awesome-list |

## Rate Limits

Stargazer is designed to be gentle with APIs:

- **GitHub API:** Configurable delay between requests (default 1-3s). Retries with exponential backoff on server errors and rate limits.
- **Claude API:** Configurable delay between batch calls (default 2s). Batches repos to minimize API calls.
- **GitHub Lists:** The `updateUserListsForItem` mutation is the slowest part. With 3s delays, assigning 3000 repos takes ~2.5 hours.
