# Releasing nightward (going public + PyPI)

Publishing is irreversible twice over: a public repo gets forked/indexed
immediately, and PyPI artifacts are mirrored the moment they upload. Work the
checklist top to bottom; nothing here is automated on purpose.

## 0. Hard gate (do not pass without it)

- [ ] Legal review complete (employment/IP constraints cleared by the owner).
      Nothing below happens before this box is checked.

## 1. History decision (file deletion does NOT scrub git history)

Sensitive content that was ever committed remains in history even after the
file is deleted. Pick one:

- [ ] **Option A (recommended, prepared): fresh public repository.**
      A clean single-commit snapshot of the release tree is maintained on the
      `public-release` branch of this repo (no history before it). To use it:
      1. On github.com create a new **private** repo (e.g. `<owner>/nightward-oss`).
      2. `git push git@github.com:<owner>/nightward-oss.git public-release:main`
      3. Audit the new repo (`git log` must show the single release commit).
      4. At launch: rename this repo to `nightward-archive`, rename the new
         repo to `nightward`, then flip it public. GitHub redirects renames.
      Keep this repo as the private archive. Pros: zero leakage risk.
      Cons: public history starts fresh (by design).
- [ ] **Option B: rewrite history in place** (`git filter-repo`) to drop
      removed files from all commits, then force-push and make public.
      Pros: keeps the repo/stars/issues. Cons: rewrites are error-prone —
      audit the result before flipping visibility.
- [ ] Either way, audit before flipping: `git log --all --oneline --stat` and
      search history for removed paths.

## 2. Content audit (already done on the branch, re-verify at release time)

- [ ] CLAUDE.md is the public English version (no legal/visibility notes).
- [ ] No personal-context docs (the private experiment specs were removed;
      experiment summaries contain aggregates only).
- [ ] `live-experiment/` does not exist in the tree being published.
- [ ] `python scripts/build_demo.py` output is the only dashboard ever
      published; no real `.nightward/` store leaves the repo.
- [ ] README quickstart works on a fresh clone (`pip install -e . && nightward run example`).

## 3. PyPI one-time setup

- [ ] pypi.org → account with 2FA.
- [ ] Add **Trusted Publisher** for the project: owner `JunghyunRyu`, repo
      `nightward`, workflow `release.yml`, environment `pypi`.
      (First release of a new project: use a "pending publisher" so no token
      is ever created.)
- [ ] GitHub → Settings → Environments → `pypi` → add yourself as required
      reviewer (second human gate on the publish job).

## 4. Ship

- [ ] Bump `version` in pyproject.toml; update README if needed.
- [ ] Tag: `git tag v0.X.Y && git push --tags`.
- [ ] Flip the repo public (same day as first release, so README links work).
- [ ] Actions → release → Run workflow. Approve the `pypi` environment.
- [ ] Verify: `pip install nightward` in a clean venv → run the quickstart.

## 5. Within 24h of launch

- [ ] Enable the Pages demo workflow (clean-room data only) if desired.
- [ ] Listings: pytest plugin list, MCP server directories, awesome-* lists.
- [ ] Launch post (Show HN: "a definition of 'done' for AI coding agents").
- [ ] From now on: PRs get human review before merge — the tool's own
      discipline applies to the tool.
