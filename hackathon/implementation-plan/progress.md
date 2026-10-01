# Progress ledger

Kept by the coordinator. One row per task; update it when a task starts and when it is done. A later task reads this file to resume.

- **Started:** 30 September 2026
- **Working directory:** `C:\Users\hekma\Documents\Projects\DDP-Tracker\.claude\worktrees\ddp-tracker-user-journeys-8235cc` (a git worktree of the local clone)
- **Subagents:** `ddp-implementer` and `ddp-reviewer` are offered, so the build uses them (model and effort pinned by their definitions)
- **Branch:** `feat/user-journeys`, created from `upstream/dev` at `a18b3f3`, with the parser fix picked from `fix/parser-mime-registry` as its first commit (yes: `5c22c20`)
- **Commits carry:** Hekmat Alrouh, as already set in git's configuration (nothing had to be asked)
- **Check-ins:** wait for Hekmat at the end of phases 2, 3 and 4 (change this line if he says otherwise)

## Upstream

What `upstream/dev` looked like when the build started, and anything that differed from the plan (the plan was written against `a18b3f3`):

- `upstream/dev` is still at `a18b3f3` (fetched 30 September 2026): nothing differs from the plan.
- `npm run build:css` gave a `main.css` that differed only in line endings; restored.

## Baseline

Before any change (expected at `a18b3f3` plus the parser fix: 493 passed, none failed, coverage 97%; 261 tests with Django's runner; ruff, mypy, djlint clean):

| Check | Result |
|---|---|
| pytest | 493 passed, none failed, coverage 97.34% |
| manage.py test | 261 tests, OK |
| ruff check, ruff format | clean (194 files formatted) |
| mypy | clean (178 source files) |
| djlint ddp_tracker | clean |

## Tasks

Status: todo, doing, review, done, blocked.

| Id | Task | Status | Commits | Notes (deviations, decisions, open points) |
|---|---|---|---|---|
| 0.1 | Preflight | done | | Tools fine (uv 0.11.16, Node 24, npm 12, git 2.53); git identity already set; both agent types offered |
| 0.2 | Branch and environment | done | `5c22c20` (parser fix) | Branch created in the worktree; `uv sync`, `npm ci`, `build:css`, docs built |
| 0.3 | Baseline, ledger, decision log | done | | Baseline as expected; site answers 200 on `/` and `/platforms/` |
| 1.1 | App skeleton and fictional packages | done | `43599c6` | Full review: approved. The test path for Instagram stories is `/media/stories/202609/{*}.jpg` (own generator per package puts all stories in September) |
| 1.2 | `seed_demo` | done | `c7a78f3`, `61d6770` | Full review: approved with notes, all fixed in `61d6770`: a test for a failed seed (rollback), reset deletes representations before suggested terms, docstring says deleted demo rows come back, correct singulars in the summary ("1 suggested term, 1 suggestion"). Seeded pages checked as the demo admin: TikTok explorer, approvals (YouTube waiting), suggestion queue all 200 |
| 2.1 | Journeys, routes and scaffolding | done | `c28b504` | Full review: approved. One commit (the step said two but gave one command). Open point for the summary: `targets.py` finds the demo uploads by platform and state, not by who uploaded them, so against real data a "demo" link could open a real upload |
| 2.2 | Navigation and styles | done | `cfa5742`, `10dc2c9` | Full review: approved with one fix, done in `10dc2c9`: pill text darkened to reach WCAG AA (green 5.57:1, amber 5.29:1). Plan said 5 navigation tests fail first; 4 do (one guards what already existed). Note for task 3.3: the copy confirmation needs a live region to be announced |
| 2.3 | Screenshots and check-in | done |  | Screenshots taken (36 pictures, no problem; the explorer's sideways scroll reported as known). Phase gate green: 566 passed, 334 with Django's runner, ruff, mypy, djlint clean. Hekmat keeps D20 and D21. Seen: the breadcrumb's middle item reads "journeys" / "prototype" in lower case, not a link (for task 5.1) |
| 3.1 | Concept view (M1) | done | `8531f91`, `0a01cec` | Full review: changes needed, fixed in `0a01cec`: two test checks that could never fail tightened (explorer link with its text, count of fictional labels), selects tested, dates shown only when seen, "Show concepts" button, badge margin. `Http404` left for task 3.2 to import. Note: the list page takes about 228 queries (fine for a prototype) |
| 3.2 | Concept detail (M2) | done | `984fbe1` | Light review (coordinator): diff read, page looked at. Link-back test checks the page's own "All concepts" link (the strip links to the list on every page). Added `LocationView.search` for the explorer link. For task 5.1: breadcrumb says "Concept", not the concept's name |
| 3.3 | Shortlist and exports (M3) | done | `50b897a`, `d11ed93`, `4c1cfa3` | Full review: changes needed, all fixed. Must fix (from task 2.2): our `.copy-button.is-copied::after` overrode the existing explorer's " Copied"; removed. Also: redirect only to local paths (a bare word gave a 500), readable path columns at phone width (`.table-scroll td.text-break` min width), "Note saved for X.", labelled note fields, "Add these to my shortlist", CSV with a byte-order mark. Hand-off tested by hand by implementer and reviewer |
| 3.4 | Changelog (M5) | done | `7437a99` | Full review: approved; figures checked against `schemas.timeline` (38 new: 5 added, 33 moved; 1 changed; 1 removed). Moved rows sorted shallowest first so the renamed lists show (the plan's plain sort failed its own test). Open points for the summary: two packages with the same request date would give two entries; "removed" compares with the latest earlier package only, and packages from different people can differ without the platform changing |
| 3.5 | API overview (M6) | done | `acb82cb` | Light review (coordinator): diff read; plan's tests word for word; no link to the live site; explainers endpoint (D29) present; no sideways scroll at 375 (implementer checked) |
| 3.6 | Screenshots and check-in | done | `d796a50` | Screenshots: no problem. Core story walked: all 13 step links of the researcher and engineer journeys land where the step says. Phase gate green (623 passed). Hekmat: remove every "fictional" label; done in `d796a50` with the shortlist's previews folded into `details` (625 passed; convention test guards it) |
| 4.1 | Compare (M4) | done | `5b4ecd0` | Light review (coordinator): diff read. The "fictional" test check dropped (Hekmat). Beware: the context name `waiting` clashes with `base.html`'s `approvals_waiting as waiting` for staff (crashed the page); renamed `no_package` |
| 4.2 | Snapshots (M7) | done | `60c8212` | Light review (coordinator): diff read. Copy button as agreed (data-copy, status element), no fictional labels; DOIs stay under `10.0000/fictional`. Download buttons name the version |
| 4.3 | Request instructions (M8) | done | `40d3763` | Light review (coordinator): diff read. No fictional label on "Last checked"; added "These steps are not <Platform>'s official instructions."; upload button carries the platform's id |
| 4.4 | Moderator dashboard (M9) | done | `dd6626a`, `1cca3d5` | Full review: approved with findings, all fixed: counts annotation suggestions only (matches the queue it links), test for a signed-in non-staff user, approval counts shown to staff only, "No counted uploads of X yet.", approvals link only when above 0. Figures match the explorer (TikTok 177 of 190 to triage, 17 lists without a representation) |
| 4.5 | Seed annotations (M10) | done | `4c14098`, `65ca02e` | Light review (coordinator): diff read; link tabs with aria-current, POSTs change nothing and redirect to a fixed local path. Follow-up `65ca02e`: written "(fictional …)" tags removed from the seeding source, the snapshot citation and the hubs (Hekmat's decision); a crawl of 44 pages finds "fictional" only in the banner, the DOI prefix and the export files' source line (kept: the files leave the site without the banner) |
| 4.6 | Roles and platforms (M11) | done | `bc72941` | Light review (coordinator): diff read. POST changes nothing and redirects to a fixed path; labelled form; accounts as `#n`; admin links for staff only; platform counts as the Explore page counts them |
| 4.7 | Learn (M12) | done | `2de1289` | Light review (coordinator): diff read. Quiz as native `details`; only curated example values; no fictional caption (a plain "typed by a curator, not anyone's real data" line). For task 5.1: "Click a question" should not assume a mouse |
| 4.8 | Feature cards page | done | `3704461` | Light review (coordinator): diff read; each card links with "See it in the prototype: <mock-up>"; tests also cover the `features` view |
| 4.9 | Screenshots and check-in | done |  | Screenshots: no problem. Every journey walked signed out and as the demo admin, the contributor's as the demo curator: every link lands where the step says. Phase gate green (682 passed). Hekmat: looks fine, go on; all mock-ups will be shown, so no order of polish |
| 5.1 | Accessibility and phone width | done | `430e9cd`, `33d2450` | Full review: approved. Breadcrumbs as `nav` + `ol` with `aria-current`, last item matches the h1; "Open a question"; "made up" remarks removed; every page checked at 375 (no sideways scroll except the known explorer); tables readable. Follow-up: header cells checked per table, empty aria-label not a label, compare's request modes read as one line. Two counts of `aria-current` in this build's own tests became 2 (breadcrumb + tab) |
| 5.2 | Rebase on upstream and full gate | done |  | `upstream/dev` still at `a18b3f3`: no rebase needed. Full gate green: pytest 690 passed (coverage 97.63%), Django's runner 458 OK (684 with the parser tests), ruff, mypy, djlint clean, no inline style or script, no em dash. Acceptance criteria 1 to 8 hold; outside `journeys` only the files of the design's list changed, plus the parser fix. 28 commits, messages clean |
| 5.3 | Final screenshots | done |  | 43 pictures on a fresh database, no problem (the explorer's sideways scroll noted as known). The tool now also takes the review of the September TikTok upload as the demo admin (`35-review-tiktok-staff`), the held YouTube upload as the demo curator (`40-inspect-held-youtube-curator`) and nine phone pictures |
| 5.4 | Documents | done |  | `RUN-THE-PROTOTYPE.md` and `prototype-summary.md` written; the tour's approval step checked on a copy of the demo database (YouTube goes from 0 to 29 data points); the demo password is referred to, not written out. Decision log complete; index updated; no Project copies (D38) |
| 5.5 | Handover | done |  | Repository clean; 28 commits from `upstream/dev` to `feat/user-journeys` (`33d2450`); the worktree is detached so the branch can be checked out in the clone; no server or background task left running |

## What Hekmat said at the check-ins

| Date | Phase | What he asked for or decided |
|---|---|---|
| 30 September 2026 | Phase 2 | Keep D20 (the previous home page at `/overview/`) and D21 (prototype pages in their own strip). Go on with Phase 3. |
| 30 September 2026 | Phase 3 | Remove every "fictional" label: they are unnecessary and distract from the other tags; everyone looking at the prototype understands the data is fictional. (The export previews on the shortlist are folded, as proposed; the blueprint keeps its label, no objection.) |
| 30 September 2026 | Phase 4 | Looks fine; go on with Phase 5. All mock-ups will be shown at the hackathon, so the order of the polish does not matter. |

## Where the plan was wrong

Anything in the plan or the starter files that did not fit and had to be adapted (so that the summary can say so):
- Task 1.1: `test_instagram` expected `/media/stories/{*}/{*}.jpg`; with one generator per package all stories fall in September 2026, so the path is `/media/stories/202609/{*}.jpg`. The reviewer checked that every path `spec.py` relies on (74) still exists and that seeding gives the figures of the phase introduction.
- Task 1.2: the command summary in step 7 read "1 suggested terms, 1 suggestions"; it now uses the singular for a count of 1. `seed.py` (docstring, order of deletion in `reset`) and `spec.py` (one description ended in a question mark) differ from the starter files after the review.
- Task 3.1: two checks in the plan's `test_availability_is_said_in_words` could never fail (the header always links to `/platforms/`, the banner always says "fictional"); tightened.
- Design section 7 and task 4.2: the class `copy-button` clashes with the reviews app's own `.copy-button` (a bare icon button) and the starter Sass rule for it overrode the explorer's confirmation. Journeys pages now use a normal Bootstrap button with `data-copy` and a `role="status" data-copy-status` element; the plan files were updated.
- Task 3.4: sorting moved paths plainly by path pushed "Video Browsing History" out of the first 8 rows, so the plan's own `test_the_page` failed; moved rows are sorted shallowest first.
- Task 4.1: a template context variable named `waiting` is overwritten for staff by `base.html`'s `{% approvals_waiting as waiting %}`; avoid that name.
- After delivery (1 October 2026): Hekmat pushed and asked for a pull request; draft PR Nico-AP/ddp-tracker#2 opened.
