# 08. Known issues, risks and open questions

## Bugs and findings (not for this prototype to fix, but do not make them worse)

| # | Issue | Evidence | Status |
|---|---|---|---|
| K1 | **TikTok chat usernames can leak into public paths.** The parser renames `Chat History with <username>:` to `{*}` only when there are at least two similar chats. The hackathon document reports `…/ChatHistory/Chat History with <username>:` on the live site. | Hackathon document; parser docs, `docs/docs/ddp_parser/index.md` §3.6, which uses exactly this path as the example for a variable-key path rule | Fix is configuration: add the path rule `/user_data_tiktok.json/Direct Message/Direct Messages/ChatHistory/Chat History with *` in the admin. Reported to Hekmat on 30 September; not confirmed as fixed. |
| K2 | **A possible second TikTok leak.** The live tree shows a key under `App Settings › Settings › SettingsMap › Family Content Preferences` that looks like a username. | Live tracker tree, 30 September | Unverified; worth checking |
| K3 | **Facebook `_v2` keys are wrongly collapsed to `{*}`.** The "hash-like token" rule `^(?=.*\d)(?=.*[A-Za-z])[A-Za-z0-9_-]{16,}$` in `packages/ddp-parser/src/ddp_parser/normalize.py` matches keys such as `deleted_friends_v2`, `account_accesses_v2` and `language_and_locale_v2`. | Reproduced with the sample Facebook DDP | Not reported upstream yet. Probably the hackathon issue "the tracker anonymizes file paths when repeated values occur". |
| K4 | **Registration e-mail says example.com.** `django.contrib.sites` is enabled with `SITE_ID = 1`, but the Site's domain is never set. | `config/settings/base.py` | Open |
| K5 | **Earliest upload shows everything as "new".** New and Changed compare only with uploads requested strictly earlier (`schemas/timeline.py`). | Code | Open (confusing, not wrong) |
| K6 | **No "Other" request mode.** Request mode is limited to app, browser or Portability API; ChatGPT exports come from a privacy centre. | `ddps/models.py` | Open |
| K7 | **User profile pages are orphaned.** Templates `users/user_detail.html` and `user_form.html` and `User.get_absolute_url` reference `users:detail`, but there is no `users/urls.py`. | Code reading (not run) | Open; avoid calling `get_absolute_url` on users |
| K8 | **`purge_upload_values` is not scheduled.** No schedule was found in the deployment configuration. | Compose and production config | Uncertain |

## Risks for the build

- **Upstream churn:**
  - Nico commits daily, and the navigation and home page are likely to change upstream too.
  - Keep changes additive and commits small.
  - Before delivering, rebase on the latest `upstream/dev` and re-run the tests.
- **Existing tests:** changing `/` or the navigation breaks `core/tests/tests.py::IndexViewTests`. Update them deliberately (see `05-codebase-guide.md`).
- **Prototype mistaken for real:**
  - every mock-up must carry the banner, and the fictional data must be obviously fictional;
  - never use real people's names or real account handles;
  - never show live-site data.
- **Scope creep:** twelve mock-up pages is a lot. If time is short, keep M1 to M3, M5 and M6 rich, and make the others simpler (a clear static page is fine). Record the trade-off.

## Open questions (for Hekmat and the team; do not block on them)

1. Offer the work back to Nico as a pull request, or keep it as a fork prototype for the hackathon?
2. Is a "researcher" a distinct account type, or is the concept view simply public?
3. Final navigation labels ("Concepts", "Compare", "Curate") and whether prototype items belong in the main navigation at all.
4. Who may become a platform moderator, and who appoints them?
5. Which export targets matter most: DDM, Port, plain JSON Schema?
6. What licence should the curated schema knowledge carry?
7. Should AI-suggested annotations be visible before a human has checked them?

Record any answers Hekmat gives during the build in `09-build-decisions.md`.
