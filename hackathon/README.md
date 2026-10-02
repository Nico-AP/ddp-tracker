> **About this folder.** A copy of the documents of the DDP2026 Hackathon's infrastructure track (user journeys prototype), added to the repository on 1 October 2026 at Hekmat's request. The originals live outside the repository. Left out of this copy: the hackathon's shared Google document (it lists the participants, and is the group's, not ours to publish), the Word copy of the features document (the Markdown copy has the same content), and every Python file of the plan (its starter files, agent definitions and screenshot tool duplicate the app's own modules and would trip the linters). A real TikTok username quoted from the live site is replaced by `<username>`, and the old demo password by `<removed>`. Links below to files that were left out do not resolve here.

# DDP2026 Hackathon: where outputs live

Conventions for every task in this Project.

## Locations

- **Local folder (Hekmat's computer):** `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs`. All documents produced for the hackathon are saved here. It sits next to the repository, not inside it.
- **Repository (fork):** `C:\Users\hekma\Documents\Projects\DDP-Tracker`, a clone of https://github.com/hekmatov/ddp-tracker on branch `dev`, with `upstream` pointing to https://github.com/Nico-AP/ddp-tracker. Only code goes here, never hackathon documents.
- **This Project (claude.ai):** this folder is connected to the Project, so tasks on Hekmat's computer read the documents here. Earlier documents also have a text copy under `claude/` in the Project; new ones do not need one (see rule 2).

## Rules for tasks

1. Save every deliverable to `DDP-Tracker-docs` (connect that folder, or request access to it), and add it to the index below.
2. A copy in the Project under `claude/` is no longer required (relaxed by Hekmat on 30 September 2026: he only works from this computer, where the folder is connected). Make one only if a chat without access to this folder has to read the document.
3. Use British English and no em dashes.

## Index

| Document | Local file | Project copy | Last updated |
|---|---|---|---|
| Features by user role (v2) | `DDP-Tracker_features-by-role.docx` and `.md` | `claude/features-by-role.md` | 30 September 2026 |
| Fictional sample DDPs (Facebook, Instagram, TikTok) with generator script | `sample-ddps/` (see its README) | `claude/sample-ddps-README.md` and `claude/make_sample_ddps.py` (the script regenerates the zips) | 30 September 2026 |
| Handoff pack: user journeys prototype (context, decisions, structure, journeys, codebase guide, build plan, demo data, issues) | `handoff-user-journeys/` (start with `00-START-HERE.md`) | `claude/handoff/` | 30 September 2026 |
| Implementation plan: user journeys prototype (coordinator guide, design, six phase files, starter files, screenshots tool, the prompt that starts the build) | `implementation-plan/` (start with `README.md`; the prompt is in `coordinator-prompt.md`) | None (not required, rule 2) | 30 September 2026 |
| Latest hackathon document (Word export), the source for the plan's design features | `latest hackathon google doc.docx` | None (not required, rule 2) | 30 September 2026 |
| User journeys prototype: how to push and run it on Windows, log in, a five-minute tour | `RUN-THE-PROTOTYPE.md` | None (not required, rule 2) | 30 September 2026 |
| User journeys prototype: summary (what was built, real versus fictional, hackathon notes, decisions to confirm, rough edges, findings for Nico, open questions) | `prototype-summary.md` | None (not required, rule 2) | 30 September 2026 |
| User journeys prototype: screenshots (43 pictures: landing page, eight journeys, every mock-up, feature cards, staff and curator views, phone width) | `prototype-screenshots/` (taken with `implementation-plan/tools/take_screenshots.py`) | None (not required, rule 2) | 30 September 2026 |
