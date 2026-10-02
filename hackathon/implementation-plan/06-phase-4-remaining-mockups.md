# 06. Phase 4: the remaining mock-ups


> **Changed at the Phase 3 check-in (Hekmat, 30 September 2026):** pages carry **no "fictional" labels** (no `badge--fictional`, no "(fictional)" tags). Where this file asks for "the fictional label" or "Fictional label", leave it out, and where a test asserts `"fictional"` on a page, drop that check (the banner contains the word anyway, so it proved nothing). Fictional data itself stays obviously fictional (DOIs under `10.0000/fictional`, `example.org` addresses, accounts as numbers). A test in `test_conventions.py` checks that no template uses `badge--fictional`.

Output: every journey step leads to a page with content. Seven mock-ups (M4, M7 to M12) and the feature cards page, then the third check-in.

The shape of every task is the one described at the top of `05-phase-3-core-mockups.md` (replace the placeholder view, add the template, add the tests, real data where the database has it, a note where it has none, the fictional label where fictional and real data meet). Read that introduction first. The template to imitate is `prototype/concepts.html`.

These tasks do not depend on each other. Each ends with the same two steps, not repeated below:

- **Run the tests, reformat, look:** `uv run djlint ddp_tracker/journeys --reformat`; the page's tests and the whole `ddp_tracker/journeys/tests` folder; then the page on port 8001 with the seeded `demo.sqlite3`, wide and at phone width.
- **Task gate and commit:** `git add ddp_tracker/journeys` (plus `assets/scss` and `ddp_tracker/static/css/main.css` if you added Sass), `uv run pre-commit run`, `git commit -m "feat(journeys): add the <page> mock-up (<number>)"`.

Buttons that would change something post to the page itself, which answers with a message that starts "In the real feature, this would" and ends "Nothing was saved.", and redirects back (so that a reload does not post again). They never change the database. Tests prove that.

---

## Task 4.1: Compare platforms (M4)

**Review:** light. **Depends on:** 3.1 (the concepts).

**Files:** modify `mockups/compare.py`; create `prototype/compare.html`, `tests/test_compare.py`.

**Consumes:** `FACTS` (in the module), `CONCEPTS` from `mockups/concepts.py`, `DEMO_PLATFORMS`, `find_platform`.

**What the page shows:**

- "What each platform discloses" (`h2`): a table `table matrix` in a `table-scroll`. Columns: the four demo platforms (`<th scope="col">`). Rows: the concepts by name (`<th scope="row">`, a link to the concept). A cell says "Yes" (`matrix__yes`) or "No" (`matrix__no`). A last row "Concepts disclosed" with "N of 9" per platform. Under the table: "No means: not seen in the packages uploaded so far. YouTube has no package that counts yet."
- "How people get their data" (`h2`): one `proto-panel` per platform in `proto-columns`, each with a `dl class="facts"`: Ways to request, Formats, How long it takes, Documentation, Machine-readable. These are fictional: one fictional label per panel.
- In each panel, "Documentation gap": "N documented but not observed, M observed but not documented" (fictional), with a link to `journeys:seed` (`?source=docs`).
- In each panel, from the database (not fictional): "In this tracker: X uploads, Y data points, Z annotations, last requested <date>", with links to the platform's explorer and its changelog (`journeys:changes`). If the platform is not in the database: the `seed_demo` note once, above the panels.

**View:**

```python
def _figures(platform: Platform) -> dict[str, Any]:
    """What this tracker holds about a platform (only uploads that count)."""
    registered = platform.uploads.filter(registered_at__isnull=False)
    points = platform.locations.filter(
        observations__is_data_point=True, observations__upload__registered_at__isnull=False
    )
    return {
        "uploads": registered.count(),
        "data_points": points.distinct().count(),
        "annotations": platform.annotations.count(),
        "last_requested": registered.aggregate(last=Max("requested_at"))["last"],
    }


def compare(request: HttpRequest) -> HttpResponse:
    """M4: concepts by platforms, and how people get at their data on each."""
    concepts = sorted(CONCEPTS, key=lambda concept: concept.name)
    matrix = [
        (concept, [slug in concept.platforms for slug in DEMO_PLATFORMS]) for concept in concepts
    ]
    panels = []
    for facts in FACTS:
        name, platform = find_platform(facts.slug)
        panels.append(
            {
                "facts": facts,
                "name": name,
                "platform": platform,
                "disclosed": sum(facts.slug in concept.platforms for concept in CONCEPTS),
                "figures": _figures(platform) if platform is not None else None,
            }
        )
    context = {
        "platforms": DEMO_PLATFORMS,
        "matrix": matrix,
        "panels": panels,
        "total": len(CONCEPTS),
        "has_data": any(panel["platform"] is not None for panel in panels),
    }
    return render_mockup(request, "compare", "journeys/prototype/compare.html", context)
```

**Tests** (`tests/test_compare.py`):

```python
"""M4, comparing platforms: which concepts each discloses, and how people get their data."""

from datetime import date

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.journeys.mockups.compare import FACTS
from ddp_tracker.journeys.mockups.concepts import CONCEPTS
from ddp_tracker.journeys.tests.utils import SeededTestCase

PAGE = reverse("journeys:compare")


class CompareWithoutDataTests(TestCase):
    def test_the_matrix_needs_no_data(self):
        response = self.client.get(PAGE)
        rows = dict(response.context["matrix"])
        by_slug = {concept.slug: cells for concept, cells in rows.items()}
        # platforms in the order facebook, instagram, tiktok, youtube
        self.assertEqual(by_slug["saw-ad"], [False, True, False, False])
        self.assertEqual(by_slug["off-platform-activity"], [True, False, True, False])
        self.assertEqual(len(rows), len(CONCEPTS))
        self.assertContains(response, "seed_demo")
        self.assertTrue(all(panel["figures"] is None for panel in response.context["panels"]))

    def test_yes_and_no_are_words(self):
        response = self.client.get(PAGE)
        self.assertContains(response, "matrix__yes")
        self.assertContains(response, ">Yes<")
        self.assertContains(response, ">No<")


class CompareTests(SeededTestCase):
    def test_the_panels_mix_fictional_facts_and_real_figures(self):
        response = self.client.get(PAGE)
        panels = {panel["facts"].slug: panel for panel in response.context["panels"]}
        self.assertEqual(set(panels), {facts.slug for facts in FACTS})
        tiktok = panels["tiktok"]
        self.assertEqual((tiktok["figures"]["uploads"], tiktok["figures"]["annotations"]), (2, 12))
        self.assertEqual(tiktok["figures"]["data_points"], 190)
        self.assertEqual(tiktok["figures"]["last_requested"], date(2026, 9, 15))
        self.assertEqual(tiktok["disclosed"], 8)
        self.assertEqual(panels["youtube"]["figures"]["uploads"], 0)  # its upload is held
        self.assertContains(response, "fictional")
        self.assertContains(response, "8 of 9")
        self.assertNotContains(response, "seed_demo")

    def test_it_links_onwards(self):
        response = self.client.get(PAGE)
        for url in (
            reverse("journeys:concept", args=["saw-ad"]),
            reverse("schemas:platform", args=["tiktok"]),
            reverse("journeys:changes", args=["tiktok"]),
            reverse("journeys:seed") + "?source=docs",
        ):
            self.assertContains(response, url)
```

(The `>Yes<` check assumes the word is the only content of its element; adjust it to your markup.)

**Acceptance:** the tests pass; the matrix scrolls inside its box on a phone; each panel carries the fictional label.

---

## Task 4.2: Snapshots (M7)

**Review:** light.

**Files:** modify `mockups/snapshots.py`; create `prototype/snapshots.html`, `tests/test_snapshots.py`.

**Consumes:** `SNAPSHOTS`, `DOI_PREFIX` (in the module); `static/js/journeys.js`.

**What the page shows:**

- An introduction: the tracker changes all the time; a snapshot fixes a state, so that a methods section, a preregistration or a report can point at it.
- "Releases" (`h2`): a table in a `table-scroll`: Version, Released, Platforms, Data points, Annotations, Representations, DOI. Each DOI is followed by the fictional label.
- Per release, "What changed" (its `changes`, as a list).
- "Cite this" (`h2`): for the latest release, the citation in a `cite-box`, and a button "Copy the citation" (`class="btn btn-secondary btn-sm"`, `data-copy="<the citation>"`, `data-copied="Citation copied to the clipboard."`) and next to it an element `role="status" data-copy-status` (as on the shortlist; no class `copy-button`, see `01-design.md`, section 7).
- "Pin a snapshot" (`h2`, `id="pin"`): two sentences for scripts and tools: ask for a version, not for "latest", and the result stays the same. The example `curl <pinned_url>` in a `code-sample`.
- "Download": three disabled buttons (JSON Schema, codebook, everything as a zip) with the sentence "In the real feature, this would download the release."
- "Licence": one sentence, and a link to the licence section of the API page (`journeys:api` with `#licence`).
- The script tag for `journeys.js`.

**View:**

```python
def snapshots(request: HttpRequest) -> HttpResponse:
    """M7: dated releases of the knowledge base, to cite and to pin."""
    context = {"snapshots": SNAPSHOTS, "latest": SNAPSHOTS[0]}
    return render_mockup(request, "snapshots", "journeys/prototype/snapshots.html", context)
```

**Tests** (`tests/test_snapshots.py`):

```python
"""M7, snapshots: dated releases to cite and to pin. All fictional."""

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils.html import escape

from ddp_tracker.journeys.mockups.snapshots import SNAPSHOTS

PAGE = reverse("journeys:snapshots")


class SnapshotDataTests(SimpleTestCase):
    def test_newest_first_and_monthly(self):
        versions = [snapshot.version for snapshot in SNAPSHOTS]
        self.assertEqual(versions, sorted(versions, reverse=True))
        self.assertEqual(versions[0], "2026.09")

    def test_a_doi_cannot_be_mistaken_for_a_real_one(self):
        for snapshot in SNAPSHOTS:
            self.assertTrue(snapshot.doi.startswith("10.0000/fictional"))
            self.assertIn("fictional DOI", snapshot.citation)


class SnapshotPageTests(TestCase):
    def test_the_releases(self):
        response = self.client.get(PAGE)
        for snapshot in SNAPSHOTS:
            self.assertContains(response, snapshot.version)
            self.assertContains(response, snapshot.doi)
        self.assertContains(response, "Tiktok Live is new")

    def test_citing_the_latest(self):
        response = self.client.get(PAGE)
        latest = SNAPSHOTS[0]
        self.assertContains(response, escape(latest.citation))
        self.assertContains(response, f'data-copy="{escape(latest.citation)}"')
        self.assertContains(response, "js/journeys.js")

    def test_pinning_for_machines(self):
        response = self.client.get(PAGE)
        self.assertContains(response, 'id="pin"')
        self.assertContains(response, SNAPSHOTS[0].pinned_url)
        self.assertContains(response, reverse("journeys:api") + "#licence")
        self.assertContains(response, "In the real feature, this would")
```

**Acceptance:** the tests pass; no DOI on the page resolves to anything real.

---

## Task 4.3: Request your data (M8)

**Review:** light.

**Files:** modify `mockups/instructions.py`; create `prototype/request.html`, `tests/test_instructions.py`.

**Consumes:** `INSTRUCTIONS`, `PAIR_HINT` (in the module), `DEMO_PLATFORMS`, `find_platform`.

**What the page shows:**

- Heading: "Request your data from <Platform>".
- The other platforms as links in a row (Bootstrap `nav nav-pills`, the current one `active` with `aria-current="page"`).
- A `badge badge--prototype` "To be verified by curators" and "Last checked <date>" with the fictional label. One sentence: platforms change their menus; if a step is wrong, say so (in the real feature, through a suggestion).
- The steps as an `<ol>`.
- A `dl class="facts"`: Choose, How long it takes, What you receive.
- A `proto-panel` "Make it a pair" with `PAIR_HINT`.
- "Then" (`h2`): a button link "Upload your DDP" to `ddps:upload-create`, with `?platform=<pk>` when the platform is in the database (the upload form reads it), and a link "What happens to your data" to the privacy guide (`docs`, `guide/privacy/`). One line: "Uploading needs an account."
- One line on what is still missing in the upload form: a way of requesting other than app, browser or Portability API cannot be recorded yet.
- For a platform that exists in the database but has no instructions: "No instructions for <Platform> yet."

**View:**

```python
def request_instructions(request: HttpRequest, slug: str) -> HttpResponse:
    """M8: how to request a data download package from one platform."""
    name, platform = find_platform(slug)
    context = {
        "slug": slug,
        "platform_name": name,
        "platform": platform,
        "instructions": INSTRUCTIONS.get(slug),
        "pair_hint": PAIR_HINT,
        "others": DEMO_PLATFORMS,
    }
    return render_mockup(request, "request", "journeys/prototype/request.html", context)
```

**Tests** (`tests/test_instructions.py`):

```python
"""M8, how to request a data download package: steps per platform, to be verified."""

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.ddps.models import Platform
from ddp_tracker.journeys.mockups.instructions import INSTRUCTIONS
from ddp_tracker.journeys.tests.utils import SeededTestCase


def page(slug):
    return reverse("journeys:request", args=[slug])


class InstructionsWithoutDataTests(TestCase):
    def test_every_demo_platform_has_steps(self):
        for slug, instructions in INSTRUCTIONS.items():
            with self.subTest(platform=slug):
                response = self.client.get(page(slug))
                self.assertContains(response, "<ol")
                for step in instructions.steps:
                    self.assertContains(response, step)
                self.assertContains(response, "To be verified by curators")
                self.assertContains(response, instructions.choose)

    def test_the_way_on(self):
        response = self.client.get(page("tiktok"))
        self.assertContains(response, "<h1>Request your data from TikTok</h1>", html=True)
        self.assertContains(response, f'href="{reverse("ddps:upload-create")}"')
        self.assertContains(response, reverse("docs", args=["guide/privacy/"]))
        self.assertContains(response, "Uploading needs an account")
        self.assertContains(response, "Request the same package twice")  # the pair hint
        for slug in INSTRUCTIONS:
            self.assertContains(response, page(slug))
        self.assertContains(response, 'aria-current="page"', count=1)

    def test_a_platform_without_instructions(self):
        Platform.objects.create(name="Spotify", slug="spotify")
        self.assertContains(self.client.get(page("spotify")), "No instructions for Spotify yet")


class InstructionsTests(SeededTestCase):
    def test_the_upload_form_opens_with_the_platform_chosen(self):
        tiktok = Platform.objects.get(slug="tiktok")
        upload = reverse("ddps:upload-create")
        self.assertContains(
            self.client.get(page("tiktok")), f'href="{upload}?platform={tiktok.pk}"'
        )
```

**Acceptance:** the tests pass; nothing on the page claims to be the platform's official instruction.

---

## Task 4.4: Moderator dashboard (M9)

**Review:** full.

**Files:** modify `mockups/moderate.py`; create `prototype/moderate.html`, `tests/test_moderate.py`.

**Consumes:** `ASSIGNED`, `HUB_NOTE`, `QUESTIONS`, `CONTRIBUTORS` (in the module); `find_platform`; `ddp_tracker.representations.eligibility.eligible`; `Proposal`, `Upload`.

**What the page shows:**

- "Your platforms" (`h2`), with one line: a moderator looks after one or more platforms (the assignment here is made up), and `HUB_NOTE`.
- Per assigned platform, a `proto-panel`. If the database has it, four queues, each a number with words and, where a page exists, a link:

  | Queue | Counted as | Link |
  |---|---|---|
  | Data points to triage (of how many) | data points of uploads that count, without an annotation and not marked "not a data point" | The explorer with `?show=annotations` (everyone) |
  | Suggestions to decide | open proposals of the platform | `proposals:annotations` with `?platform=<slug>` (staff only: for others the number without a link, and "staff only today") |
  | Uploads to approve | uploads of the platform that wait for approval | `ddps:approvals` (staff only, as above) |
  | Lists without a representation | list items that can have a representation and have none | The explorer with `?show=representations` (everyone) |

  And "Annotate next": the five open data points that occur in the most uploads, each with its path and "in N uploads". One line: in the real feature the order would also use how often researchers shortlist a data point.
- "Elsewhere" : how many uploads wait for approval on platforms that are not yours ("1 upload waits on a platform you do not moderate"). This shows what scoping a role to platforms means.
- A `proto-panel` "Seed annotations" with two sentences and a link to `journeys:seed`.
- "Questions from the community" (`h2`): `QUESTIONS`, each with its path in `<code>`, the question and "N answers". Fictional label.
- "Top contributors this month" (`h2`): `CONTRIBUTORS` as a small table (Account, Annotations, Uploads). Accounts are numbers. Fictional label.

**View:**

```python
def _queues(platform: Platform) -> dict[str, Any]:
    """What waits on a platform, counted as the explorer and the queues count it."""
    points = platform.locations.filter(
        observations__is_data_point=True, observations__upload__registered_at__isnull=False
    ).distinct()
    open_points = points.filter(annotation__isnull=True, ignored=False)
    lists = platform.locations.filter(path__endswith=ITEM, representations__isnull=True)
    return {
        "data_points": points.count(),
        "untriaged": open_points.count(),
        "suggestions": Proposal.objects.filter(
            platform=platform, status=Proposal.Status.OPEN
        ).count(),
        "approvals": platform.uploads.filter(plausibility=Upload.Plausibility.AWAITING).count(),
        "unrepresented": len(eligible(lists)),
        # the open data points that the most uploads have: annotate these first
        "next": list(
            open_points.annotate(seen=Count("observations__upload", distinct=True)).order_by(
                "-seen", "path"
            )[:5]
        ),
    }


def dashboard(request: HttpRequest) -> HttpResponse:
    """M9: what waits on the platforms a moderator looks after."""
    panels = []
    for slug in ASSIGNED:
        name, platform = find_platform(slug)
        panels.append(
            {
                "slug": slug,
                "name": name,
                "platform": platform,
                "queues": _queues(platform) if platform is not None else None,
            }
        )
    elsewhere = (
        Upload.objects.filter(plausibility=Upload.Plausibility.AWAITING)
        .exclude(platform__slug__in=ASSIGNED)
        .count()
    )
    context = {
        "panels": panels,
        "elsewhere": elsewhere,
        "hub_note": HUB_NOTE,
        "questions": QUESTIONS,
        "contributors": CONTRIBUTORS,
        "has_data": any(panel["platform"] is not None for panel in panels),
    }
    return render_mockup(request, "moderate", "journeys/prototype/moderate.html", context)
```

**Tests** (`tests/test_moderate.py`):

```python
"""M9, the moderator's dashboard: real queues of the platforms someone looks after."""

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.journeys.demo.spec import ADMIN_EMAIL
from ddp_tracker.journeys.tests.utils import SeededTestCase
from ddp_tracker.users.models import User

PAGE = reverse("journeys:moderate")


class DashboardWithoutDataTests(TestCase):
    def test_it_says_that_there_is_nothing_to_count(self):
        response = self.client.get(PAGE)
        self.assertContains(response, "seed_demo")
        self.assertTrue(all(panel["queues"] is None for panel in response.context["panels"]))
        self.assertContains(response, "IsFastLane")  # the community's questions are fictional


class DashboardTests(SeededTestCase):
    def queues(self, response, slug):
        return next(p["queues"] for p in response.context["panels"] if p["slug"] == slug)

    def test_the_queues_are_counted_from_the_database(self):
        response = self.client.get(PAGE)
        tiktok = self.queues(response, "tiktok")
        self.assertEqual(
            (
                tiktok["data_points"],
                tiktok["untriaged"],
                tiktok["suggestions"],
                tiktok["approvals"],
            ),
            (190, 177, 1, 0),
        )
        self.assertEqual(tiktok["unrepresented"], 17)
        self.assertEqual(len(tiktok["next"]), 5)
        self.assertEqual(tiktok["next"][0].seen, 2)  # in both TikTok packages
        self.assertGreater(self.queues(response, "instagram")["untriaged"], 100)
        # the held YouTube upload is not on "your" platforms
        self.assertEqual(response.context["elsewhere"], 1)
        self.assertContains(response, "a platform you do not moderate")

    def test_links_to_the_pages_that_exist(self):
        explorer = reverse("schemas:platform", args=["tiktok"])
        response = self.client.get(PAGE)
        self.assertContains(response, f"{explorer}?show=annotations")
        self.assertContains(response, f"{explorer}?show=representations")
        self.assertContains(response, reverse("journeys:seed"))
        # the staff queues are linked for staff only
        queue = reverse("proposals:annotations")
        self.assertNotContains(response, f'href="{queue}')
        self.assertContains(response, "staff only today")
        self.client.force_login(User.objects.get(email=ADMIN_EMAIL))
        response = self.client.get(PAGE)
        self.assertContains(response, f'href="{queue}?platform=tiktok"')
        self.assertContains(response, f'href="{reverse("ddps:approvals")}"')

    def test_people_are_numbers(self):
        response = self.client.get(PAGE)
        self.assertContains(response, "#12")
        self.assertNotContains(response, "@example.org")
```

**Acceptance:** the tests pass; the figures on the page equal what the explorer of TikTok says ("177 not yet assigned to an annotation" of 190 data points).

---

## Task 4.5: Seed annotations (M10)

**Review:** light.

**Files:** modify `mockups/seeding.py`; create `prototype/seed.html`, `tests/test_seeding.py`.

**Consumes:** everything in the module (`SOURCES`, `DOC_ENTRIES`, `PAIR_ROWS`, `AI_SUGGESTIONS` and the texts).

**What the page shows:**

- An introduction: annotating by hand is slow; three sources can give a first version that a person then checks.
- The three sources as tabs that are links (`nav nav-pills`, `?source=docs`, `?source=pairs`, `?source=ai`; the current one `active` with `aria-current="page"`). An unknown or missing `source` is `docs`.
- **Official documentation:** the platform (Facebook) and `DOC_SOURCE`. A summary line: "3 matched, 2 documented but not observed, 2 observed but not documented." A table in a `table-scroll`: "The documentation says" (the documented name and text, with `badge badge--official` "Official"), "Seen in uploads" (the path in `<code>`, cell `text-break`), "Status" (the label), and an action. For a matched row: a form with the button "Accept <documented name> as an official annotation". One sentence above the table: an official annotation is kept as its own kind, next to the curator's, so that the gap between what a platform says and what its packages contain stays visible.
- **Paired uploads:** `PAIR_TITLE`, "Differs in: Account language". A table: "First upload", "Second upload", "Why they match", and an action: where the first has an annotation, a form with the button "Carry <annotation> across".
- **AI suggestions:** `AI_NOTE`. A table: Data point, Suggested label, Why, Confidence, and the status "Needs a human check" on every row, with two buttons ("Accept <label>", "Reject <label>").
- Every form posts to the page itself with a hidden `source`, and the page answers as described at the top of this file.

**View:**

```python
def seed_sources(request: HttpRequest) -> HttpResponse:
    """M10: three sources for a first version of annotations, each to be checked by a person."""
    chosen = request.POST.get("source") or request.GET.get("source", "")
    source = chosen if chosen in dict(SOURCES) else DOCS
    if request.method == "POST":
        messages.info(
            request,
            "In the real feature, this would record your decision and create or update the "
            "annotation. Nothing was saved.",
        )
        return redirect(f"{reverse('journeys:seed')}?source={source}")
    statuses = Counter(entry.status for entry in DOC_ENTRIES)
    context = {
        "sources": SOURCES,
        "source": source,
        "doc_platform": DEMO_PLATFORMS[DOC_PLATFORM],
        "doc_source": DOC_SOURCE,
        "doc_entries": DOC_ENTRIES,
        "doc_summary": [(MATCH_LABELS[status], statuses[status]) for status in MATCH_LABELS],
        "pair_title": PAIR_TITLE,
        "pair_differs_in": PAIR_DIFFERS_IN,
        "pair_rows": PAIR_ROWS,
        "ai_suggestions": AI_SUGGESTIONS,
        "ai_note": AI_NOTE,
    }
    return render_mockup(request, "seed", "journeys/prototype/seed.html", context)
```

**Tests** (`tests/test_seeding.py`):

```python
"""M10, seeding annotations from documentation, paired uploads and AI suggestions."""

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.annotations.models import Annotation
from ddp_tracker.journeys.mockups.seeding import AI_SUGGESTIONS, DOC_ENTRIES, PAIR_ROWS
from ddp_tracker.journeys.tests.utils import SeededTestCase

PAGE = reverse("journeys:seed")


class SeedingPageTests(TestCase):
    def test_official_documentation_is_the_first_tab(self):
        for url in (PAGE, PAGE + "?source=docs", PAGE + "?source=nope"):
            response = self.client.get(url)
            self.assertEqual(response.context["source"], "docs")
            self.assertContains(response, "Documented but not observed")
            self.assertContains(response, "Observed but not documented")
        self.assertEqual(
            response.context["doc_summary"],
            [
                ("Matched", 3),
                ("Documented but not observed", 2),
                ("Observed but not documented", 2),
            ],
        )
        for entry in DOC_ENTRIES:
            self.assertContains(response, entry.documented or entry.path)
        self.assertContains(response, "fictional")
        self.assertContains(response, 'aria-current="page"', count=1)

    def test_paired_uploads(self):
        response = self.client.get(PAGE + "?source=pairs")
        self.assertContains(response, "Account language")
        for row in PAIR_ROWS:
            self.assertContains(response, row.right)
        self.assertContains(response, "Carry Watched video across")
        self.assertNotContains(response, "Documented but not observed")

    def test_ai_suggestions_wait_for_a_person(self):
        response = self.client.get(PAGE + "?source=ai")
        self.assertContains(response, "Needs a human check", count=len(AI_SUGGESTIONS))
        self.assertContains(response, "never shown to the public before a person has checked")


class SeedingActionsTests(SeededTestCase):
    def test_a_button_explains_and_saves_nothing(self):
        before = Annotation.objects.count()
        response = self.client.post(PAGE, {"source": "pairs"}, follow=True)
        self.assertRedirects(response, PAGE + "?source=pairs")
        self.assertContains(response, "In the real feature, this would")
        self.assertContains(response, "Nothing was saved.")
        self.assertEqual(Annotation.objects.count(), before)
```

**Acceptance:** the tests pass; every "official" text carries the fictional label once per table or section.

---

## Task 4.6: Roles and platforms (M11)

**Review:** light.

**Files:** modify `mockups/roles.py`; create `prototype/roles.html`, `tests/test_roles.py`.

**Consumes:** `ROLE_DEFINITIONS`, `PEOPLE`, `HUBS`, `EXAMPLE_RULE`, `EXAMPLE_RULE_NOTE` (in the module); `Platform`, `PathRule`.

**What the page shows:**

- "Roles" (`h2`, `id="roles"`): a table of the four roles (Role, May, The closest thing today). Then "People" as a table (Account, Role, Platforms; "All" where a role needs no platform): accounts are numbers; fictional label. Then "Hubs" as a table (Platform, Hub, Working group); fictional label. Two disabled-looking controls are not needed: one sentence says that in the real feature an administrator would change a role here.
- "Platforms" (`h2`, `id="platforms"`): the platforms of the database as a table (Platform, Uploads that count, Data points); on an empty database, the `seed_demo` note. Below it a form "Add a platform" (a text input named `name` with a label, a button "Add platform"): it posts to the page, which answers as described at the top of this file and redirects to `#platforms`.
- "Path rules" (`h3`): what a path rule is, in two sentences (the parser renames keys that are personal, such as a username in a chat's key; a rule tells it which). The rules of the database as a list (platform, kind, pattern in `<code>`); if there are none, `EXAMPLE_RULE` with `EXAMPLE_RULE_NOTE`, marked "an example".
- For staff only (`{% if user.is_staff %}`): "Today this is done in the Django admin" with links to `admin:ddps_platform_changelist` and `admin:ddps_pathrule_changelist`. For everyone else, the same sentence without links.

**View:**

```python
def roles(request: HttpRequest) -> HttpResponse:
    """M11: roles, hubs, platforms and path rules in one place."""
    if request.method == "POST":
        messages.info(
            request,
            "In the real feature, this would add the platform, after which people could "
            "upload its packages. Nothing was saved.",
        )
        return redirect(f"{reverse('journeys:roles')}#platforms")
    counted = Q(uploads__registered_at__isnull=False)
    platforms = Platform.objects.annotate(
        upload_count=Count("uploads", filter=counted, distinct=True),
        data_point_count=Count(
            "locations",
            filter=Q(
                locations__observations__is_data_point=True,
                locations__observations__upload__registered_at__isnull=False,
            ),
            distinct=True,
        ),
    )
    context = {
        "definitions": ROLE_DEFINITIONS,
        "people": PEOPLE,
        "hubs": HUBS,
        "platforms": platforms,
        "rules": PathRule.objects.select_related("platform"),
        "example_rule": EXAMPLE_RULE,
        "example_rule_note": EXAMPLE_RULE_NOTE,
    }
    return render_mockup(request, "roles", "journeys/prototype/roles.html", context)
```

(The two counts are those of the Explore page, `schemas.views.platform_list`.)

**Tests** (`tests/test_roles.py`):

```python
"""M11, roles and platforms: who may do what, where, without the Django admin."""

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.ddps.models import PathRule, Platform
from ddp_tracker.journeys.demo.spec import ADMIN_EMAIL
from ddp_tracker.journeys.mockups.roles import EXAMPLE_RULE, ROLE_DEFINITIONS
from ddp_tracker.journeys.tests.utils import SeededTestCase
from ddp_tracker.users.models import User

PAGE = reverse("journeys:roles")


class RolesWithoutDataTests(TestCase):
    def test_roles_people_and_hubs(self):
        response = self.client.get(PAGE)
        for anchor in ('id="roles"', 'id="platforms"'):  # the administrator's journey links here
            self.assertContains(response, anchor)
        for definition in ROLE_DEFINITIONS:
            self.assertContains(response, definition.name)
        self.assertContains(response, "#7")
        self.assertContains(response, "Short video working group")
        self.assertNotContains(response, "@example.org")

    def test_an_example_rule_when_there_is_none(self):
        response = self.client.get(PAGE)
        self.assertContains(response, EXAMPLE_RULE)
        self.assertContains(response, "an example")
        self.assertContains(response, "seed_demo")


class RolesTests(SeededTestCase):
    def test_the_platforms_and_rules_are_the_databases(self):
        tiktok = Platform.objects.get(slug="tiktok")
        PathRule.objects.create(platform=tiktok, pattern="/user_data_tiktok.json/Some/Key *")
        response = self.client.get(PAGE)
        counts = {
            p.slug: (p.upload_count, p.data_point_count) for p in response.context["platforms"]
        }
        self.assertEqual(counts["tiktok"], (2, 190))
        self.assertEqual(counts["youtube"], (0, 0))
        self.assertContains(response, "/user_data_tiktok.json/Some/Key *")
        self.assertNotContains(response, EXAMPLE_RULE)

    def test_adding_a_platform_explains_and_saves_nothing(self):
        before = Platform.objects.count()
        response = self.client.post(PAGE, {"name": "Spotify"}, follow=True)
        self.assertContains(response, "In the real feature, this would add the platform")
        self.assertEqual(Platform.objects.count(), before)

    def test_only_staff_get_links_to_the_admin(self):
        admin = reverse("admin:ddps_platform_changelist")
        self.assertNotContains(self.client.get(PAGE), admin)
        self.client.force_login(User.objects.get(email=ADMIN_EMAIL))
        response = self.client.get(PAGE)
        self.assertContains(response, admin)
        self.assertContains(response, reverse("admin:ddps_pathrule_changelist"))
```

**Acceptance:** the tests pass; no real person or institution is named.

---

## Task 4.7: What a platform keeps about you (M12)

**Review:** light.

**Files:** modify `mockups/learn.py`; create `prototype/learn.html`, `tests/test_learn.py`.

**Consumes:** `CATEGORIES`, `EXPLAINED`, `QUIZ` (in the module); `find_platform`; `Annotation`, `Location`.

**What the page shows:**

- Heading: "What <Platform> keeps about you". An introduction in plain words: when you ask a platform for your data, you get a package; this page says what kinds of information are in it, without the technical detail.
- The categories as `proto-panel`s in `proto-columns`: name (`h2`), text, and, from the database, "N kinds of information" (the data points under the category's paths). Without data: the text alone, and the `seed_demo` note once.
- "One example, looked at closely" (`h2`): the annotation `EXPLAINED[slug]` from the database: its name, its description, a table Title and Value of the example values below it ("Fictional values"), and a link to the explorer (`?q=` with the list's key). Without data: left out.
- "Try it yourself" (`h2`, `id="exercise"`): `QUIZ` inside `<div class="quiz">`, each question a `<details>` with the question in `<summary>` and the answer in a `<p>`. One line: click a question to see the answer.
- "For teachers and study designers" (`h2`): these explanations could also reach donation tools through the API (link to `journeys:api` with `#explainers`); link to the user guide (`docs`).
- Links to the other platforms that have a summary.
- A platform without categories (YouTube, or any other platform of the database): "No summary for <Platform> yet." and the exercise.

**View:**

```python
def _count(platform: Platform, category: Category) -> int:
    """How many data points of uploads that count lie under the category's paths."""
    under = Q()
    for prefix in category.prefixes:
        under |= Q(path__startswith=prefix)
    return (
        platform.locations.filter(
            under,
            observations__is_data_point=True,
            observations__upload__registered_at__isnull=False,
        )
        .distinct()
        .count()
    )


def _explained(platform: Platform, name: str) -> dict[str, Any] | None:
    """One annotation with the example values below its location in use now."""
    annotation = Annotation.objects.filter(platform=platform, name=name).first()
    if annotation is None:
        return None
    location = annotation.locations.order_by("-pk").first()
    if location is None:
        return None
    below = (
        Location.objects.filter(platform=platform, path__startswith=f"{location.path}/")
        .exclude(example_values=[])
        .order_by("position", "path")
    )
    return {
        "annotation": annotation,
        "location": location,
        "search": next(part for part in reversed(location.path.split("/")) if part != "[]"),
        "examples": [
            (entry.path.removeprefix(f"{location.path}/"), entry.example_values[0]["value"])
            for entry in below
        ],
    }


def learn(request: HttpRequest, slug: str) -> HttpResponse:
    """M12: a plain summary of a platform's package, one example, and a short exercise."""
    name, platform = find_platform(slug)
    categories = [
        (category, _count(platform, category) if platform is not None else None)
        for category in CATEGORIES.get(slug, ())
    ]
    context = {
        "slug": slug,
        "platform_name": name,
        "platform": platform,
        "categories": categories,
        "explained": (
            _explained(platform, EXPLAINED[slug])
            if platform is not None and slug in EXPLAINED
            else None
        ),
        "quiz": QUIZ,
        "others": [(other, DEMO_PLATFORMS[other]) for other in CATEGORIES if other != slug],
    }
    return render_mockup(request, "learn", "journeys/prototype/learn.html", context)
```

"The location in use now": for "Watched video" the annotation has two locations; the one created last is the September path, hence `order_by("-pk")`. If you prefer, reuse `resolve` of `mockups/concepts.py` instead, whose first location is the one seen last.

**Tests** (`tests/test_learn.py`):

```python
"""M12, for learners: what a platform keeps about you, one example, a short exercise."""

from django.test import TestCase
from django.urls import reverse

from ddp_tracker.journeys.mockups.learn import CATEGORIES, QUIZ
from ddp_tracker.journeys.tests.utils import SeededTestCase


def page(slug):
    return reverse("journeys:learn", args=[slug])


class LearnWithoutDataTests(TestCase):
    def test_the_categories_and_the_exercise_need_no_data(self):
        response = self.client.get(page("tiktok"))
        self.assertContains(response, "<h1>What TikTok keeps about you</h1>", html=True)
        for category in CATEGORIES["tiktok"]:
            self.assertContains(response, category.name)
        self.assertContains(response, "seed_demo")
        self.assertContains(response, 'id="exercise"')
        self.assertContains(response, "<details", count=len(QUIZ))
        self.assertNotContains(response, "kinds of information")


class LearnTests(SeededTestCase):
    def test_categories_are_counted(self):
        response = self.client.get(page("tiktok"))
        counts = {category.name: count for category, count in response.context["categories"]}
        self.assertEqual(counts["Your messages"], 5)
        self.assertEqual(counts["Your profile and connections"], 55)
        self.assertGreater(counts["What you did"], 40)
        self.assertContains(response, "5 kinds of information")

    def test_one_example_looked_at_closely(self):
        response = self.client.get(page("tiktok"))
        explained = response.context["explained"]
        self.assertEqual(explained["annotation"].name, "Watched video")
        self.assertEqual(explained["examples"][0], ("Date", "2026-09-01 08:15:42"))
        self.assertContains(response, "One video that was shown to the user")
        explorer = reverse("schemas:platform", args=["tiktok"])
        self.assertContains(response, f'href="{explorer}?q=VideoList"')

    def test_it_points_teachers_to_the_explainers(self):
        response = self.client.get(page("instagram"))
        self.assertContains(response, reverse("journeys:api") + "#explainers")
        self.assertContains(response, page("facebook"))

    def test_a_platform_without_a_summary(self):
        response = self.client.get(page("youtube"))
        self.assertContains(response, "No summary for YouTube yet")
        self.assertContains(response, 'id="exercise"')
```

**Acceptance:** the tests pass; a reader who has never seen a file tree can follow the page.

---

## Task 4.8: Feature cards page

**Review:** light.

**Files:** modify `ddp_tracker/journeys/templates/journeys/features.html` (replace the list of titles); create `tests/test_feature_cards.py`. `feature_cards.py` and the view exist.

**What the page shows:**

- Heading "Feature cards". An introduction: planned features of the infrastructure track, in the template of the hackathon document, so that they can be compared with and pasted into it; each links to where the prototype shows it. A line: "Proposals for discussion, not decisions."
- A table of contents (the titles, linking to the cards).
- Per card an `<article class="proto-panel" id="<slug>">`: the title (`h2`); a `badge` "In the hackathon document" where `from_hackathon_document`; a table with the five rows of the template, the labels in `<th scope="row">`: Title, Problem, Description of solution, User group, Technical implementation; and a link "See it in the prototype: <see_label>" to `card.see_url`.
- At the bottom: a link back to the landing page and to the journeys.

This is a page of the app, not a mock-up: it does not extend `prototype/base.html` and has no banner.

**Tests** (`tests/test_feature_cards.py`):

```python
"""The planned features as feature cards, in the hackathon's template."""

from urllib.parse import urlsplit

from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse
from django.utils.html import escape

from ddp_tracker.journeys.feature_cards import CARDS

PAGE = reverse("journeys:features")


class FeatureCardDataTests(SimpleTestCase):
    def test_every_card_is_complete_and_leads_somewhere(self):
        self.assertEqual(len({card.slug for card in CARDS}), len(CARDS))
        for card in CARDS:
            with self.subTest(card=card.slug):
                for text in (
                    card.title,
                    card.problem,
                    card.solution,
                    card.user_group,
                    card.technical,
                ):
                    self.assertTrue(text)
                    self.assertNotIn(chr(0x2014), text)  # no em dash
                resolve(urlsplit(card.see_url).path)


class FeatureCardPageTests(TestCase):
    def test_the_cards_follow_the_template(self):
        response = self.client.get(PAGE)
        self.assertContains(response, "<h1>Feature cards</h1>", html=True)
        for label in (
            "Problem",
            "Description of solution",
            "User group",
            "Technical implementation",
        ):
            self.assertContains(
                response, f'<th scope="row">{label}</th>', count=len(CARDS), html=True
            )
        for card in CARDS:
            with self.subTest(card=card.slug):
                self.assertContains(response, f'id="{card.slug}"')
                self.assertContains(response, escape(card.title))
                self.assertContains(response, f'href="{escape(card.see_url)}"')
        self.assertContains(response, "In the hackathon document", count=2)
        self.assertContains(response, "Proposals for discussion")

    def test_it_is_reached_from_the_landing_page_and_the_journeys(self):
        self.assertContains(self.client.get("/"), f'href="{PAGE}"')
        journey = reverse("journeys:journey", args=["researcher"])
        self.assertContains(self.client.get(journey), f'href="{PAGE}"')
```

Commit: `feat(journeys): add the feature cards page`.

**Acceptance:** the tests pass; the page has no banner and exactly one `h1`.

---

## Task 4.9: Screenshots and check-in (coordinator)

- [ ] Fresh database, seed, server, screenshots tool. No PROBLEM lines.
- [ ] Walk **every** journey by hand, step by step, once signed out and once as the demo admin (the curator's and the administrator's journeys as the admin). Note every link that does not land where the step says, and have it fixed.
- [ ] Log in as `demo-curator@example.org` and walk the contributor's journey: step 4 must offer "Inspect the held demo upload".
- [ ] Phase gate.
- [ ] Check in with Hekmat. Show the seven pages and the feature cards. Ask the one question, and: which of the mock-ups, if any, should be shown first at the hackathon (so that Phase 5's polish goes there first).
