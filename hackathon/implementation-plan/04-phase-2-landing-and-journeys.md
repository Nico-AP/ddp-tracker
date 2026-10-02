# 04. Phase 2: landing page, journeys, navigation

Output: `/` is the role picker, every role has its journey, every step leads somewhere (a page that exists, or a mock-up page that for now is a placeholder with the banner), the navigation shows it all, and the styles are in place. Two subagent tasks, then the first check-in.

---

## Task 2.1: Journeys, routes and scaffolding

**Review:** full.

**Files:**

- Create (copy from `starter-files/ddp_tracker/journeys/`): `content.py`, `feature_cards.py`, and the whole folder `mockups/` (twelve modules)
- Create: `ddp_tracker/journeys/targets.py`
- Create: `ddp_tracker/journeys/views.py`
- Create: `ddp_tracker/journeys/urls.py`
- Create, in `ddp_tracker/journeys/templates/journeys/`: `index.html`, `journey.html`, `_step.html`, `features.html`, `_prototype_banner.html`, `prototype/base.html`, `prototype/placeholder.html`
- Create, in `ddp_tracker/journeys/tests/`: `test_content.py`, `test_views.py`, `test_mockups.py`, `test_conventions.py`
- Modify: `config/urls.py` (one line), `ddp_tracker/core/urls.py` (one line), `config/settings/base.py` (two lines)

**Interfaces:**

- Consumes: `SeededTestCase` from `ddp_tracker/journeys/tests/utils.py` (task 1.2); the demo data's names (the annotation "Watched video" on TikTok, the held YouTube upload).
- Produces: everything in `01-design.md`, sections 5.1 to 5.4. After this task every URL name of the app exists and answers, so later tasks only replace a placeholder view, add a template and add tests.

**What the copied files are.** `content.py` holds the eight journeys as data. `mockups/__init__.py` holds the registry of the twelve mock-up pages and the helpers `render_mockup` and `find_platform`. Each other module in `mockups/` holds the fictional data of one page and, at the bottom, a **placeholder view** that renders `journeys/prototype/placeholder.html`. `feature_cards.py` holds the hackathon feature cards. All were linted and type-checked against this repository. Read `content.py` and `mockups/__init__.py` before you start.

- [ ] **Step 1: Copy the starter files**

  ```bash
  P="/c/Users/hekma/Documents/Projects/DDP-Tracker-docs/implementation-plan/starter-files/ddp_tracker/journeys"
  cp "$P/content.py" "$P/feature_cards.py" ddp_tracker/journeys/
  cp -r "$P/mockups" ddp_tracker/journeys/
  mkdir -p ddp_tracker/journeys/templates/journeys/prototype
  ```

- [ ] **Step 2: Write the failing tests**

  `ddp_tracker/journeys/tests/test_content.py`:

  ```python
  """The journeys as data (content.py): complete, well formed, and every link leads somewhere."""

  from urllib.parse import urlsplit

  from django.test import SimpleTestCase
  from django.urls import resolve

  from ddp_tracker.journeys.content import (
      AVAILABLE,
      FEATURE_STATUSES,
      NEEDS,
      PROTOTYPE,
      ROLES,
      ROLES_BY_SLUG,
      STATUSES,
  )
  from ddp_tracker.journeys.targets import DEMO_LINK_KEYS


  class ContentTests(SimpleTestCase):
      def test_the_eight_roles_in_order(self):
          self.assertEqual(
              [role.slug for role in ROLES],
              [
                  "researcher",
                  "engineer",
                  "policy",
                  "contributor",
                  "curator",
                  "admin",
                  "machine",
                  "learner",
              ],
          )
          self.assertEqual(set(ROLES_BY_SLUG), {role.slug for role in ROLES})

      def test_a_journey_has_three_to_five_steps(self):
          for role in ROLES:
              with self.subTest(role=role.slug):
                  self.assertGreaterEqual(len(role.steps), 3)
                  self.assertLessEqual(len(role.steps), 5)
                  self.assertEqual(role.available_count + role.prototype_count, len(role.steps))

      def test_steps_are_well_formed(self):
          for role in ROLES:
              for step in role.steps:
                  with self.subTest(role=role.slug, step=step.title):
                      self.assertIn(step.status, STATUSES)
                      self.assertIn(step.needs, NEEDS)
                      self.assertIn(step.demo_link, ("", *DEMO_LINK_KEYS))
                      self.assertTrue(step.title and step.text and step.link_label)
                      # a prototype step leads to a mock-up, an available one to a page that exists
                      is_mockup = step.url_name.startswith("journeys:")
                      self.assertEqual(is_mockup, step.status == PROTOTYPE)
                      # a "today" link comes with its label, and only on prototype steps
                      self.assertEqual(bool(step.today_url_name), bool(step.today_label))
                      if step.today_url_name:
                          self.assertEqual(step.status, PROTOTYPE)

      def test_every_link_leads_somewhere(self):
          for role in ROLES:
              for step in role.steps:
                  with self.subTest(role=role.slug, step=step.title):
                      resolve(urlsplit(step.url).path)  # raises Resolver404 if nothing is there
                      if step.today_url:
                          resolve(urlsplit(step.today_url).path)

      def test_link_texts_make_sense_out_of_context(self):
          for role in ROLES:
              labels = [step.link_label for step in role.steps]
              with self.subTest(role=role.slug):
                  self.assertEqual(len(labels), len(set(labels)))  # no two links read the same
                  for label in labels:
                      self.assertGreater(len(label.split()), 2, label)  # not "Go" or "Open it"

      def test_both_kinds_of_step_occur(self):
          statuses = {step.status for role in ROLES for step in role.steps}
          self.assertEqual(statuses, {AVAILABLE, PROTOTYPE})

      def test_features_have_a_known_status(self):
          for role in ROLES:
              self.assertTrue(role.features, role.slug)
              for feature in role.features:
                  self.assertIn(feature.status, FEATURE_STATUSES)

      def test_the_texts_have_no_em_dash(self):
          for role in ROLES:
              for thing in (role, *role.steps, *role.features):
                  for name, value in vars(thing).items():
                      if isinstance(value, str):
                          self.assertNotIn("\u2014", value, f"{role.slug}: {name}")
  ```

  `ddp_tracker/journeys/tests/test_views.py`:

  ```python
  """The landing page (pick a role) and the journey pages."""

  from django.conf import settings
  from django.shortcuts import resolve_url
  from django.test import TestCase
  from django.urls import reverse
  from django.utils.html import escape  # pages escape apostrophes: compare with escaped text

  from ddp_tracker.journeys.content import ROLES, ROLES_BY_SLUG
  from ddp_tracker.journeys.demo.spec import ADMIN_EMAIL, CURATOR_EMAIL
  from ddp_tracker.journeys.tests.utils import SeededTestCase
  from ddp_tracker.users.models import User

  NO_DATA = "This database has no demo data yet"


  def journey_url(slug):
      return reverse("journeys:journey", args=[slug])


  class LandingPageTests(TestCase):
      def test_the_home_page_is_the_role_picker(self):
          response = self.client.get("/")
          self.assertEqual(response.status_code, 200)
          self.assertTemplateUsed(response, "journeys/index.html")
          self.assertEqual(reverse("journeys:index"), "/")
          self.assertContains(response, "<h1>DDP Tracker</h1>", html=True)
          self.assertContains(response, "What brings you here?")
          for role in ROLES:
              with self.subTest(role=role.slug):
                  self.assertContains(response, f'href="{journey_url(role.slug)}"')
                  self.assertContains(response, escape(f"I want to {role.card_line}."))

      def test_a_card_says_how_much_works_today(self):
          # the research engineer: two steps on pages that exist, three on mock-ups
          self.assertContains(
              self.client.get("/"),
              '<p class="card__hint role-card__meta">5 steps: 2 available today, 3 prototype</p>',
              html=True,
          )

      def test_it_works_for_everyone(self):
          for user in (
              None,
              User.objects.create_user("someone@example.org"),
              User.objects.create_user("staff@example.org", is_staff=True),
          ):
              if user is not None:
                  self.client.force_login(user)
              self.assertEqual(self.client.get("/").status_code, 200)

      def test_an_empty_tracker_counts_nothing(self):
          response = self.client.get("/")
          self.assertEqual(
              response.context["counts"],
              [("Platforms", 0), ("Uploads", 0), ("Data points", 0), ("Annotations", 0)],
          )

      def test_the_previous_home_page_is_the_overview(self):
          self.assertEqual(reverse("core:index"), "/overview/")
          response = self.client.get("/overview/")
          self.assertTemplateUsed(response, "core/index.html")
          self.assertContains(self.client.get("/"), 'href="/overview/"')

      def test_logging_in_and_out_leads_home(self):
          self.assertEqual(resolve_url(settings.LOGIN_REDIRECT_URL), "/")
          self.assertEqual(resolve_url(settings.LOGOUT_REDIRECT_URL), "/")


  class SeededLandingPageTests(SeededTestCase):
      def test_the_figures_are_counted(self):
          counts = dict(self.client.get("/").context["counts"])
          # the held YouTube upload does not count
          self.assertEqual(
              (counts["Platforms"], counts["Uploads"], counts["Annotations"]), (4, 4, 28)
          )
          self.assertGreater(counts["Data points"], 500)


  class JourneyPageTests(TestCase):
      def test_every_journey_shows_its_aim_and_steps(self):
          for role in ROLES:
              with self.subTest(role=role.slug):
                  response = self.client.get(journey_url(role.slug))
                  self.assertEqual(response.status_code, 200)
                  self.assertContains(response, f"<h1>{role.name}</h1>", html=True)
                  self.assertContains(response, escape(role.aim))
                  self.assertContains(response, escape(role.audience))
                  for step in role.steps:
                      self.assertContains(response, escape(step.title))
                      self.assertContains(response, escape(step.link_label))
                  self.assertContains(response, "badge--available", count=role.available_count)
                  self.assertContains(response, "badge--prototype", count=role.prototype_count)

      def test_a_step_says_what_it_needs_and_what_is_missing(self):
          response = self.client.get(journey_url("contributor"))
          self.assertContains(response, "Needs an account", count=3)
          self.assertContains(response, "Still missing:")
          self.assertContains(self.client.get(journey_url("curator")), "Staff only today")

      def test_a_prototype_step_can_name_the_page_that_exists_today(self):
          response = self.client.get(journey_url("researcher"))
          today = reverse("annotations:annotations", args=["tiktok"])
          self.assertContains(response, f'href="{today}"')
          self.assertContains(response, "Today: TikTok&#x27;s annotations")

      def test_the_features_a_journey_needs(self):
          response = self.client.get(journey_url("engineer"))
          self.assertContains(response, "Features this journey needs")
          for feature in ROLES_BY_SLUG["engineer"].features:
              self.assertContains(response, escape(feature.title))
          for label, css in (("Exists", "exists"), ("Partial", "partial"), ("Gap", "gap")):
              self.assertContains(
                  response, f'<span class="badge badge--{css}">{label}</span>', html=True
              )
          self.assertContains(response, "raised at the hackathon")

      def test_the_other_journeys_are_one_click_away(self):
          response = self.client.get(journey_url("policy"))
          for role in ROLES:
              if role.slug != "policy":
                  self.assertContains(response, f'href="{journey_url(role.slug)}"')

      def test_an_unknown_role_is_not_found(self):
          self.assertEqual(self.client.get(journey_url("nobody")).status_code, 404)

      def test_without_demo_data_the_page_says_so(self):
          self.assertContains(self.client.get(journey_url("engineer")), NO_DATA)


  class SeededJourneyPageTests(SeededTestCase):
      def test_with_demo_data_there_is_no_notice(self):
          self.assertNotContains(self.client.get(journey_url("engineer")), NO_DATA)

      def test_everyone_gets_the_public_demo_link(self):
          response = self.client.get(journey_url("researcher"))
          self.assertContains(response, "Read TikTok&#x27;s annotation Watched video")

      def test_staff_get_the_review_of_the_demo_upload(self):
          review = "Open the review of the demo TikTok upload"
          self.assertNotContains(self.client.get(journey_url("engineer")), review)
          self.client.force_login(User.objects.get(email=ADMIN_EMAIL))
          response = self.client.get(journey_url("engineer"))
          self.assertContains(response, review)
          # and the link works
          url = response.content.decode().split(review)[0].rsplit('href="', 1)[1].split('"')[0]
          self.assertEqual(self.client.get(url).status_code, 200)

      def test_an_uploader_gets_their_held_upload(self):
          held = "Inspect the held demo upload"
          self.assertNotContains(self.client.get(journey_url("contributor")), held)
          self.client.force_login(User.objects.get(email=CURATOR_EMAIL))
          response = self.client.get(journey_url("contributor"))
          self.assertContains(response, held)
          url = response.content.decode().split(held)[0].rsplit('href="', 1)[1].split('"')[0]
          self.assertEqual(self.client.get(url).status_code, 200)
          # the curator's uploads are their own: no review of the admin's TikTok upload
          self.assertNotContains(response, "Open the review of the demo TikTok upload")
  ```

  `ddp_tracker/journeys/tests/test_mockups.py`:

  ```python
  """Every mock-up page: there, for everyone, with the banner, and part of a journey. What each
  page shows has its own test file."""

  from django.test import SimpleTestCase, TestCase
  from django.urls import reverse

  from ddp_tracker.journeys.mockups import MOCKUPS, find_platform, roles_using
  from ddp_tracker.journeys.tests.utils import SeededTestCase
  from ddp_tracker.users.models import User

  BANNER = (
      "Prototype: this page shows fictional data to illustrate a planned feature. "
      "It does not work yet."
  )


  def mockup_urls():
      """A URL of every mock-up page, by its key in ``MOCKUPS``."""
      return {
          "concepts": reverse("journeys:concepts"),
          "concept": reverse("journeys:concept", args=["watched-video"]),
          "shortlist": reverse("journeys:shortlist"),
          "compare": reverse("journeys:compare"),
          "changes": reverse("journeys:changes", args=["tiktok"]),
          "api": reverse("journeys:api"),
          "snapshots": reverse("journeys:snapshots"),
          "request": reverse("journeys:request", args=["tiktok"]),
          "moderate": reverse("journeys:moderate"),
          "seed": reverse("journeys:seed"),
          "roles": reverse("journeys:roles"),
          "learn": reverse("journeys:learn", args=["tiktok"]),
      }


  class RegistryTests(SimpleTestCase):
      def test_the_twelve_mockups(self):
          self.assertEqual(set(MOCKUPS), set(mockup_urls()))
          self.assertEqual(
              sorted(mockup.number for mockup in MOCKUPS.values()),
              sorted(f"M{number}" for number in range(1, 13)),
          )

      def test_every_mockup_is_reached_from_a_journey(self):
          for mockup in MOCKUPS.values():
              with self.subTest(mockup=mockup.key):
                  self.assertTrue(roles_using(mockup))

      def test_their_url_names_exist(self):
          for mockup in MOCKUPS.values():
              for name in mockup.url_names:
                  with self.subTest(name=name):
                      args = {"journeys:concept": ["x"]}.get(name) or (
                          ["tiktok"]
                          if name in {"journeys:changes", "journeys:request", "journeys:learn"}
                          else []
                      )
                      self.assertTrue(reverse(name, args=args).startswith("/prototype/"))


  def check_every_page(case: TestCase) -> None:
      """Every page answers 200 with the banner, one heading, and where it fits, whoever asks."""
      visitors = {
          "signed out": None,
          "signed in": User.objects.create_user("someone@example.org"),
          "staff": User.objects.create_user("staff@example.org", is_staff=True),
      }
      for who, user in visitors.items():
          if user is not None:
              case.client.force_login(user)
          for key, url in mockup_urls().items():
              with case.subTest(who=who, page=key):
                  response = case.client.get(url)
                  case.assertEqual(response.status_code, 200)
                  case.assertContains(response, BANNER)
                  case.assertContains(response, "<h1", count=1)
                  case.assertContains(response, "Where this fits")
                  for role in roles_using(MOCKUPS[key]):
                      journey = reverse("journeys:journey", args=[role.slug])
                      case.assertContains(response, f'href="{journey}"')


  class EmptyDatabaseTests(TestCase):
      def test_every_page_answers_for_everyone(self):
          check_every_page(self)

      def test_a_demo_platform_is_known_before_seeding(self):
          self.assertEqual(find_platform("tiktok"), ("TikTok", None))

      def test_an_unknown_platform_is_not_found(self):
          for name in ("journeys:changes", "journeys:request", "journeys:learn"):
              with self.subTest(name=name):
                  self.assertEqual(self.client.get(reverse(name, args=["nope"])).status_code, 404)


  class SeededDatabaseTests(SeededTestCase):
      def test_every_page_answers_for_everyone(self):
          check_every_page(self)

      def test_a_seeded_platform_is_found(self):
          name, platform = find_platform("tiktok")
          assert platform is not None
          self.assertEqual((name, platform.slug), ("TikTok", "tiktok"))
  ```

  Later tasks add their own checks to their own test files; they leave this file alone, except that a task whose page gains a required query or a changed URL updates `mockup_urls()`.

  `ddp_tracker/journeys/tests/test_conventions.py`:

  ```python
  """Rules that production enforces and local development does not (the content security policy
  allows no inline style or script), and the project's writing rules: checked on this app's
  templates and sources, so that a slip shows up in the tests and not on the live site."""

  import re
  from pathlib import Path

  from django.test import SimpleTestCase

  APP = Path(__file__).resolve().parent.parent
  TEMPLATES = sorted((APP / "templates").rglob("*.html"))
  SOURCES = sorted(APP.rglob("*.py"))
  EM_DASH = "\u2014"
  SIZES = {"btn-sm", "btn-lg"}


  def templates():
      return [(path.name, path.read_text(encoding="utf-8")) for path in TEMPLATES]


  class ConventionsTests(SimpleTestCase):
      def test_there_are_templates_to_check(self):
          self.assertTrue(TEMPLATES)

      def test_no_inline_styles(self):
          for name, text in templates():
              with self.subTest(template=name):
                  self.assertNotRegex(text, r"\sstyle\s*=")
                  self.assertNotIn("<style", text)

      def test_scripts_are_files(self):
          for name, text in templates():
              with self.subTest(template=name):
                  for tag in re.findall(r"<script\b[^>]*>", text):
                      self.assertIn("src=", tag)

      def test_no_inline_event_handlers(self):
          for name, text in templates():
              with self.subTest(template=name):
                  self.assertNotRegex(text, r"\son[a-z]+\s*=\s*[\"']")

      def test_buttons_name_a_variant(self):
          for name, text in templates():
              with self.subTest(template=name):
                  for classes in re.findall(r'class="([^"]*)"', text):
                      names = classes.split()
                      if "btn" in names:
                          variants = [n for n in names if n.startswith("btn-") and n not in SIZES]
                          self.assertTrue(variants, classes)

      def test_no_user_e_mail_addresses(self):
          for name, text in templates():
              with self.subTest(template=name):
                  self.assertNotIn(".email", text)

      def test_no_em_dash(self):
          for path in [*TEMPLATES, *SOURCES]:
              with self.subTest(file=path.name):
                  self.assertNotIn(EM_DASH, path.read_text(encoding="utf-8"))
  ```

- [ ] **Step 3: Run the tests and see them fail**

  ```bash
  DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest ddp_tracker/journeys/tests -q -p no:sugar --no-cov -x
  ```

  Expected: an import error (`No module named 'ddp_tracker.journeys.targets'`).

- [ ] **Step 4: Write `targets.py`**

  ```python
  """Links from journey steps into the demo data (``manage.py seed_demo``): the review of the
  demo upload, a held upload to inspect, an annotation. A link only exists if the data does and
  the visitor may open it; otherwise the step simply does not show it.
  """

  from collections.abc import Callable
  from dataclasses import dataclass

  from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
  from django.urls import reverse

  from ddp_tracker.annotations.models import Annotation
  from ddp_tracker.ddps.models import Upload

  type Visitor = AbstractBaseUser | AnonymousUser


  @dataclass(frozen=True)
  class DemoLink:
      label: str
      url: str


  def _tiktok_review(user: Visitor) -> DemoLink | None:
      """The review of the latest TikTok upload that counts: for its uploader and staff."""
      upload = (
          Upload.objects.visible_to(user)
          .filter(platform__slug="tiktok", registered_at__isnull=False)
          .order_by("-requested_at")
          .first()
      )
      if upload is None:
          return None
      url = reverse("reviews:review", args=[upload.pk])
      return DemoLink("Open the review of the demo TikTok upload", url)


  def _held_upload(user: Visitor) -> DemoLink | None:
      """An upload that waits for approval: for its uploader and staff to inspect."""
      upload = (
          Upload.objects.visible_to(user)
          .filter(
              plausibility=Upload.Plausibility.AWAITING,
              document__isnull=False,
              registered_at__isnull=True,
          )
          .order_by("created_at")
          .first()
      )
      if upload is None:
          return None
      url = reverse("ddps:upload-inspect", args=[upload.pk])
      return DemoLink("Inspect the held demo upload", url)


  def _watched_video(user: Visitor) -> DemoLink | None:
      """TikTok's annotation of a watched video (public)."""
      annotation = Annotation.objects.filter(platform__slug="tiktok", name="Watched video").first()
      if annotation is None:
          return None
      return DemoLink("Read TikTok's annotation Watched video", annotation.get_absolute_url())


  _LINKS: dict[str, Callable[[Visitor], DemoLink | None]] = {
      "tiktok-review": _tiktok_review,
      "held-upload": _held_upload,
      "watched-video": _watched_video,
  }
  DEMO_LINK_KEYS = tuple(_LINKS)


  def demo_link(key: str, user: Visitor) -> DemoLink | None:
      """The demo link ``key`` for ``user``, if there is one to show ("" means the step has none)."""
      return _LINKS[key](user) if key else None
  ```

- [ ] **Step 5: Write `views.py`**

  ```python
  """The landing page (pick a role), a journey per role, and the feature cards. The mock-up pages
  that journeys lead to are in ``mockups``."""

  from django.http import Http404, HttpRequest, HttpResponse
  from django.shortcuts import render

  from ddp_tracker.annotations.models import Annotation
  from ddp_tracker.ddps.models import Platform, Upload
  from ddp_tracker.journeys.content import ROLES, ROLES_BY_SLUG
  from ddp_tracker.journeys.feature_cards import CARDS
  from ddp_tracker.journeys.targets import demo_link
  from ddp_tracker.schemas.models import Observation


  def index(request: HttpRequest) -> HttpResponse:
      """What brings you here? The eight roles, how the tracker works, and what it holds today
      (only uploads that count: registered)."""
      points = Observation.objects.filter(is_data_point=True, upload__registered_at__isnull=False)
      counts = [
          ("Platforms", Platform.objects.count()),
          ("Uploads", Upload.objects.filter(registered_at__isnull=False).count()),
          ("Data points", points.values("location").distinct().count()),
          ("Annotations", Annotation.objects.count()),
      ]
      return render(request, "journeys/index.html", {"roles": ROLES, "counts": counts})


  def journey(request: HttpRequest, role: str) -> HttpResponse:
      """One role's journey: its aim, its steps (each with its links) and the features it needs."""
      found = ROLES_BY_SLUG.get(role)
      if found is None:
          raise Http404
      context = {
          "role": found,
          "steps": [(step, demo_link(step.demo_link, request.user)) for step in found.steps],
          "others": [other for other in ROLES if other != found],
          # several steps link to TikTok's pages: they need the demo data (manage.py seed_demo)
          "has_demo_data": Upload.objects.filter(
              platform__slug="tiktok", registered_at__isnull=False
          ).exists(),
      }
      return render(request, "journeys/journey.html", context)


  def features(request: HttpRequest) -> HttpResponse:
      """The planned features as feature cards, in the hackathon's template."""
      return render(request, "journeys/features.html", {"cards": CARDS})
  ```

- [ ] **Step 6: Write `urls.py` and wire it in**

  `ddp_tracker/journeys/urls.py`:

  ```python
  from django.urls import path

  from ddp_tracker.journeys import views
  from ddp_tracker.journeys.mockups import (
      api,
      changes,
      compare,
      concepts,
      instructions,
      learn,
      moderate,
      roles,
      seeding,
      shortlist,
      snapshots,
  )

  app_name = "journeys"

  urlpatterns = [
      path("", views.index, name="index"),
      path("journeys/<slug:role>/", views.journey, name="journey"),
      path("features/", views.features, name="features"),
      # mock-ups of planned features (mockups/): fictional data, one banner
      path("prototype/concepts/", concepts.concept_list, name="concepts"),
      path("prototype/concepts/<slug:slug>/", concepts.concept_detail, name="concept"),
      path("prototype/shortlist/", shortlist.shortlist, name="shortlist"),
      path("prototype/shortlist/add/", shortlist.add, name="shortlist-add"),
      path("prototype/shortlist/remove/", shortlist.remove, name="shortlist-remove"),
      path("prototype/shortlist/clear/", shortlist.clear, name="shortlist-clear"),
      path("prototype/shortlist/codebook.csv", shortlist.codebook, name="shortlist-codebook"),
      path("prototype/shortlist/blueprint.json", shortlist.blueprint, name="shortlist-blueprint"),
      path("prototype/compare/", compare.compare, name="compare"),
      path("prototype/platforms/<slug:slug>/changes/", changes.changes, name="changes"),
      path("prototype/api/", api.api_overview, name="api"),
      path("prototype/snapshots/", snapshots.snapshots, name="snapshots"),
      path("prototype/request/<slug:slug>/", instructions.request_instructions, name="request"),
      path("prototype/moderate/", moderate.dashboard, name="moderate"),
      path("prototype/moderate/seed/", seeding.seed_sources, name="seed"),
      path("prototype/admin/roles/", roles.roles, name="roles"),
      path("prototype/learn/<slug:slug>/", learn.learn, name="learn"),
  ]
  ```

  `config/urls.py`: add one line **before** the include of `ddp_tracker.core.urls`:

  ```python
  (path("", include("ddp_tracker.reviews.urls")),)
  (path("", include("ddp_tracker.journeys.urls")),)  # the landing page ("/"), the journeys
  (path("", include("ddp_tracker.core.urls")),)
  ```

  `ddp_tracker/core/urls.py`: the index keeps its name and moves off `/`:

  ```python
  (path("overview/", views.index, name="index"),)  # "/" is the journeys' landing page
  ```

  `config/settings/base.py`: after logging in or out, people land on `/`, as before:

  ```python
  LOGIN_REDIRECT_URL = "journeys:index"
  LOGOUT_REDIRECT_URL = "journeys:index"
  ```

- [ ] **Step 7: Write the templates**

  All under `ddp_tracker/journeys/templates/journeys/`. The class names are those of `01-design.md`, section 7; their styles arrive with task 2.2, so the pages look plain for now.

  `index.html`:

  ```django
  {% extends "base.html" %}
  {% block title %}DDP Tracker{% endblock %}
  {% block content %}
    <section class="landing-hero">
      <h1>DDP Tracker</h1>
      <p class="fs-5 text-black">
        Find out what platforms' data downloads contain, what it means, and how it changes.
      </p>
      <p>
        People upload the data download package (DDP) they requested from a platform. The tracker
        keeps only its structure, never the data in it, and curators describe what each data
        point means.
      </p>
    </section>
    <h2 id="roles">What brings you here?</h2>
    <ul class="cards" aria-labelledby="roles">
      {% for role in roles %}
        <li class="card role-card">
          <a class="card__title" href="{% url 'journeys:journey' role.slug %}">{{ role.name }}</a>
          <p class="role-card__line">I want to {{ role.card_line }}.</p>
          <p class="card__hint role-card__meta">
            {{ role.steps|length }} steps: {{ role.available_count }} available today,
            {{ role.prototype_count }} prototype
          </p>
        </li>
      {% endfor %}
    </ul>
    <h2>How it works</h2>
    <ol class="how-it-works">
      <li>
        <strong>Upload</strong>
        <p>Someone requests their DDP from a platform and uploads it.</p>
      </li>
      <li>
        <strong>Parse</strong>
        <p>The tracker notes the structure (which fields exist, of what type) and deletes the file.</p>
      </li>
      <li>
        <strong>Annotate</strong>
        <p>Curators describe what each data point means, in terms shared across platforms.</p>
      </li>
      <li>
        <strong>Explore</strong>
        <p>Everyone can explore the result, platform by platform.</p>
      </li>
    </ol>
    <h2>In this tracker today</h2>
    <ul class="stat-tiles">
      {% for label, count in counts %}
        <li class="stat-tile">
          <span class="stat-tile__value">{{ count }}</span>
          <span class="stat-tile__label">{{ label }}</span>
        </li>
      {% endfor %}
    </ul>
    <p>
      Prefer a list of everything you can do today? See
      <a href="{% url 'core:index' %}">all tasks on one page</a>.
      Curious what is planned? See the
      <a href="{% url 'journeys:features' %}">planned features as feature cards</a>.
    </p>
  {% endblock %}
  ```

  `journey.html`:

  ```django
  {% extends "base.html" %}
  {% block title %}{{ role.name }} · DDP Tracker{% endblock %}
  {% block content %}
    <p class="breadcrumbs">
      <a href="{% url 'journeys:index' %}">Home</a> / journeys / {{ role.name }}
    </p>
    <h1>{{ role.name }}</h1>
    <dl class="facts">
      <dt>Aim</dt>
      <dd>{{ role.aim }}</dd>
      <dt>Who this is for</dt>
      <dd>{{ role.audience }}</dd>
    </dl>
    {% if not has_demo_data %}
      <p class="message message--info">
        This database has no demo data yet, so links to TikTok's pages lead nowhere. Create it
        with <code>uv run manage.py seed_demo</code>.
      </p>
    {% endif %}
    <h2>Steps</h2>
    <ol class="journey-steps">
      {% for step, demo in steps %}
        {% include "journeys/_step.html" %}
      {% endfor %}
    </ol>
    <h2>Features this journey needs</h2>
    <div class="table-scroll">
      <table class="table table-sm">
        <thead>
          <tr>
            <th scope="col">Feature</th>
            <th scope="col">Today</th>
            <th scope="col">Note</th>
          </tr>
        </thead>
        <tbody>
          {% for feature in role.features %}
            <tr>
              <td>{{ feature.title }}</td>
              <td>
                <span class="badge badge--{{ feature.status }}">{{ feature.status_label }}</span>
              </td>
              <td>
                {{ feature.note }}
                {% if feature.hackathon %}<span class="muted">(raised at the hackathon)</span>{% endif %}
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    <p>
      The planned ones are described as
      <a href="{% url 'journeys:features' %}">feature cards</a>.
    </p>
    <h2>Other journeys</h2>
    <ul class="role-switch">
      {% for other in others %}
        <li>
          <a href="{% url 'journeys:journey' other.slug %}">{{ other.name }}</a>
        </li>
      {% endfor %}
    </ul>
  {% endblock %}
  ```

  `_step.html` (included with `step` and `demo` in its context):

  ```django
  <li class="journey-step journey-step--{{ step.status }}">
    <h3 class="journey-step__title">
      {{ step.title }}
      {% if step.status == "available" %}
        <span class="badge badge--available">Available</span>
      {% else %}
        <span class="badge badge--prototype">Prototype</span>
      {% endif %}
    </h3>
    <p>{{ step.text }}</p>
    {% if step.needs_label %}<p class="card__hint">{{ step.needs_label }}.</p>{% endif %}
    <p class="button-row">
      <a class="btn btn-primary btn-sm" href="{{ step.url }}">{{ step.link_label }}</a>
      {% if step.today_url %}
        <a class="btn btn-secondary btn-sm" href="{{ step.today_url }}">{{ step.today_label }}</a>
      {% endif %}
      {% if demo %}
        <a class="btn btn-secondary btn-sm" href="{{ demo.url }}">{{ demo.label }}</a>
      {% endif %}
    </p>
    {% if step.missing %}
      <p class="journey-step__missing muted">
        <strong>Still missing:</strong> {{ step.missing }}
      </p>
    {% endif %}
  </li>
  ```

  `features.html` (task 4.8 replaces its body; for now it lists the titles):

  ```django
  {% extends "base.html" %}
  {% block title %}Feature cards · DDP Tracker{% endblock %}
  {% block content %}
    <p class="breadcrumbs">
      <a href="{% url 'journeys:index' %}">Home</a> / feature cards
    </p>
    <h1>Feature cards</h1>
    <p class="lead">Planned features, in the template of the hackathon document.</p>
    <ul>
      {% for card in cards %}<li>{{ card.title }}</li>{% endfor %}
    </ul>
  {% endblock %}
  ```

  `_prototype_banner.html` (the sentence is fixed, see `01-design.md`, 5.4; keep it on **one line** and without tags inside it, because the tests look for it as one run of text):

  ```django
  <div class="alert alert-warning prototype-banner" role="note">
    Prototype: this page shows fictional data to illustrate a planned feature. It does not work yet.
  </div>
  ```

  `prototype/base.html` (every mock-up page extends it):

  ```django
  {% extends "base.html" %}
  {% block title %}{{ mockup.title }} · Prototype · DDP Tracker{% endblock %}
  {% block content %}
    {% include "journeys/_prototype_banner.html" %}
    <p class="breadcrumbs">
      <a href="{% url 'journeys:index' %}">Home</a> / prototype / {{ mockup.title }}
    </p>
    <h1>
      {% block heading %}{{ mockup.title }}{% endblock %}
    </h1>
    <p class="lead">{{ mockup.lead }}</p>
    {% block mockup %}{% endblock %}
    <footer class="prototype-footer">
      <h2>Where this fits</h2>
      <p>
        {{ mockup.number }}, a mock-up of {{ mockup.feature }}
        (features analysis, section {{ mockup.section }}). Part of the journey of:
        {% for role in mockup_roles %}
          <a href="{% url 'journeys:journey' role.slug %}">{{ role.name }}</a>{% if not forloop.last %},{% endif %}
        {% endfor %}
      </p>
      {% if mockup.hackathon %}<p>From the hackathon notes: {{ mockup.hackathon }}</p>{% endif %}
    </footer>
  {% endblock %}
  ```

  `prototype/placeholder.html`:

  ```django
  {% extends "journeys/prototype/base.html" %}
  {% block mockup %}
    <p class="message message--info">This mock-up is being built. Its journey already leads here.</p>
  {% endblock %}
  ```

  After writing them: `uv run djlint ddp_tracker/journeys --reformat`, then read the result. Django's `assertContains` compares the raw text, line breaks included, so a sentence that a test looks for must stay on one line (the banner; "I want to …"; "This database has no demo data yet"). djlint re-indents but does not re-wrap text.

- [ ] **Step 8: Run the tests and see them pass**

  ```bash
  DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest ddp_tracker/journeys/tests -q -p no:sugar --no-cov
  DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest ddp_tracker/core -q -p no:sugar --no-cov
  ```

  Expected: all pass, the existing `core` tests included (unchanged: they ask for `core:index`, which is now `/overview/`).

- [ ] **Step 9: Look at it**

  With the coordinator's `demo.sqlite3` (or make one: `migrate`, then `seed_demo`), you may run the server yourself for this step only, on port 8001 so as not to collide, and stop it again:

  ```bash
  DATABASE_URL=sqlite:///demo.sqlite3 USE_DOCKER=no uv run manage.py runserver 127.0.0.1:8001 --noreload
  ```

  Open `/`, `/journeys/engineer/`, `/prototype/concepts/` and `/overview/`. They are unstyled in places; they must show the right content and no error.

- [ ] **Step 10: Run the task gate and commit**

  Two commits:

  ```bash
  git add config/urls.py config/settings/base.py ddp_tracker/core/urls.py ddp_tracker/journeys/content.py ddp_tracker/journeys/targets.py ddp_tracker/journeys/feature_cards.py ddp_tracker/journeys/views.py ddp_tracker/journeys/urls.py ddp_tracker/journeys/mockups ddp_tracker/journeys/templates ddp_tracker/journeys/tests
  uv run pre-commit run
  git commit -m "feat(journeys): add the landing page, eight journeys and placeholders for the mock-ups

  The home page (/) is now the role picker. The previous home page keeps its
  content and its URL name (core:index) and moves to /overview/."
  ```

  If you prefer smaller commits (content and tests first, then routes and templates), that is welcome, as long as the tests pass at each commit.

**Acceptance:**

- `/` renders `journeys/index.html` with eight role links; `/overview/` renders the previous home page.
- Every journey answers 200; an unknown role 404.
- All twelve mock-up URLs answer 200 with the banner, for a signed-out visitor, a signed-in user and staff, on an empty and on a seeded database.
- `ddp_tracker/core/tests/tests.py` is unchanged and passes.
- The full suite is as at the baseline plus the new tests; ruff, mypy, djlint clean.

---

## Task 2.2: Navigation and styles

**Review:** full.

**Files:**

- Modify: `ddp_tracker/templates/base.html`
- Create: `ddp_tracker/journeys/templates/journeys/_prototype_nav.html`
- Create (copy): `assets/scss/pages/_journeys.scss` from `starter-files/assets/scss/pages/_journeys.scss`
- Modify: `assets/scss/main.scss` (one line)
- Modify (rebuilt): `ddp_tracker/static/css/main.css`
- Create (copy): `ddp_tracker/static/js/journeys.js` from `starter-files/ddp_tracker/static/js/journeys.js`
- Modify: `ddp_tracker/journeys/tests/test_views.py` (add a test class)

**Interfaces:**

- Consumes: the URL names of task 2.1.
- Produces: the classes of `01-design.md`, section 7, for every later page; the header as in `01-design.md`, 6.1.

**Existing tests that look at the header** (they must pass unchanged):

- `ddp_tracker/core/tests/tests.py`: the header has exactly `<a href="/platforms/">Explore</a>`; the overview page has `href="/platforms/"` exactly four times (so the header may link there only once); signed-out visitors and non-staff never see the word "Curate"; staff do.
- `ddp_tracker/schemas/tests/test_platforms.py`: the text between `<nav class="site-nav">` and the first `</nav>` does not contain "Representations".
- `ddp_tracker/ddps/tests/test_uploads.py`: the menu has `My uploads</a>`.
- `ddp_tracker/proposals/tests/test_views.py`: non-staff see "My suggestions" and never "Suggestions ("; staff see "Suggestions (3)".

- [ ] **Step 1: Write the failing tests**

  Add to `ddp_tracker/journeys/tests/test_views.py`:

  ```python
  class NavigationTests(TestCase):
      """The header of every page: what exists in the main row, the mock-ups in a strip below."""

      def nav(self, response, css_class):
          return response.content.decode().split(f'<nav class="{css_class}"')[1].split("</nav>")[0]

      def test_the_brand_and_home_lead_to_the_landing_page(self):
          response = self.client.get(reverse("schemas:platforms"))
          self.assertContains(response, '<a class="site-header__brand" href="/">')
          self.assertContains(response, '<a href="/">Home</a>', html=True)

      def test_the_main_row_has_only_what_exists(self):
          main = self.nav(self.client.get("/"), "site-nav")
          for text in ("Home", "Explore", "Docs", "Contribute", "Log in"):
              self.assertIn(text, main)
          self.assertIn(f'href="{reverse("journeys:journey", args=["contributor"])}"', main)
          for text in ("Concepts", "Compare", "API", "prototype"):
              self.assertNotIn(text, main)

      def test_the_mockups_are_in_a_strip_of_their_own(self):
          strip = self.nav(self.client.get(reverse("schemas:platforms")), "prototype-nav")
          self.assertIn('aria-label="Prototype pages"', strip)
          self.assertIn("Prototype previews", strip)
          for name in ("journeys:concepts", "journeys:compare", "journeys:api"):
              self.assertIn(f'href="{reverse(name)}"', strip)
          self.assertNotIn("Curate", strip)  # staff only

      def test_staff_also_get_the_moderator_dashboard(self):
          self.client.force_login(User.objects.create_user("staff@example.org", is_staff=True))
          strip = self.nav(self.client.get("/"), "prototype-nav")
          self.assertIn(f'href="{reverse("journeys:moderate")}"', strip)
          self.assertIn("Curate", strip)

      def test_signed_in_people_keep_their_items(self):
          self.client.force_login(User.objects.create_user("someone@example.org"))
          main = self.nav(self.client.get("/"), "site-nav")
          for text in ("My uploads", "My suggestions", "Upload a DDP", "Log out"):
              self.assertIn(text, main)
          self.assertNotIn("Contribute", main)  # they have the upload button
  ```

- [ ] **Step 2: Run them and see them fail**

  ```bash
  DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest ddp_tracker/journeys/tests/test_views.py -q -p no:sugar --no-cov -k Navigation
  ```

  Expected: 5 failed.

- [ ] **Step 3: Change `ddp_tracker/templates/base.html`**

  Three small edits, nothing else in the file:

  1. The brand leads to the landing page: `href="{% url 'core:index' %}"` becomes `href="{% url 'journeys:index' %}"`.
  2. In `<nav class="site-nav">`, add "Home" before "Explore" and "Docs" after it, and "Contribute" for signed-out visitors. The lines between `{% if user.is_authenticated %}` and `{% else %}` stay exactly as they are:

     ```django
     <nav class="site-nav">
       <a href="{% url 'journeys:index' %}">Home</a>
       <a href="{% url 'schemas:platforms' %}">Explore</a>
       <a href="{% url 'docs' '' %}">Docs</a>
       {% if user.is_authenticated %}
         … unchanged …
       {% else %}
         <a href="{% url 'journeys:journey' 'contributor' %}">Contribute</a>
         <a href="{% url 'account_login' %}">Log in</a>
       {% endif %}
     </nav>
     ```

  3. Right after `</header>`, include the strip:

     ```django
     </header>
     {% include "journeys/_prototype_nav.html" %}
     ```

  `ddp_tracker/journeys/templates/journeys/_prototype_nav.html`:

  ```django
  {# Mock-ups of planned features, kept apart from the pages that exist (journeys/mockups). #}
  <nav class="prototype-nav" aria-label="Prototype pages">
    <span class="prototype-nav__label">Prototype previews</span>
    <a href="{% url 'journeys:concepts' %}">Concepts</a>
    <a href="{% url 'journeys:compare' %}">Compare</a>
    <a href="{% url 'journeys:api' %}">API</a>
    {% if user.is_staff %}<a href="{% url 'journeys:moderate' %}">Curate</a>{% endif %}
  </nav>
  ```

- [ ] **Step 4: Add the styles and the script**

  ```bash
  P="/c/Users/hekma/Documents/Projects/DDP-Tracker-docs/implementation-plan/starter-files"
  cp "$P/assets/scss/pages/_journeys.scss" assets/scss/pages/_journeys.scss
  cp "$P/ddp_tracker/static/js/journeys.js" ddp_tracker/static/js/journeys.js
  ```

  In `assets/scss/main.scss`, after the last `@use` line:

  ```scss
  @use "layout/header";
  @use "layout/page";

  // the user journeys prototype (ddp_tracker/journeys)
  @use "pages/journeys";
  ```

  Build, and check that the compiled file changed and nothing else did:

  ```bash
  npm run build:css
  git status --short
  ```

  Expected: `assets/scss/main.scss`, `assets/scss/pages/_journeys.scss`, `ddp_tracker/static/css/main.css`, `ddp_tracker/static/js/journeys.js`, `ddp_tracker/templates/base.html`, the new partial and the test file. Sass must print no warning of its own (warnings from Bootstrap are silenced by the build).

  `journeys.js` is not loaded yet: task 3.3 loads it on the page that needs it.

- [ ] **Step 5: Run the tests**

  ```bash
  DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest -q -p no:sugar
  ```

  Expected: the five new tests pass, and so do the four existing test files named above.

- [ ] **Step 6: Look at it, wide and narrow**

  Run the server on port 8001 as in task 2.1, step 9, and open `/`, `/journeys/researcher/`, `/prototype/concepts/` and `/platforms/tiktok/`. Check, at a normal width and with the browser window made as narrow as a phone (about 375 pixels):

  - the header wraps instead of running off the page; the strip sits under it on every page;
  - the role cards are a grid that becomes one column; the last line of each card sits at the bottom;
  - the steps have a numbered circle; prototype steps have a dashed frame and an amber number;
  - the badges read "Available" (green) and "Prototype" (amber);
  - the explorer page looks as before, apart from the header.

  The pictures in `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs\implementation-plan\planning-screenshots\` show what these pages looked like when the plan's listings were run while planning: yours should look the same. Fix what is off in `_journeys.scss` (rebuild after each change). Do not change any other Sass file.

- [ ] **Step 7: Run the task gate and commit**

  ```bash
  git add ddp_tracker/templates/base.html ddp_tracker/journeys assets/scss ddp_tracker/static/css/main.css ddp_tracker/static/js/journeys.js
  uv run pre-commit run
  git commit -m "feat(journeys): add the navigation and the styles of the prototype

  The header's main row keeps the pages that exist (Home, Explore, Docs and the
  account items). Mock-ups of planned features get a strip of their own below it.
  The compiled main.css is rebuilt, as in every Sass change of this repository."
  ```

**Acceptance:**

- The five navigation tests pass; every existing test passes unchanged.
- `git diff HEAD~1 --stat` lists only the files above.
- `grep -c "prototype-nav" ddp_tracker/static/css/main.css` is 1 or more (the CSS was rebuilt).
- No Sass warning from our partial.

---

## Task 2.3: Screenshots and check-in (coordinator)

- [ ] **Fresh database and server.**

  ```bash
  rm -f demo.sqlite3
  DATABASE_URL=sqlite:///demo.sqlite3 USE_DOCKER=no uv run manage.py migrate -v 0
  DATABASE_URL=sqlite:///demo.sqlite3 USE_DOCKER=no uv run manage.py seed_demo
  ```

  Start the server in the background (`00-coordinator-guide.md`, section 4).

- [ ] **Take the screenshots.** From `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs\implementation-plan\tools`:

  ```bash
  uv run --no-project --with playwright python take_screenshots.py
  ```

  Expected: "saved …" for every page and no line starting with PROBLEM. The mock-up pages are placeholders at this point; that is fine. If the login step fails (the staff pictures), open `/accounts/login/` in the browser pane, look at the form's field names, and correct the selectors in the tool.

- [ ] **Look at the pictures** in `DDP-Tracker-docs\prototype-screenshots\`: `01-landing.png`, `01-landing-phone.png`, `02-journey-researcher.png`, `02-journey-contributor.png`, `30-landing-staff.png`, `23-overview.png`, `24-explorer-tiktok.png`. Compare the landing page with `..\handoff-user-journeys\reference-screenshots\current-home.png`: same family (white, navy, cards), not a different site.

- [ ] **Phase gate** (`00-coordinator-guide.md`, section 5).

- [ ] **Check in with Hekmat** (`00-coordinator-guide.md`, section 6). Show at least: the landing page (wide and phone), two journeys, the header with the strip. Say that the mock-up pages are placeholders until phases 3 and 4. Ask the one question, and ask him to confirm or change these two decisions, which are the most visible: D20 (the previous home page is now `/overview/`) and D21 (prototype pages in a strip of their own).
