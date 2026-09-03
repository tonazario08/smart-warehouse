# Git and GitHub Rules

Apply these rules before every Git or GitHub action in this repository.

## Before committing

- Inspect `git status`, the staged diff, and the unstaged diff before choosing a commit message.
- Base the commit message on the actual changes, not on a generic task title.
- Use a concise Conventional Commit prefix when it accurately describes the change, such as `feat:`, `fix:`, `docs:`, `test:`, `build:`, or `chore:`.
- Run the relevant verification command for changed code. Run both `python -m pytest -q` and `npm.cmd run build` when backend and frontend change together.
- Do not stage or commit `.env`, credentials, tokens, private keys, `node_modules`, build artifacts, caches, virtual environments, or generated local data.
- Review the staged file list after `git add` and before `git commit`.

## Before publishing to GitHub

- Inspect the current branch and `git remote -v` before pushing.
- Push only to a configured, explicitly intended remote and branch.
- Never force-push, delete branches, rewrite history, change repository visibility, or create a pull request unless the user explicitly requests that action.
- After a successful push or pull request creation, report the commit hash and the resulting remote URL or pull request URL.

## Commit handoff

- Report the verification commands run and their results.
- Report the commit hash, subject, and whether the working tree is clean.
