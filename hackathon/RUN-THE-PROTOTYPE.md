# Run the user journeys prototype

For Hekmat, on Windows. Written 30 September 2026 at the end of the build.

## 1. What this is

A prototype of a restructured DDP Tracker: a landing page where a visitor picks one of eight roles, a journey page per role, twelve mock-up pages of planned features (with fictional data and a banner) and a feature cards page, plus a `seed_demo` command that fills an empty database with a demo. It lives on the branch **`feat/user-journeys`** of your local clone.

## 2. Push the branch

The build could not push (no GitHub credentials). In PowerShell or Git Bash:

```powershell
cd C:\Users\hekma\Documents\Projects\DDP-Tracker
git push -u origin feat/user-journeys
```

GitHub Desktop or VS Code work as well. No pull request was opened; whether to offer the work to Nico is an open question (see `prototype-summary.md`).

The build ran in a git worktree of your clone and has let go of the branch, so you can check it out in the clone itself.

## 3. Run it without Docker

This route was used throughout the build on this computer. Node is not needed: the compiled CSS is in the repository.

```powershell
cd C:\Users\hekma\Documents\Projects\DDP-Tracker
git switch feat/user-journeys
uv sync
$env:DATABASE_URL = "sqlite:///demo.sqlite3"
$env:USE_DOCKER = "no"
$env:DJANGO_EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
uv run manage.py migrate
uv run manage.py seed_demo
uv run mkdocs build -q -f docs/mkdocs.yml
uv run manage.py runserver
```

Then open http://127.0.0.1:8000/.

- The `mkdocs` line is optional: without it, the Docs link and the privacy guide answer "not found".
- The three `$env:` lines are needed in every new PowerShell window.
- `demo.sqlite3` is ignored by git.

## 4. Run it with Docker (the upstream way)

Not tested by the build.

```powershell
npm install
npm run build:css
docker compose -f docker-compose.local.yml up -d --build
docker compose -f docker-compose.local.yml run --rm django python manage.py seed_demo
```

Use `npm run build:css`, not `npm run build`: the second half of `npm run build` uses `mkdir -p` and `cp`, which fail on Windows.

## 5. Log in

`seed_demo` creates two demo users and prints their password when it runs. To choose the password yourself, set it before running `seed_demo` (it is never stored in the code):

```powershell
$env:DJANGO_DEMO_PASSWORD = "<a password of your choice>"
```

Without it, `seed_demo` makes up a random password and prints it once.

| User | Can do |
|---|---|
| `demo-admin@example.org` | Staff and superuser: approvals, the suggestion queues, the Django admin, the "Curate" item of the prototype strip, the staff view of the moderator dashboard |
| `demo-curator@example.org` | Not staff: owns the held YouTube upload (inspect it), one open suggestion and the suggested term "liked"; sees "My uploads" and "My suggestions" |

`seed_demo` only runs while `DEBUG` is on (local settings), unless you add `--force`.

## 6. A five-minute tour

1. **The landing page** (`/`): eight role cards, "How it works" and the live figures.
2. **The researcher's journey:** pick "Substantive researcher", then step 1 (the concept view for News and politics), step 3 (the concept "Watched a video") and add two or three concepts to the shortlist.
3. **The hand-over:** on the shortlist, "Copy the link for your engineer", open it in a private window (as the engineer would), and download the codebook or the DDM File Blueprints.
4. **The engineer's journey:** step 4, TikTok's changelog: 5 data points added, 33 moved or renamed, 1 changed and 1 removed between March and September 2026, computed from the two demo uploads.
5. **As the demo admin:** open "Approvals (1)", open the YouTube upload and approve it. Under Explore, YouTube then has 29 data points instead of 0.

## 7. Start again

```powershell
uv run manage.py seed_demo --reset
uv run manage.py seed_demo
```

`--reset` removes only what `seed_demo` made. Or delete `demo.sqlite3` and run `migrate` and `seed_demo` again.

## 8. If something is off

| What you see | Why, and what to do |
|---|---|
| "Error: That port is already in use." | Another server runs on port 8000. Stop it, or run `uv run manage.py runserver 8001`. In PowerShell: `Get-NetTCPConnection -LocalPort 8000 -State Listen \| ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }` |
| The pages have no prototype strip or look unstyled | The branch is not checked out: `git switch feat/user-journeys`. |
| `/docs/` or the privacy guide says "not found" | Build the docs: `uv run mkdocs build -q -f docs/mkdocs.yml`. |
| "Unknown command: 'seed_demo'" | Same as above: the branch is not checked out, or `uv sync` has not run. |
| The platform explorer scrolls sideways on a phone | Known, and older than this work (the explorer's own filter control). Not changed by the prototype. |
