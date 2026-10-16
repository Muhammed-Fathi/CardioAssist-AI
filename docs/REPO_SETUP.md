# Publish starter repository and connect Arena Agent

## Create repository (human)

1. Extract the starter ZIP locally.
2. On GitHub, choose **New repository** and name it `CardioAssist-AI`, mark **Private**, and **do not** generate an initial README, `.gitignore`, or license (already included in the extracted starter).
3. In **PowerShell**, enter the extracted `CardioAssist-AI-repo-starter` folder and run the commands below, replacing `YOUR_GITHUB_USERNAME` with your actual username:

```powershell
git init -b main
git add .
git commit -m "chore: initialize CardioAssist research workspace"
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/CardioAssist-AI.git
git push -u origin main
```

You must have Git installed and be authenticated to GitHub (e.g., Git Credential Manager). If `git init -b main` is unavailable on an older installation, update Git.

4. In GitHub verify that `AGENTS.md`, `research/source_materials`, `prompts/arena_phase0.md` and the project README are visible. Add trusted team collaborators from repository **Settings**.
5. In Arena Agent Mode, connect GitHub, choose **Manage repositories**, authorize `CardioAssist-AI`, and enable GitHub for the session. Ensure the agent has selected the correct repository before submitting the prompt.
6. Paste the prompt in `prompts/arena_phase0.md`. Do not attach unrelated sensitive data.
7. Require a **dedicated branch, report at `docs/phase0/PHASE0_REVIEW_DRAFT.md`, and PR only**. Review the PR diff before any merge.

## GitHub Free / private limitations
- Enforced branch protection rules are **not supported** for private repositories on GitHub Free according to GitHub Docs; do not claim the branch is technically protected. Use explicit maintainer review and separate working branches, but recognize it is a team process, not a platform guarantee.
- Individual Git objects over 100 MiB are blocked; objects above 50 MiB produce warnings. This starter deliberately excludes the ~70 MiB source PPTX, providing the PDF and complete speaker notes instead.
- Only use Git LFS after checking its current *metered free quota*, ownership, and zero-dollar budget configuration. Prefer excluding raw datasets/model artifacts from the repo entirely.
- GitHub persists **pushed commits**, not arbitrary Arena sandbox files, installed dependencies, caches or downloaded datasets.
- Arena's GitHub workflow normally gives a single PR per chat session; start a new Agent session for the next PR and make sure files are committed/pushed *before closing or merging*.

## Local sanity check (optional)

```powershell
python scripts/verify_sources.py
```

Use Python 3.10+ for the basic verifier; the verifier uses only the standard library and does **not** download or modify anything.
