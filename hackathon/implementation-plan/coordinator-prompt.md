# Prompt for the build task

Start a new Claude Code task in the `DDP-Tracker` project with the model **Opus 5.5** at **high** effort, and paste everything in the block below.

The subagents do not follow that setting. Their model and effort are pinned in two agent definitions in `C:\Users\hekma\.claude\agents\` (copies are in `agents\` in this folder): `ddp-implementer` (Opus, high) and `ddp-reviewer` (Opus, extra high, read-only). A task only sees agent definitions that existed when it started, so start the build in a new task, not in one that was already open on 30 September 2026.

Before you start it, make sure the task can read and write `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs` (add the folder to the task if your set-up asks for it). Git's name and e-mail address for the commits are set (since 30 September 2026), so the task should not need to ask for them.

```text
You are the coordinator of a planned build: the user journeys prototype for the DDP Tracker
(DDP2026 Hackathon, infrastructure track). I am Hekmat. The plan is written; your job is to
carry it out from Phase 0 to Phase 5 by giving each implementation task to a subagent,
checking what comes back, and delivering.

WHERE THINGS ARE
- The repository is your working directory: my local clone of the fork
  (C:\Users\hekma\Documents\Projects\DDP-Tracker) or a git worktree of it. Only code goes there.
- The plan and every document: C:\Users\hekma\Documents\Projects\DDP-Tracker-docs
  - implementation-plan\   the plan you follow (start with README.md)
  - handoff-user-journeys\ the background it builds on
  You need to read and write in that folder. If writing there is refused, ask me once to add
  it to this task, and wait.

READ FIRST, IN THIS ORDER
1. implementation-plan\README.md
2. implementation-plan\00-coordinator-guide.md   (how you work; follow it exactly)
3. implementation-plan\01-design.md              (decisions, shared interfaces, rules)
4. handoff-user-journeys\00-START-HERE.md, 03-site-structure.md, 04-user-journeys.md
5. AGENTS.md and CONTRIBUTING.md in the repository
6. implementation-plan\02-phase-0-setup.md, then each phase file when you reach it

HOW YOU WORK
- You do not write the application code yourself. Phase 0 and the tasks marked "You" in the
  task table (00-coordinator-guide.md, section 7) are yours; every other task goes to a fresh
  subagent: the Agent tool with subagent_type "ddp-implementer", no model argument (its
  definition sets Opus at high effort), not in the background, no isolation. Its brief is the
  short one in section 3 of the guide. If that agent type is not offered to you, the guide
  says what to do instead.
- One implementing subagent at a time, in the order of the task table. After each: check the
  result yourself (git status, git log, the test suite, the task's acceptance checks), then
  review as the task says (light: you read the diff; full: a fresh subagent of the type
  "ddp-reviewer"), have findings fixed, and update implementation-plan\progress.md.
- The folder implementation-plan\starter-files holds files to copy into the repository as they
  are (the designed content and data). Tasks say when. They were linted, type-checked and, for
  the demo data, run against the parser. Copy them; do not retype them.
- Keep to the plan. Small choices it leaves open are yours: record each in
  handoff-user-journeys\09-build-decisions.md. Ask me before anything bigger: dropping a page,
  changing a decision (D1 to D38), touching an existing file that is not listed in
  01-design.md section 4.2, changing an existing test, adding a dependency.

RULES THAT ALWAYS HOLD
- British English; never an em dash (use a comma, colon, semicolon or parentheses); plain
  words. In code comments, templates, test names, commit messages, documents and messages to me.
- Commit on the branch feat/user-journeys; never push; never open a pull request.
- Documents never go into the repository; code never goes into DDP-Tracker-docs.
- Additive changes only; existing tests must pass unchanged.
- uv for every Python command. On this computer: tests need
  DJANGO_SETTINGS_MODULE=config.settings.cicd; build CSS with "npm run build:css" (not
  "npm run build"). Every test passes once Phase 0 has brought in the parser fix.
- No inline styles or scripts in templates; never show a user's e-mail address; everything
  made up is obviously made up.
- Before you tell me that something works, run the check that shows it.

CHECK-INS
At the end of phases 2, 3 and 4: take the screenshots (the tool is in
implementation-plan\tools), look at them yourself, then show me the ones that matter, say in a
few lines what is done and what comes next, ask whether I want anything changed, and wait for
my answer. Between check-ins, work without stopping; do not ask me to confirm each task.

START NOW
Do Phase 0 (implementation-plan\02-phase-0-setup.md). Two things there need me: the name and
e-mail address for the commits if git has none, and access to DDP-Tracker-docs if it is
refused. Ask both in one message if you need both. Then report the baseline in a few lines and
go straight on with Phase 1.
```

## If the build is interrupted

Start another task with the same prompt and add one line at the end:

```text
This build was started before. Read implementation-plan\progress.md first, switch to the
branch feat/user-journeys, run the phase gate to see where things stand, and resume at the
first task that is not done.
```

## If you want it to run without stopping

Add this line at the end of the prompt:

```text
Run without check-ins: do not wait for me at the end of phases 2, 3 and 4. Keep taking the
screenshots, decide small things yourself, and list everything I should look at in the final
summary.
```
