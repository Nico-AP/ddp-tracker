# 05. Phase 3: the core mock-ups

Output: the story "two views, one model, and a hand-off" works from end to end. A researcher finds concepts (M1), reads one (M2), builds a shortlist and hands it over (M3); an engineer opens it, sees exact paths, reads what changed (M5) and looks at the API (M6). Five subagent tasks, then the second check-in.

**Every task in this phase and the next has the same shape:**

1. The page exists already as a placeholder: a module in `ddp_tracker/journeys/mockups/` with the page's fictional data and a placeholder view at its bottom. **Replace the placeholder view**, keep the data (you may add to it).
2. Add the page's template in `ddp_tracker/journeys/templates/journeys/prototype/`. It extends `journeys/prototype/base.html` and fills `{% block mockup %}` (and `{% block heading %}` if the heading should differ from the mock-up's title). Use the classes of `01-design.md`, section 7. Add Sass only if nothing there fits: then add it at the end of `assets/scss/pages/_journeys.scss`, run `npm run build:css` and commit `ddp_tracker/static/css/main.css` with it.
3. Add the page's test file in `ddp_tracker/journeys/tests/`. Tests with data subclass `SeededTestCase` (`tests/utils.py`); a test on an empty database uses `TestCase`.
4. The generic tests in `test_mockups.py` and `test_conventions.py` already cover: 200 for everyone, the banner, one `h1`, the link back to the journeys, no inline style or script. Keep them green.
5. Real data where the database has it (D33). Where it has none, a short note: "No demo data in this database yet. Create it with `uv run manage.py seed_demo`." The page must never fail on an empty database.
6. **Changed at the Phase 3 check-in (Hekmat, 30 September 2026): no "fictional" labels anywhere.** The banner says once per page that the data is fictional; a `badge--fictional` tag next to things is not used. Originally: anything that is fictional on a page that also shows real data is marked as such where it stands, with a small label: `<span class="badge badge--fictional">fictional</span>`.

The tests below are the contract for behaviour. If a test's wording check does not match your wording, change the wording check, not the meaning, and report it.

Verified figures for the demo data, which the tests use: TikTok has two registered uploads (15 March and 15 September 2026); the September one has 156 data points, of which 5 are new outright (the five under `Tiktok Live`), 33 moved, 1 changed and 1 removed (`likesReceived`); TikTok has 190 data points in all, 177 of them without an annotation; all platforms together have 632 data points.

---

## Task 3.1: Concept view (M1)

**Review:** full.

**Files:**

- Modify: `ddp_tracker/journeys/mockups/concepts.py` (add the resolving code, replace `concept_list`)
- Create: `ddp_tracker/journeys/templates/journeys/prototype/concepts.html`
- Create: `ddp_tracker/journeys/tests/test_concepts.py`

**Interfaces:**

- Consumes: `FIELDS`, `CONCEPTS`, `Binding` (already in the module); `DEMO_PLATFORMS`, `render_mockup` from `mockups/__init__.py`; `profiles` from `ddp_tracker.schemas.profiles`; the annotation names of `demo/spec.py`.
- Produces (tasks 3.2, 3.3 and 4.1 use them):

  ```python
  @dataclass
  class FieldView:                     # one data point: a field of a list's item, or a single value
      location: Location
      profile: Profile
      # properties: name (the key), example (its first example value, or "")

  @dataclass
  class LocationView:                  # an annotated location, with what the uploads that count say
      location: Location
      profile: Profile
      languages: list[str]
      fields: list[FieldView]          # a list's item: its direct fields; a single value: itself
      examples: list[tuple[str, str]]  # (title, value) rows for the examples table

  @dataclass
  class PlatformView:                  # a concept on one platform
      binding: Binding
      name: str                        # the platform's name
      annotation: Annotation | None    # None: this database does not have it (no demo data)
      locations: list[LocationView]    # the path in use now first (the one seen last)

  @dataclass(frozen=True)
  class Availability:
      known: bool                      # this database has at least one of the annotations
      first_seen: date | None
      last_seen: date | None
      uploads: int                     # uploads that count and contain it, all platforms
      pii: bool

  def resolve(concept: Concept) -> list[PlatformView]
  def availability(views: list[PlatformView]) -> Availability
  ```

**What the page shows** (`03-site-structure.md`, M1, and `01-design.md`, section 3):

- A toolbar (a GET form, no JavaScript): "Research field" (select, `field`), "Platform" (select, `platform`, with "All platforms"), "Sort by" (select, `sort`: "Relevance" or "Name"), a button "Show". Below it the themes of the chosen field as chips that are links ("All themes" first); the chosen one has `chip--active` and `aria-current="true"`. Every link keeps the other choices.
- One line: "The demo data is in English only, so there is no language filter."
- One line with a link: "Looking for every path and type? Open the full structure in the explorer." (to `schemas:platforms`).
- How many concepts are shown, for example "4 concepts for News and politics".
- The concepts as cards (`<ul class="cards">`). A card has: the name (a link to `journeys:concept`); the description; the statement in `<code>`; one chip per demo platform that has concepts (TikTok, Instagram, Facebook): `chip--on` with the platform's name where the concept is available, `chip--off` with "<name>: not available" where it is not (words, not only colour); the chosen field's themes that the concept belongs to, as plain chips; "On N studies' shortlists" with the fictional label; where the database knows the concept: "First seen <date>, last seen <date>, in <n> uploads"; a `badge badge--pii` "Personal data" if any of its annotations is flagged.
- On a database without the demo data: the note of rule 5 above the cards.

- [ ] **Step 1: Write the failing tests**

  `ddp_tracker/journeys/tests/test_concepts.py`:

  ```python
  """M1 and M2, the concept view: concepts across platforms, with labels per research field, and
  what the uploads say about each (mockups/concepts.py)."""

  from datetime import date

  from django.test import SimpleTestCase, TestCase
  from django.urls import reverse

  from ddp_tracker.journeys.demo.spec import ANNOTATIONS
  from ddp_tracker.journeys.mockups.concepts import (
      CONCEPTS,
      CONCEPTS_BY_SLUG,
      FIELDS,
      availability,
      resolve,
  )
  from ddp_tracker.journeys.tests.utils import SeededTestCase

  LIST = reverse("journeys:concepts")
  T = "/user_data_tiktok.json"


  def slugs(response):
      return [card["concept"].slug for card in response.context["cards"]]


  class ConceptDataTests(SimpleTestCase):
      def test_every_binding_names_an_annotation_of_the_demo_data(self):
          seeded = {(spec.platform, spec.name) for spec in ANNOTATIONS}
          for concept in CONCEPTS:
              for binding in concept.bindings:
                  with self.subTest(concept=concept.slug, platform=binding.platform):
                      self.assertIn((binding.platform, binding.annotation), seeded)

      def test_themes_belong_to_fields_and_every_theme_is_used(self):
          themes = {theme.slug for field in FIELDS for theme in field.themes}
          used = {theme for concept in CONCEPTS for theme in concept.themes}
          self.assertEqual(used, themes)

      def test_slugs_are_unique(self):
          self.assertEqual(len(CONCEPTS_BY_SLUG), len(CONCEPTS))


  class ConceptListWithoutDataTests(TestCase):
      def test_every_concept_by_relevance(self):
          response = self.client.get(LIST)
          expected = [c.slug for c in sorted(CONCEPTS, key=lambda c: -c.studies)]
          self.assertEqual(slugs(response), expected)
          self.assertContains(response, f"{len(CONCEPTS)} concepts")

      def test_it_says_that_the_demo_data_is_missing(self):
          response = self.client.get(LIST)
          self.assertContains(response, "seed_demo")
          self.assertFalse(any(card["availability"].known for card in response.context["cards"]))
          self.assertNotContains(response, "First seen")


  class ConceptListTests(SeededTestCase):
      def test_a_theme_narrows_the_list(self):
          response = self.client.get(LIST, {"field": "communication", "theme": "news-politics"})
          self.assertEqual(
              set(slugs(response)), {"watched-video", "searched", "commented", "followed-account"}
          )
          self.assertContains(response, "4 concepts for News and politics")
          self.assertContains(response, 'aria-current="true"', count=1)

      def test_a_field_has_its_own_themes(self):
          response = self.client.get(LIST, {"field": "health"})
          self.assertContains(response, "Wellbeing and screen time")
          self.assertNotContains(response, "News and politics")
          # a theme of another field is ignored
          response = self.client.get(LIST, {"field": "communication", "theme": "wellbeing"})
          self.assertEqual(len(slugs(response)), len(CONCEPTS))

      def test_a_platform_narrows_the_list(self):
          found = slugs(self.client.get(LIST, {"platform": "instagram"}))
          self.assertIn("saw-ad", found)
          self.assertNotIn("off-platform-activity", found)
          # an unknown platform is ignored
          self.assertEqual(len(slugs(self.client.get(LIST, {"platform": "nope"}))), len(CONCEPTS))

      def test_sorting_by_name(self):
          found = slugs(self.client.get(LIST, {"sort": "name"}))
          names = [CONCEPTS_BY_SLUG[slug].name for slug in found]
          self.assertEqual(names, sorted(names))

      def test_the_choices_survive_in_the_theme_links(self):
          response = self.client.get(LIST, {"field": "health", "platform": "tiktok", "sort": "name"})
          self.assertContains(
              response, "?field=health&amp;theme=wellbeing&amp;platform=tiktok&amp;sort=name"
          )

      def test_a_card_says_what_the_uploads_show(self):
          found = availability(resolve(CONCEPTS_BY_SLUG["watched-video"]))
          self.assertTrue(found.known)
          # TikTok's older package is the first to have it; four uploads that count have it
          self.assertEqual(
              (found.first_seen, found.last_seen, found.uploads, found.pii),
              (date(2026, 3, 15), date(2026, 9, 15), 4, False),
          )
          self.assertTrue(availability(resolve(CONCEPTS_BY_SLUG["sent-message"])).pii)
          response = self.client.get(LIST)
          self.assertContains(response, "First seen")
          self.assertContains(response, "Personal data")

      def test_a_concept_resolves_to_its_paths(self):
          tiktok, instagram, facebook = resolve(CONCEPTS_BY_SLUG["watched-video"])
          self.assertEqual(
              (tiktok.name, instagram.name, facebook.name), ("TikTok", "Instagram", "Facebook")
          )
          # the path in use now first, then the older one
          self.assertEqual(
              [entry.location.path for entry in tiktok.locations],
              [
                  f"{T}/Your Activity/Watch History/VideoList/[]",
                  f"{T}/Activity/Video Browsing History/VideoList/[]",
              ],
          )
          current = tiktok.locations[0]
          self.assertEqual([field.name for field in current.fields], ["Date", "Link"])
          self.assertEqual(current.fields[0].profile.main_format, "%Y-%m-%d %H:%M:%S")
          self.assertEqual(current.languages, ["en"])
          self.assertEqual(current.examples[0], ("Date", "2026-09-01 08:15:42"))

      def test_availability_is_said_in_words(self):
          response = self.client.get(LIST)
          self.assertContains(response, "TikTok: not available")  # "Saw an ad" is Instagram only
          self.assertContains(response, reverse("journeys:concept", args=["watched-video"]))
          self.assertContains(response, reverse("schemas:platforms"))
          self.assertContains(response, "fictional")
  ```

- [ ] **Step 2: Run them and see them fail**

  ```bash
  DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest ddp_tracker/journeys/tests/test_concepts.py -q -p no:sugar --no-cov
  ```

  Expected: an import error (`cannot import name 'availability'`).

- [ ] **Step 3: Add the resolving code to `mockups/concepts.py`**

  Below the data, above the views. This code was checked against the demo data for the queries it makes; treat it as the reference and adapt what the linter or the type checker asks for.

  ```python
  @dataclass
  class FieldView:
      """One data point: a field of a list's item, or a value on its own."""

      location: Location
      profile: Profile

      @property
      def name(self) -> str:
          return self.location.display_name

      @property
      def example(self) -> str:
          examples = self.location.example_values
          return examples[0]["value"] if examples else ""


  @dataclass
  class LocationView:
      """An annotated location, with what the uploads that count say about it."""

      location: Location
      profile: Profile
      languages: list[str]
      fields: list[FieldView]
      examples: list[tuple[str, str]]


  @dataclass
  class PlatformView:
      """A concept on one platform: the annotation that describes it there, if this database has
      it (``seed_demo``), and its locations, the path in use now first."""

      binding: Binding
      name: str
      annotation: Annotation | None
      locations: list[LocationView]


  @dataclass(frozen=True)
  class Availability:
      known: bool
      first_seen: date | None
      last_seen: date | None
      uploads: int
      pii: bool


  def _counted() -> QuerySet[Observation]:
      """Only uploads that count: registered."""
      return Observation.objects.filter(upload__registered_at__isnull=False)


  def _examples(location: Location) -> list[tuple[str, str]]:
      """Example values as rows of title and value: for a list's item, the data points below it
      that have examples (by their path below the item); for a single value, its own."""
      if not location.path.endswith(ITEM):
          return [(location.display_name, example["value"]) for example in location.example_values]
      below = (
          Location.objects.filter(platform=location.platform_id, path__startswith=f"{location.path}/")
          .exclude(example_values=[])
          .order_by("position", "path")
      )
      return [
          (entry.path.removeprefix(f"{location.path}/"), entry.example_values[0]["value"])
          for entry in below
      ]


  def _location_view(location: Location) -> LocationView:
      children: list[Location] = []
      if location.path.endswith(ITEM):  # a list's item: its direct fields
          children = list(
              Location.objects.filter(platform=location.platform_id, parent_path=location.path)
              .exclude(name=None)
              .order_by("position")
          )
      found = profiles([location.pk, *(child.pk for child in children)], _counted())
      fields = [FieldView(child, found[child.pk]) for child in children]
      seen = location.observations.filter(upload__registered_at__isnull=False)
      languages = sorted(
          {code or "unknown" for code in seen.values_list("upload__language", flat=True)}
      )
      return LocationView(
          location=location,
          profile=found[location.pk],
          languages=languages,
          fields=fields or [FieldView(location, found[location.pk])],
          examples=_examples(location),
      )


  def resolve(concept: Concept) -> list[PlatformView]:
      """The concept on each platform it is bound to, with what this database knows about it."""
      views = []
      for binding in concept.bindings:
          annotation = (
              Annotation.objects.filter(platform__slug=binding.platform, name=binding.annotation)
              .select_related("platform")
              .first()
          )
          if annotation is None:  # no demo data: the binding alone
              views.append(PlatformView(binding, DEMO_PLATFORMS[binding.platform], None, []))
              continue
          locations = [_location_view(location) for location in annotation.locations.all()]
          locations.sort(key=lambda entry: entry.profile.last_seen or date.min, reverse=True)
          views.append(PlatformView(binding, annotation.platform.name, annotation, locations))
      return views


  def availability(views: list[PlatformView]) -> Availability:
      """A concept at a glance, over all its platforms."""
      entries = [entry for view in views for entry in view.locations]
      firsts = [entry.profile.first_seen for entry in entries if entry.profile.first_seen]
      lasts = [entry.profile.last_seen for entry in entries if entry.profile.last_seen]
      uploads = Upload.objects.filter(
          registered_at__isnull=False,
          observations__location__in=[entry.location.pk for entry in entries],
      )
      return Availability(
          known=any(view.annotation is not None for view in views),
          first_seen=min(firsts, default=None),
          last_seen=max(lasts, default=None),
          uploads=uploads.distinct().count(),
          pii=any(view.annotation.pii for view in views if view.annotation is not None),
      )
  ```

  Imports to add: `from datetime import date`; `from typing import Any`; `from django.db.models import QuerySet`; `Http404` (for task 3.2); `Annotation` (`ddp_tracker.annotations.models`), `Upload` (`ddp_tracker.ddps.models`), `ITEM`, `Location`, `Observation` (`ddp_tracker.schemas.models`), `Profile`, `profiles` (`ddp_tracker.schemas.profiles`), and `DEMO_PLATFORMS` from `ddp_tracker.journeys.mockups`.

- [ ] **Step 4: Replace the placeholder `concept_list`**

  ```python
  def concept_list(request: HttpRequest) -> HttpResponse:
      """M1: the concepts, narrowed by a research field's theme and by platform, sorted by
      relevance (how many studies use them: fictional) or by name."""
      chosen_field = FIELDS_BY_SLUG.get(request.GET.get("field", ""), FIELDS[0])
      themes = {theme.slug: theme for theme in chosen_field.themes}
      theme = themes.get(request.GET.get("theme", ""))  # a theme of another field: ignored
      platform = request.GET.get("platform", "")
      platforms = {
          slug: name
          for slug, name in DEMO_PLATFORMS.items()
          if any(slug in concept.platforms for concept in CONCEPTS)
      }
      if platform not in platforms:
          platform = ""
      sort = "name" if request.GET.get("sort") == "name" else "relevance"
      chosen = [
          concept
          for concept in CONCEPTS
          if (theme is None or theme.slug in concept.themes)
          and (not platform or platform in concept.platforms)
      ]
      chosen.sort(key=(lambda c: c.name) if sort == "name" else (lambda c: -c.studies))
      cards: list[dict[str, Any]] = []
      for concept in chosen:
          views = resolve(concept)
          cards.append(
              {
                  "concept": concept,
                  "availability": availability(views),
                  # every platform of the matrix, with whether the concept is there
                  "platforms": [
                      (name, slug in concept.platforms) for slug, name in platforms.items()
                  ],
                  "themes": [t for t in chosen_field.themes if t.slug in concept.themes],
              }
          )
      context = {
          "fields": FIELDS,
          "field": chosen_field,
          "theme": theme,
          "platforms": platforms,
          "platform": platform,
          "sort": sort,
          "cards": cards,
          "has_data": any(card["availability"].known for card in cards),
      }
      return render_mockup(request, "concepts", "journeys/prototype/concepts.html", context)
  ```

  If ruff reports the two lambdas (`E731` does not apply to arguments; `PLW0108` might), use `operator.attrgetter("name")` and a small function.

- [ ] **Step 5: Write the template `prototype/concepts.html`**

  This is the reference template for the mock-ups: the others follow its patterns (a toolbar form with labels, chips that say things in words, cards, the no-data note).

  ```django
  {% extends "journeys/prototype/base.html" %}
  {% block mockup %}
    <form method="get" class="proto-toolbar">
      <div>
        <label class="form-label" for="concept-field">Research field</label>
        <select class="form-select" id="concept-field" name="field">
          {% for option in fields %}
            <option value="{{ option.slug }}"{% if option == field %} selected{% endif %}>{{ option.name }}</option>
          {% endfor %}
        </select>
      </div>
      <div>
        <label class="form-label" for="concept-platform">Platform</label>
        <select class="form-select" id="concept-platform" name="platform">
          <option value="">All platforms</option>
          {% for slug, name in platforms.items %}
            <option value="{{ slug }}"{% if slug == platform %} selected{% endif %}>{{ name }}</option>
          {% endfor %}
        </select>
      </div>
      <div>
        <label class="form-label" for="concept-sort">Sort by</label>
        <select class="form-select" id="concept-sort" name="sort">
          <option value="relevance"{% if sort == "relevance" %} selected{% endif %}>Relevance</option>
          <option value="name"{% if sort == "name" %} selected{% endif %}>Name</option>
        </select>
      </div>
      {% if theme %}<input type="hidden" name="theme" value="{{ theme.slug }}">{% endif %}
      <button type="submit" class="btn btn-primary">Show</button>
    </form>
    <p>
      Themes in {{ field.name }}:
      <a class="chip{% if not theme %} chip--active{% endif %}"
         href="?field={{ field.slug }}&amp;platform={{ platform }}&amp;sort={{ sort }}"
         {% if not theme %}aria-current="true"{% endif %}>All themes</a>
      {% for option in field.themes %}
        <a class="chip{% if option == theme %} chip--active{% endif %}"
           href="?field={{ field.slug }}&amp;theme={{ option.slug }}&amp;platform={{ platform }}&amp;sort={{ sort }}"
           {% if option == theme %}aria-current="true"{% endif %}>{{ option.name }}</a>
      {% endfor %}
      <span class="badge badge--fictional">fictional</span>
    </p>
    <p class="muted">
      The demo data is in English only, so there is no language filter. Looking for every path and
      type? Open the <a href="{% url 'schemas:platforms' %}">full structure in the explorer</a>.
    </p>
    {% if not has_data %}
      <p class="message message--info">
        No demo data in this database yet, so the concepts come without dates and paths. Create
        it with <code>uv run manage.py seed_demo</code>.
      </p>
    {% endif %}
    <h2>
      {{ cards|length }} concept{{ cards|length|pluralize }}{% if theme %} for {{ theme.name }}{% endif %}
    </h2>
    <ul class="cards">
      {% for card in cards %}
        <li class="card">
          <a class="card__title"
             href="{% url 'journeys:concept' card.concept.slug %}">{{ card.concept.name }}</a>
          {% if card.availability.pii %}<span class="badge badge--pii">Personal data</span>{% endif %}
          <p>{{ card.concept.description }}</p>
          <p>
            <code>{{ card.concept.statement }}</code>
          </p>
          <p>
            {% for name, available in card.platforms %}
              {% if available %}
                <span class="chip chip--on">{{ name }}</span>
              {% else %}
                <span class="chip chip--off">{{ name }}: not available</span>
              {% endif %}
            {% endfor %}
          </p>
          <p>
            {% for option in card.themes %}<span class="chip">{{ option.name }}</span>{% endfor %}
          </p>
          <p class="card__hint">
            On {{ card.concept.studies }} studies' shortlists
            <span class="badge badge--fictional">fictional</span>
          </p>
          {% if card.availability.known %}
            <p class="card__hint">
              First seen {{ card.availability.first_seen|date:"Y-m-d" }}, last seen
              {{ card.availability.last_seen|date:"Y-m-d" }}, in
              {{ card.availability.uploads }} upload{{ card.availability.uploads|pluralize }}
            </p>
          {% endif %}
        </li>
      {% endfor %}
    </ul>
  {% endblock %}
  ```

  The test `test_the_choices_survive_in_the_theme_links` looks for `?field=health&amp;theme=wellbeing&amp;platform=tiktok&amp;sort=name`: keep that order of parameters.

- [ ] **Step 6: Run the tests, reformat, look**

  ```bash
  uv run djlint ddp_tracker/journeys --reformat
  DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest ddp_tracker/journeys/tests -q -p no:sugar --no-cov
  ```

  Expected: all pass. Then look at `/prototype/concepts/` and `/prototype/concepts/?field=health&theme=wellbeing` on port 8001 with the seeded `demo.sqlite3`, wide and narrow.

- [ ] **Step 7: Task gate and commit**

  ```bash
  git add ddp_tracker/journeys
  uv run pre-commit run
  git commit -m "feat(journeys): add the concept view mock-up (M1)"
  ```

**Acceptance:** the tests of `test_concepts.py` pass; the page works with and without demo data; the four selects and chips keep each other's values; nothing scrolls sideways at 375 pixels.

---

## Task 3.2: Concept detail (M2)

**Review:** light.

**Files:**

- Modify: `ddp_tracker/journeys/mockups/concepts.py` (replace `concept_detail`)
- Create: `ddp_tracker/journeys/templates/journeys/prototype/concept.html`
- Modify: `ddp_tracker/journeys/tests/test_concepts.py` (add a test class)

**Interfaces:** consumes `resolve`, `CONCEPTS_BY_SLUG`, `FIELDS` (task 3.1). Produces nothing new.

**What the page shows**, top to bottom:

- Heading: the concept's name (fill `{% block heading %}`). Under it: the description; the statement in `<code>`; a chip with `concept.meaning_label` ("Agreed by curators" or "Under discussion"); "On N studies' shortlists" with the fictional label; per research field, the themes the concept belongs to.
- One section per platform of the concept (`h2` with the platform's name), inside a `proto-panel` or plainly:
  - If the database has the annotation: its name as a link to the real annotation page (`annotation.get_absolute_url`), a `badge` "Curator annotation", and `badge badge--pii` "Personal data" if flagged; its description; "Sources and notes": its note, if any.
  - If `binding.official`: a `badge badge--official` "Official documentation", the text, and the fictional label. Say once on the page that official documentation would be kept as its own kind of annotation, next to the curator's.
  - "Whose time?": `binding.tz_whos`, with "(proposed attribute: tz_whos)".
  - If `binding.no_data`: "No data markers": the values in `<code>`, and "values that mean the field is empty".
  - A table, one row per location (wrapped in `table-scroll`): Path (`<code>`, cell with `text-break`), Seen (first to last date), Uploads, Languages. Mark the first row "in use now" when there are several.
  - For the location in use now, a table "Fields": Field, Type, Format, Example (from `entry.fields`: `field.name`, `field.profile.main_type`, `field.profile.main_format` or the shape hint, `field.example`).
  - "Examples" as a table with the columns Title and Value (from `entry.examples`), with the line "Fictional values, typed by a curator."
  - A link "Open in <platform>'s explorer" to `schemas:platform` with `?q=` and the key of the list (the path's last named segment).
  - If the database does not have the annotation: "Not in this database yet" and the `seed_demo` hint.
- "This concept in other languages": the translations as a small table, with the fictional label and the sentence "In the real feature, curators could add a translation here."
- A link back: "All concepts".

- [ ] **Step 1: Write the failing tests** (add to `test_concepts.py`)

  ```python
  def detail(slug):
      return reverse("journeys:concept", args=[slug])


  class ConceptDetailWithoutDataTests(TestCase):
      def test_an_unknown_concept_is_not_found(self):
          self.assertEqual(self.client.get(detail("nope")).status_code, 404)

      def test_without_demo_data_it_still_explains_the_concept(self):
          response = self.client.get(detail("watched-video"))
          self.assertContains(response, "<h1>Watched a video</h1>", html=True)
          self.assertContains(response, "Not in this database yet", count=3)  # three platforms
          self.assertContains(response, "UTC (assumed")


  class ConceptDetailTests(SeededTestCase):
      def test_it_shows_where_and_how_each_platform_provides_it(self):
          response = self.client.get(detail("watched-video"))
          for text in (
              f"{T}/Your Activity/Watch History/VideoList/[]",
              f"{T}/Activity/Video Browsing History/VideoList/[]",  # the older path
              "/ads_information/ads_and_topics/videos_watched.json/[]",  # Instagram
              "%Y-%m-%d %H:%M:%S",
              "2026-09-01 08:15:42",  # an example value
              "Agreed by curators",
              "tz_whos",
              "UTC (a Unix timestamp",
              "Official documentation",
              "Video bekeken",  # a translation
          ):
              with self.subTest(text=text):
                  self.assertContains(response, text)
          self.assertNotContains(response, "Not in this database yet")

      def test_it_links_to_the_pages_that_exist(self):
          response = self.client.get(detail("watched-video"))
          for view in resolve(CONCEPTS_BY_SLUG["watched-video"]):
              self.assertContains(response, f'href="{view.annotation.get_absolute_url()}"')
          explorer = reverse("schemas:platform", args=["tiktok"])
          self.assertContains(response, f'href="{explorer}?q=VideoList"')
          self.assertContains(response, reverse("journeys:concepts"))

      def test_examples_are_a_table_of_title_and_value(self):
          response = self.client.get(detail("watched-video"))
          self.assertContains(response, '<th scope="col">Title</th>', html=True)
          self.assertContains(response, '<th scope="col">Value</th>', html=True)

      def test_markers_for_no_data_and_personal_data(self):
          response = self.client.get(detail("commented"))
          self.assertContains(response, "No data markers")
          self.assertContains(response, "<code>N/A</code>", html=True)
          self.assertContains(self.client.get(detail("sent-message")), "Personal data")
  ```

- [ ] **Step 2: Run and see them fail** (the placeholder answers 200 for any slug and shows none of this).

- [ ] **Step 3: Replace `concept_detail`**

  ```python
  def concept_detail(request: HttpRequest, slug: str) -> HttpResponse:
      """M2: what one concept means, and where and how each platform provides it."""
      concept = CONCEPTS_BY_SLUG.get(slug)
      if concept is None:
          raise Http404
      context = {
          "concept": concept,
          "views": resolve(concept),
          # its themes, per research field
          "themes": [
              (field.name, [theme.name for theme in field.themes if theme.slug in concept.themes])
              for field in FIELDS
          ],
      }
      return render_mockup(request, "concept", "journeys/prototype/concept.html", context)
  ```

  For the explorer link, the template needs the key of the list: add a property to `LocationView`, for example `search` (the last segment of the path that is not `[]`), and use `?q={{ entry.search|urlencode }}`.

- [ ] **Step 4: Write the template**, following "What the page shows" and the patterns of `concepts.html`. Use `<th scope="col">` in every table.

- [ ] **Step 5: Run the tests, reformat, look** (`/prototype/concepts/watched-video/` and `/prototype/concepts/commented/`, wide and narrow; the wide tables must scroll inside their `table-scroll` box).

- [ ] **Step 6: Task gate and commit**

  ```bash
  git add ddp_tracker/journeys
  uv run pre-commit run
  git commit -m "feat(journeys): add the concept detail mock-up (M2)"
  ```

**Acceptance:** the new tests pass; every concept's page answers 200 with and without demo data (add a loop over `CONCEPTS` to the tests if you want it proven).

---

## Task 3.3: Shortlist and exports (M3)

**Review:** full.

**Files:**

- Modify: `ddp_tracker/journeys/mockups/shortlist.py` (replace everything below the docstring)
- Create: `ddp_tracker/journeys/templates/journeys/prototype/shortlist.html`
- Create: `ddp_tracker/journeys/tests/test_shortlist.py`
- Modify: `prototype/concepts.html` and `prototype/concept.html` (add the "Add to shortlist" form)

**Interfaces:**

- Consumes: `CONCEPTS_BY_SLUG`, `resolve` and the view classes of task 3.1; `static/js/journeys.js` (task 2.2).
- Produces: a shortlist kept in the session under the key `journeys_shortlist` as `[{"concept": "<slug>", "note": "<text>"}, …]`; a shared shortlist as a link `?c=<slug>&c=<slug>`; two downloads.

**Behaviour:**

| Request | Does |
|---|---|
| `GET journeys:shortlist` | Shows the visitor's own shortlist (from the session). With `?c=…` in the link, shows **that** list instead, read-only, marked "A shared shortlist", without touching the session. Unknown slugs in the link are ignored. |
| `POST journeys:shortlist-add` | `concept` (one or several values) must all be known concepts, else 400. Adds them. If the form has a `note` field, sets the note (at most 300 characters) on those concepts. Then redirects to `next` if it is a local URL, else to the shortlist. Says so with a message ("Added to your shortlist: …"). |
| `POST journeys:shortlist-remove` | Removes `concept`. Redirects as above. |
| `POST journeys:shortlist-clear` | Empties the shortlist. |
| `GET journeys:shortlist-codebook` | The rows as CSV, as a download (`Content-Disposition: attachment; filename="ddp-tracker-codebook-prototype.csv"`). Uses `?c=…` if given, else the session. |
| `GET journeys:shortlist-blueprint` | The same rows as File Blueprints, JSON, as a download (`ddp-tracker-ddm-blueprints-prototype.json`). |

GET on the three POST routes answers 405 (`@require_POST`).

**Rows.** A row is one data point of a chosen concept: for an annotated list item, one row per direct field (path, type, format); for an annotated single value, the value itself. Rows come from `resolve(concept)`: every platform that has the annotation, every location (so the older TikTok path is there too: an engineer needs the variants).

**The page**, top to bottom:

- If shared: a note "A shared shortlist: what a researcher chose for a study." and a form "Save it as my shortlist" (POST to `shortlist-add` with one hidden `concept` input per concept).
- If empty: "Your shortlist is empty." with a link to the concept view and a link "Load an example shortlist" (`?c=watched-video&c=searched&c=liked-content`).
- "Chosen concepts": one entry per concept with its name (link to the concept), and, on one's own shortlist, a small form to write the note "Why this study needs it" (text input named `note`, button "Save note") and a form with the button "Remove <name>". On a shared one, no forms.
- "Data points" (`h2`): the rows as a table in a `table-scroll`: Concept, Platform, Path (`text-break`, `<code>`), Type, Format, Personal data, Whose time. Below it, if the database has no demo data: the note of rule 5.
- "Hand over" (`h2`, `id="share"`): a button "Copy the link for your engineer" with `class="btn btn-primary copy-button"` and `data-copy="<absolute link with ?c=…>"`; the link itself in a read-only text input with a label (so it can be copied without JavaScript); "Download the codebook (CSV)" and "Download DDM File Blueprints (JSON)" as links with `btn btn-secondary`, carrying the same `?c=…`.
- "Ethics summary" (`h2`): "N of M data points are flagged as personal data." and one sentence that this helps with an ethics application or a data protection impact assessment.
- "Preview" (`h2`): the codebook and the blueprints, each in `<pre class="code-sample">`.
- On one's own non-empty shortlist: a form with the button "Clear my shortlist" (`btn btn-outline-danger btn-sm`).
- The script: `<script src="{% static 'js/journeys.js' %}" defer></script>` at the top of the block (as the explorer page loads its script).

- [ ] **Step 1: Write the failing tests**

  `ddp_tracker/journeys/tests/test_shortlist.py`:

  ```python
  """M3, the study shortlist: kept in the session, shared as a link, downloaded as a codebook and
  as File Blueprints (mockups/shortlist.py)."""

  import csv
  import io
  import json

  from django.test import SimpleTestCase, TestCase
  from django.urls import reverse

  from ddp_tracker.journeys.mockups.shortlist import SESSION_KEY, split_path
  from ddp_tracker.journeys.tests.utils import SeededTestCase

  PAGE = reverse("journeys:shortlist")
  ADD = reverse("journeys:shortlist-add")
  REMOVE = reverse("journeys:shortlist-remove")
  CLEAR = reverse("journeys:shortlist-clear")
  CODEBOOK = reverse("journeys:shortlist-codebook")
  BLUEPRINT = reverse("journeys:shortlist-blueprint")
  T = "/user_data_tiktok.json"
  SHARED = "?c=watched-video&c=searched"


  class SplitPathTests(SimpleTestCase):
      def test_the_file_and_the_keys_inside_it(self):
          self.assertEqual(
              split_path(f"{T}/Your Activity/Watch History/VideoList/[]"),
              ("user_data_tiktok.json", ["Your Activity", "Watch History", "VideoList", "[]"]),
          )
          self.assertEqual(
              split_path("/your_instagram_activity/likes/liked_posts.json/[]/timestamp"),
              ("your_instagram_activity/likes/liked_posts.json", ["[]", "timestamp"]),
          )
          self.assertEqual(split_path("/folder/only"), ("folder/only", []))


  class ShortlistTests(TestCase):
      def chosen(self):
          return self.client.session.get(SESSION_KEY, [])

      def test_an_empty_shortlist_offers_a_start(self):
          response = self.client.get(PAGE)
          self.assertContains(response, "Your shortlist is empty")
          self.assertContains(response, reverse("journeys:concepts"))
          self.assertContains(response, "?c=watched-video&amp;c=searched&amp;c=liked-content")

      def test_adding_and_removing(self):
          response = self.client.post(ADD, {"concept": "watched-video"})
          self.assertRedirects(response, PAGE)
          self.client.post(ADD, {"concept": "searched", "note": "Exposure to news"})
          self.assertEqual(
              self.chosen(),
              [
                  {"concept": "watched-video", "note": ""},
                  {"concept": "searched", "note": "Exposure to news"},
              ],
          )
          page = self.client.get(PAGE)
          self.assertContains(page, "Watched a video")
          self.assertContains(page, "Exposure to news")
          self.client.post(ADD, {"concept": "watched-video"})  # twice: still once
          self.assertEqual(len(self.chosen()), 2)
          self.client.post(REMOVE, {"concept": "watched-video"})
          self.assertEqual([entry["concept"] for entry in self.chosen()], ["searched"])
          self.client.post(CLEAR)
          self.assertEqual(self.chosen(), [])

      def test_a_note_can_be_changed_and_is_kept_when_adding_again(self):
          self.client.post(ADD, {"concept": "searched", "note": "First"})
          self.client.post(ADD, {"concept": "searched"})  # no note field: the note stays
          self.assertEqual(self.chosen()[0]["note"], "First")
          self.client.post(ADD, {"concept": "searched", "note": "x" * 400})
          self.assertEqual(len(self.chosen()[0]["note"]), 300)

      def test_only_known_concepts_and_only_by_post(self):
          self.assertEqual(self.client.post(ADD, {"concept": "nope"}).status_code, 400)
          self.assertEqual(self.client.post(ADD).status_code, 400)
          for url in (ADD, REMOVE, CLEAR):
              self.assertEqual(self.client.get(url).status_code, 405)
          self.assertEqual(self.chosen(), [])

      def test_it_returns_to_where_the_visitor_was_if_that_is_here(self):
          back = reverse("journeys:concepts") + "?field=health"
          response = self.client.post(ADD, {"concept": "searched", "next": back})
          self.assertRedirects(response, back)
          response = self.client.post(ADD, {"concept": "searched", "next": "https://example.org/"})
          self.assertRedirects(response, PAGE)

      def test_adding_says_so(self):
          response = self.client.post(ADD, {"concept": "searched"}, follow=True)
          self.assertContains(response, "Added to your shortlist")

      def test_a_shared_link_shows_its_own_list_and_leaves_mine_alone(self):
          self.client.post(ADD, {"concept": "logged-in"})
          response = self.client.get(PAGE + SHARED + "&c=nope")
          self.assertContains(response, "A shared shortlist")
          self.assertContains(response, "Watched a video")
          self.assertContains(response, "Searched")
          self.assertNotContains(response, "Save note")  # read-only
          self.assertEqual([entry["concept"] for entry in self.chosen()], ["logged-in"])

      def test_a_shared_shortlist_can_be_saved(self):
          self.client.post(ADD, {"concept": ["watched-video", "searched"]})
          self.assertEqual(len(self.chosen()), 2)

      def test_the_link_to_hand_over(self):
          self.client.post(ADD, {"concept": "watched-video"})
          self.client.post(ADD, {"concept": "searched"})
          response = self.client.get(PAGE)
          self.assertContains(
              response,
              'data-copy="http://testserver/prototype/shortlist/?c=watched-video&amp;c=searched"',
          )
          self.assertContains(response, f"{CODEBOOK}?c=watched-video&amp;c=searched")
          self.assertContains(response, "js/journeys.js")


  class ShortlistWithDataTests(SeededTestCase):
      def test_the_data_points_of_the_chosen_concepts(self):
          response = self.client.get(PAGE + SHARED)
          for text in (
              f"{T}/Your Activity/Watch History/VideoList/[]/Date",
              f"{T}/Activity/Video Browsing History/VideoList/[]/Link",  # the older variant too
              "/logged_information/search/your_search_history.json/searches_v2/[]/timestamp",
              "%Y-%m-%d %H:%M:%S",
              "UTC (assumed",
          ):
              with self.subTest(text=text):
                  self.assertContains(response, text)

      def test_the_codebook(self):
          response = self.client.get(CODEBOOK + SHARED)
          self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
          self.assertIn(
              'filename="ddp-tracker-codebook-prototype.csv"', response["Content-Disposition"]
          )
          rows = list(csv.DictReader(io.StringIO(response.content.decode())))
          self.assertEqual(
              list(rows[0]),
              [
                  "concept",
                  "platform",
                  "annotation",
                  "path",
                  "type",
                  "format",
                  "personal_data",
                  "tz_whos",
                  "first_seen",
                  "last_seen",
                  "note",
                  "source",
              ],
          )
          date = next(
              row
              for row in rows
              if row["path"] == f"{T}/Your Activity/Watch History/VideoList/[]/Date"
          )
          self.assertEqual(
              (date["concept"], date["platform"], date["annotation"], date["type"], date["format"]),
              ("Watched a video", "TikTok", "Watched video", "string", "%Y-%m-%d %H:%M:%S"),
          )
          self.assertEqual((date["first_seen"], date["personal_data"]), ("2026-09-15", "no"))
          self.assertIn("prototype", date["source"])
          self.assertEqual({row["platform"] for row in rows}, {"TikTok", "Instagram", "Facebook"})

      def test_the_codebook_of_my_own_shortlist_has_my_notes(self):
          self.client.post(ADD, {"concept": "sent-message", "note": "Social support"})
          rows = list(csv.DictReader(io.StringIO(self.client.get(CODEBOOK).content.decode())))
          self.assertEqual({row["note"] for row in rows}, {"Social support"})
          self.assertEqual({row["personal_data"] for row in rows}, {"yes"})

      def test_the_blueprints(self):
          response = self.client.get(BLUEPRINT + SHARED)
          self.assertIn("ddm-blueprints-prototype.json", response["Content-Disposition"])
          data = json.loads(response.content)
          self.assertTrue(data["prototype"])
          self.assertIn("Illustrative", data["note"])
          by_name: dict[str, list[dict]] = {}
          for blueprint in data["blueprints"]:
              by_name.setdefault(blueprint["name"], []).append(blueprint)
          current, older = by_name["TikTok: Watched a video"]  # the path in use now first
          self.assertEqual(current["expected_file"], "user_data_tiktok.json")
          self.assertEqual(current["file_format"], "json")
          self.assertEqual(current["list_at"], ["Your Activity", "Watch History", "VideoList"])
          self.assertEqual(current["required_fields"], ["Date", "Link"])
          self.assertEqual(current["fields_to_keep"], ["Date", "Link"])
          self.assertEqual(older["list_at"], ["Activity", "Video Browsing History", "VideoList"])

      def test_a_variable_folder_becomes_a_pattern(self):
          data = json.loads(self.client.get(BLUEPRINT + "?c=sent-message").content)
          instagram = next(b for b in data["blueprints"] if b["platform"] == "instagram")
          self.assertEqual(
              instagram["expected_file"], "your_instagram_activity/messages/inbox/*/message_1.json"
          )
          self.assertEqual(instagram["list_at"], ["messages"])
          self.assertEqual(instagram["required_fields"], ["content"])
          self.assertTrue(instagram["personal_data"])

      def test_the_ethics_summary_counts_personal_data(self):
          response = self.client.get(PAGE + "?c=sent-message&c=searched")
          self.assertEqual(response.context["personal"], 3)  # the message text on three platforms
          self.assertContains(response, "flagged as personal data")

      def test_the_previews_are_on_the_page(self):
          response = self.client.get(PAGE + SHARED)
          self.assertContains(response, "concept,platform,annotation,path")
          self.assertContains(
              response, "&quot;expected_file&quot;: &quot;user_data_tiktok.json&quot;"
          )

      def test_concept_pages_add_to_the_shortlist(self):
          for url in (reverse("journeys:concepts"), reverse("journeys:concept", args=["searched"])):
              with self.subTest(url=url):
                  response = self.client.get(url)
                  self.assertContains(response, f'action="{ADD}"')
                  self.assertContains(response, 'name="concept" value="searched"')
                  self.assertContains(response, "csrfmiddlewaretoken")
  ```

- [ ] **Step 2: Run and see them fail** (an import error: `SESSION_KEY`).

- [ ] **Step 3: Write `mockups/shortlist.py`**

  Keep the module docstring, replace the rest. The reference implementation (adapt to what the linter and the type checker ask for):

  ```python
  import csv
  import io
  import json
  import re
  from dataclasses import dataclass
  from datetime import date
  from typing import Any
  from urllib.parse import urlencode

  from django.contrib import messages
  from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, JsonResponse
  from django.shortcuts import redirect
  from django.urls import reverse
  from django.utils.http import url_has_allowed_host_and_scheme
  from django.views.decorators.http import require_POST

  from ddp_tracker.journeys.mockups import render_mockup
  from ddp_tracker.journeys.mockups.concepts import CONCEPTS_BY_SLUG, Concept, resolve
  from ddp_tracker.schemas.models import ITEM

  SESSION_KEY = "journeys_shortlist"  # [{"concept": slug, "note": text}] in the visitor's session
  MAX_NOTE = 300
  EXAMPLE = ("watched-video", "searched", "liked-content")
  SOURCE = "DDP Tracker prototype: fictional demo data"
  BLUEPRINT_NOTE = (
      "Illustrative only. It follows the fields of a File Blueprint as described by Pfiffner, "
      "Witlox and Friemel (2024), not the import format of the Data Donation Module."
  )
  COLUMNS = (
      "concept",
      "platform",
      "annotation",
      "path",
      "type",
      "format",
      "personal_data",
      "tz_whos",
      "first_seen",
      "last_seen",
      "note",
      "source",
  )


  @dataclass(frozen=True)
  class Entry:
      concept: Concept
      note: str = ""


  @dataclass(frozen=True)
  class Row:
      """One data point of the shortlist: a field of a list's item, or a single value."""

      concept: str
      platform: str
      platform_slug: str
      annotation: str
      path: str
      parent: str  # the list's item the field belongs to; "" for a single value
      value_type: str
      value_format: str
      pii: bool
      tz_whos: str
      first_seen: date | None
      last_seen: date | None
      note: str


  # --- which concepts: the visitor's own (session) or the ones a shared link names ------------


  def stored(request: HttpRequest) -> list[Entry]:
      """The visitor's own shortlist."""
      return [
          Entry(CONCEPTS_BY_SLUG[item["concept"]], item.get("note", ""))
          for item in request.session.get(SESSION_KEY, [])
          if item.get("concept") in CONCEPTS_BY_SLUG
      ]


  def shared(request: HttpRequest) -> list[Entry] | None:
      """The shortlist a link names (``?c=…&c=…``), or None if the link names none."""
      slugs = request.GET.getlist("c")
      if not slugs:
          return None
      return [
          Entry(CONCEPTS_BY_SLUG[slug]) for slug in dict.fromkeys(slugs) if slug in CONCEPTS_BY_SLUG
      ]


  def _chosen(request: HttpRequest) -> list[Entry]:
      from_link = shared(request)
      return stored(request) if from_link is None else from_link


  def _save(request: HttpRequest, entries: list[Entry]) -> None:
      request.session[SESSION_KEY] = [
          {"concept": entry.concept.slug, "note": entry.note} for entry in entries
      ]


  # --- the data points, and the two exports -----------------------------------------------------


  def rows(entries: list[Entry]) -> list[Row]:
      """The data points of the chosen concepts, on every platform and at every path the
      database knows (an older path is a variant the engineer has to handle)."""
      found = []
      for entry in entries:
          for view in resolve(entry.concept):
              if view.annotation is None:
                  continue
              for location in view.locations:
                  is_item = location.location.path.endswith(ITEM)
                  found += [
                      Row(
                          concept=entry.concept.name,
                          platform=view.name,
                          platform_slug=view.binding.platform,
                          annotation=view.annotation.name,
                          path=field.location.path,
                          parent=location.location.path if is_item else "",
                          value_type=field.profile.main_type,
                          value_format=field.profile.main_format,
                          pii=view.annotation.pii,
                          tz_whos=view.binding.tz_whos,
                          first_seen=field.profile.first_seen,
                          last_seen=field.profile.last_seen,
                          note=entry.note,
                      )
                      for field in location.fields
                  ]
      return found


  def codebook_csv(found: list[Row]) -> str:
      out = io.StringIO()
      writer = csv.writer(out, lineterminator="\n")
      writer.writerow(COLUMNS)
      for row in found:
          writer.writerow(
              [
                  row.concept,
                  row.platform,
                  row.annotation,
                  row.path,
                  row.value_type,
                  row.value_format,
                  "yes" if row.pii else "no",
                  row.tz_whos,
                  row.first_seen or "",
                  row.last_seen or "",
                  row.note,
                  SOURCE,
              ]
          )
      return out.getvalue()


  _FILE = re.compile(r"\.(json|jsonl|csv|js)$", re.IGNORECASE)


  def split_path(path: str) -> tuple[str, list[str]]:
      """A path as the file and the keys inside it: ``/a/b.json/x/[]/y`` gives
      ``("a/b.json", ["x", "[]", "y"])``. Without a file in it: the whole path, no keys."""
      segments = path.strip("/").split("/")
      for index, segment in enumerate(segments):
          if _FILE.search(segment):
              return "/".join(segments[: index + 1]), segments[index + 1 :]
      return "/".join(segments), []


  def blueprints(found: list[Row]) -> dict[str, Any]:
      """The rows as File Blueprints: per list (or single value), the file to expect, where the
      list is in it, and the fields to require and keep."""
      groups: dict[tuple[str, str, str], list[Row]] = {}
      for row in found:
          groups.setdefault((row.platform, row.concept, row.parent or row.path), []).append(row)
      items = []
      for (platform, concept, anchor), members in groups.items():
          file, keys = split_path(anchor)
          if keys and keys[-1] == "[]":  # a list: its items' fields
              list_at = keys[:-1]
              fields = [member.path.rsplit("/", 1)[1] for member in members]
          else:  # a single value: its key, in the list (or object) that holds it
              list_at = [key for key in keys[:-1] if key != "[]"]
              fields = keys[-1:]
          items.append(
              {
                  "name": f"{platform}: {concept}",
                  "platform": members[0].platform_slug,
                  "expected_file": file.replace("{*}", "*"),
                  "file_format": file.rsplit(".", 1)[-1].lower(),
                  "list_at": list_at,
                  "required_fields": fields,
                  "fields_to_keep": fields,
                  "personal_data": members[0].pii,
              }
          )
      return {"prototype": True, "note": BLUEPRINT_NOTE, "generated_by": SOURCE, "blueprints": items}


  # --- views -----------------------------------------------------------------------------------


  def shortlist(request: HttpRequest) -> HttpResponse:
      """M3: the chosen concepts with their data points, the link to hand over, the downloads."""
      from_link = shared(request)
      entries = stored(request) if from_link is None else from_link
      found = rows(entries)
      query = urlencode([("c", entry.concept.slug) for entry in entries])
      share_url = request.build_absolute_uri(f"{reverse('journeys:shortlist')}?{query}")
      context = {
          "entries": entries,
          "rows": found,
          "is_shared": from_link is not None,
          "query": query,
          "share_url": share_url if entries else "",
          "personal": sum(row.pii for row in found),
          "codebook": codebook_csv(found),
          "blueprint": json.dumps(blueprints(found), indent=2),
          "example_query": urlencode([("c", slug) for slug in EXAMPLE]),
      }
      return render_mockup(request, "shortlist", "journeys/prototype/shortlist.html", context)


  def _back(request: HttpRequest) -> HttpResponse:
      """To where the visitor was (``next``), if that is on this site; else to the shortlist."""
      target = request.POST.get("next", "")
      if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
          target = reverse("journeys:shortlist")
      return redirect(target)


  @require_POST
  def add(request: HttpRequest) -> HttpResponse:
      """Add concepts to the visitor's shortlist; with a ``note`` field, set their note."""
      slugs = request.POST.getlist("concept")
      if not slugs or any(slug not in CONCEPTS_BY_SLUG for slug in slugs):
          return HttpResponseBadRequest("Unknown concept.")
      entries = {entry.concept.slug: entry for entry in stored(request)}
      for slug in slugs:
          note = entries[slug].note if slug in entries else ""
          if "note" in request.POST:
              note = request.POST["note"].strip()[:MAX_NOTE]
          entries[slug] = Entry(CONCEPTS_BY_SLUG[slug], note)
      _save(request, list(entries.values()))
      names = ", ".join(CONCEPTS_BY_SLUG[slug].name for slug in slugs)
      messages.success(request, f"Added to your shortlist: {names}.")
      return _back(request)


  @require_POST
  def remove(request: HttpRequest) -> HttpResponse:
      slug = request.POST.get("concept", "")
      _save(request, [entry for entry in stored(request) if entry.concept.slug != slug])
      return _back(request)


  @require_POST
  def clear(request: HttpRequest) -> HttpResponse:
      _save(request, [])
      return _back(request)


  def codebook(request: HttpRequest) -> HttpResponse:
      """The shortlist as a codebook (CSV), to download."""
      name = "ddp-tracker-codebook-prototype.csv"
      return HttpResponse(
          codebook_csv(rows(_chosen(request))),
          content_type="text/csv; charset=utf-8",
          headers={"Content-Disposition": f'attachment; filename="{name}"'},
      )


  def blueprint(request: HttpRequest) -> HttpResponse:
      """The shortlist as File Blueprints for the Data Donation Module (JSON), to download."""
      name = "ddp-tracker-ddm-blueprints-prototype.json"
      return JsonResponse(
          blueprints(rows(_chosen(request))),
          json_dumps_params={"indent": 2},
          headers={"Content-Disposition": f'attachment; filename="{name}"'},
      )
  ```

  Two things to check while you make the tests pass:

  - In `test_the_blueprints` the TikTok watch history gives two blueprints with the same name, the path in use now first: `rows()` follows the order of `view.locations`, which `resolve` sorts that way.
  - In `test_a_variable_folder_becomes_a_pattern` the annotated location is a single value inside a list (`…/messages/[]/content`): its `list_at` is `["messages"]`.

- [ ] **Step 4: Write the template `prototype/shortlist.html`** after "The page" above.

- [ ] **Step 5: Add the form to the two concept pages.** In `concepts.html`, in each card; in `concept.html`, under the heading:

  ```django
  <form method="post" action="{% url 'journeys:shortlist-add' %}" class="inline-form">
    {% csrf_token %}
    <input type="hidden" name="concept" value="{{ card.concept.slug }}">
    <input type="hidden" name="next" value="{{ request.get_full_path }}">
    <button type="submit" class="btn btn-secondary btn-sm">Add {{ card.concept.name }} to the shortlist</button>
  </form>
  ```

  (In `concept.html` it is `concept.slug` and `concept.name`.) The button's text names the concept, so that every button on the page reads differently. Also add, on both pages, a link "Open the study shortlist" to `journeys:shortlist`.

- [ ] **Step 6: Run the tests, reformat, look.** Try the whole hand-off by hand: `/prototype/concepts/`, add two concepts, open the shortlist, write a note, copy the link, open the link in a private window, download both files and open them.

- [ ] **Step 7: Task gate and commit**

  ```bash
  git add ddp_tracker/journeys
  uv run pre-commit run
  git commit -m "feat(journeys): add the study shortlist mock-up with its exports (M3)"
  ```

**Acceptance:** the tests of `test_shortlist.py` pass; the hand-off of step 6 works by hand; the session holds only concept slugs and notes (nothing about the user); no JavaScript is needed for anything but the copy button.

---

## Task 3.4: Changelog (M5)

**Review:** full.

**Files:**

- Modify: `ddp_tracker/journeys/mockups/changes.py`
- Create: `ddp_tracker/journeys/templates/journeys/prototype/changes.html`
- Create: `ddp_tracker/journeys/tests/test_changes.py`

**Interfaces:**

- Consumes: `find_platform`, `render_mockup`; `ddp_tracker.schemas.timeline.new_in` and `change_details`.
- Produces: `timeline(platform) -> list[Entry]`.

**What the page shows:** heading "<Platform>: changelog". If the platform is in the database: one `timeline__entry` per registered upload, newest request first, with its request date as the entry's heading and:

- the first one: "First package: N data points. There is nothing earlier to compare it with."
- a later one: a sentence that sums it up ("5 added, 33 moved or renamed, 1 changed, 1 removed, compared with the requests before it."), then four lists with headings: "Added" (paths), "Moved or renamed" (from, to), "Changed" (path, which field, before, now), "Removed" (paths). A list longer than 8 shows its first 8 and "and N more" (Django's `slice` filter). An empty list is left out.

Below the timeline: links to the other platforms' changelogs; a note that today this is only visible per upload, in its review, to the uploader and staff. If the platform has no registered upload (YouTube in the demo data): "No package counts for <Platform> yet." If the platform is not in the database: the note of rule 5.

Two controls that would exist in the real feature, shown disabled with the sentence "In the real feature, this would …": "Compare two dates" and "Tell me when <Platform> changes" (both `<button type="button" class="btn btn-secondary btn-sm" disabled>`).

- [ ] **Step 1: Write the failing tests**

  `ddp_tracker/journeys/tests/test_changes.py`:

  ```python
  """M5, a platform's changelog: what it added, moved, changed and removed between requests,
  computed from the observations (mockups/changes.py)."""

  from datetime import date

  from django.test import TestCase
  from django.urls import reverse

  from ddp_tracker.ddps.models import Platform
  from ddp_tracker.journeys.mockups.changes import timeline
  from ddp_tracker.journeys.tests.utils import SeededTestCase

  T = "/user_data_tiktok.json"
  LIKE_DATE = f"{T}/Likes and Favorites/Like List/ItemFavoriteList/[]/date"


  def page(slug):
      return reverse("journeys:changes", args=[slug])


  class ChangelogWithoutDataTests(TestCase):
      def test_a_demo_platform_without_data_says_so(self):
          response = self.client.get(page("tiktok"))
          self.assertContains(response, "TikTok: changelog")
          self.assertContains(response, "seed_demo")


  class ChangelogTests(SeededTestCase):
      def test_the_timeline_of_tiktok(self):
          september, march = timeline(Platform.objects.get(slug="tiktok"))  # newest first
          self.assertEqual(
              (march.upload.requested_at, september.upload.requested_at),
              (date(2026, 3, 15), date(2026, 9, 15)),
          )
          self.assertTrue(march.first)
          self.assertEqual((march.added, march.moved, march.changed, march.removed), ([], [], [], []))
          self.assertFalse(september.first)
          self.assertEqual(september.data_points, 156)
          # the live section is new; nothing else is
          self.assertEqual(len(september.added), 5)
          self.assertTrue(all("/Tiktok Live/" in path for path in september.added))
          # the renamed section's data points are recognised, not reported as new and removed
          self.assertIn(
              (
                  f"{T}/Activity/Video Browsing History/VideoList/[]",
                  f"{T}/Your Activity/Watch History/VideoList/[]",
              ),
              september.moved,
          )
          self.assertEqual(len(september.moved), 33)
          (change,) = september.changed
          self.assertEqual(
              (change.path, change.field, change.before, change.now),
              (LIKE_DATE, "format", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"),
          )
          self.assertEqual(
              september.removed, [f"{T}/Profile And Settings/Profile Info/ProfileMap/likesReceived"]
          )

      def test_the_page(self):
          response = self.client.get(page("tiktok"))
          for text in (
              "TikTok: changelog",
              "5 added, 33 moved or renamed, 1 changed, 1 removed",
              "Tiktok Live",
              "Video Browsing History",
              "%Y-%m-%dT%H:%M:%SZ",
              "likesReceived",
              "First package",
              "and 25 more",  # 33 moved, 8 shown
              "In the real feature, this would",
          ):
              with self.subTest(text=text):
                  self.assertContains(response, text)
          self.assertContains(response, page("instagram"))

      def test_a_platform_with_one_package(self):
          (only,) = timeline(Platform.objects.get(slug="instagram"))
          self.assertTrue(only.first)
          self.assertContains(self.client.get(page("instagram")), "First package")

      def test_a_platform_without_a_package_that_counts(self):
          self.assertEqual(timeline(Platform.objects.get(slug="youtube")), [])
          self.assertContains(self.client.get(page("youtube")), "No package counts for YouTube yet")

      def test_it_never_names_an_uploader(self):
          response = self.client.get(page("tiktok"))
          self.assertNotContains(response, "@example.org")
  ```

- [ ] **Step 2: Run and see them fail** (an import error: `timeline`).

- [ ] **Step 3: Write `mockups/changes.py`**

  Keep the docstring. The computation was run against the demo data while planning and gave the figures the tests expect:

  ```python
  from dataclasses import dataclass

  from django.http import HttpRequest, HttpResponse

  from ddp_tracker.ddps.models import Platform, Upload
  from ddp_tracker.journeys.mockups import DEMO_PLATFORMS, find_platform, render_mockup
  from ddp_tracker.schemas.timeline import change_details, new_in


  @dataclass(frozen=True)
  class Change:
      path: str
      field: str  # kind, type, shape or format
      before: str  # what earlier requests had
      now: str


  @dataclass(frozen=True)
  class Entry:
      """One request of the platform, compared with the ones requested before it."""

      upload: Upload
      first: bool  # nothing earlier to compare with
      data_points: int
      added: list[str]  # new, and unlike anything earlier
      moved: list[tuple[str, str]]  # (the earlier path, the path now)
      changed: list[Change]
      removed: list[str]  # in the request before, gone now, and not moved


  def timeline(platform: Platform) -> list[Entry]:
      """The platform's uploads that count, newest request first, each with what changed since
      the requests before it. "New" and "changed" are the review's (``schemas/timeline.py``): they
      compare with uploads requested strictly earlier."""
      uploads = list(
          platform.uploads.filter(registered_at__isnull=False).order_by("requested_at", "pk")
      )
      entries = []
      for upload in uploads:
          observations = list(
              upload.observations.filter(is_data_point=True).select_related("location")
          )
          paths = {observation.location_id: observation.location.path for observation in observations}
          earlier = [other for other in uploads if other.requested_at < upload.requested_at]
          if not earlier:
              entries.append(
                  Entry(
                      upload=upload,
                      first=True,
                      data_points=len(paths),
                      added=[],
                      moved=[],
                      changed=[],
                      removed=[],
                  )
              )
              continue
          new = new_in(upload)
          fresh = [observation for observation in observations if observation.location_id in new]
          moved = sorted(
              (observation.suggestions[0]["path"], observation.location.path)
              for observation in fresh
              if observation.suggestions
          )
          added = sorted(o.location.path for o in fresh if not o.suggestions)
          changed = sorted(
              (
                  Change(paths[location_id], change.field, ", ".join(change.before), change.now)
                  for location_id, found in change_details(upload).items()
                  if location_id in paths  # data points only
                  for change in found
              ),
              key=lambda change: (change.path, change.field),
          )
          before = set(
              earlier[-1]
              .observations.filter(is_data_point=True)
              .values_list("location__path", flat=True)
          )
          removed = sorted(before - set(paths.values()) - {source for source, _ in moved})
          entries.append(
              Entry(
                  upload=upload,
                  first=False,
                  data_points=len(paths),
                  added=added,
                  moved=moved,
                  changed=changed,
                  removed=removed,
              )
          )
      return entries[::-1]


  def changes(request: HttpRequest, slug: str) -> HttpResponse:
      """M5: the changelog of one platform."""
      name, platform = find_platform(slug)
      context = {
          "platform_name": name,
          "platform": platform,
          "entries": timeline(platform) if platform is not None else [],
          "others": [(other, label) for other, label in DEMO_PLATFORMS.items() if other != slug],
      }
      return render_mockup(request, "changes", "journeys/prototype/changes.html", context)
  ```

- [ ] **Step 4: Write the template** after "What the page shows". The heading: `{% block heading %}{{ platform_name }}: changelog{% endblock %}`. The summary sentence only names what occurred, in this order and wording, separated by commas: "N added", "N moved or renamed", "N changed", "N removed" (the test expects "5 added, 33 moved or renamed, 1 changed, 1 removed"). Building that sentence in the view (a property `summary` on `Entry`) is simpler than in the template.

- [ ] **Step 5: Run the tests, reformat, look** at `/prototype/platforms/tiktok/changes/`, `/instagram/` and `/youtube/`.

- [ ] **Step 6: Task gate and commit**

  ```bash
  git add ddp_tracker/journeys
  uv run pre-commit run
  git commit -m "feat(journeys): add the platform changelog mock-up, computed from observations (M5)"
  ```

**Acceptance:** the tests pass; the page shows paths only (no upload id, no uploader, no file name).

---

## Task 3.5: API overview (M6)

**Review:** light.

**Files:**

- Modify: `ddp_tracker/journeys/mockups/api.py` (replace the placeholder view)
- Create: `ddp_tracker/journeys/templates/journeys/prototype/api.html`
- Create: `ddp_tracker/journeys/tests/test_api.py`

**Interfaces:** consumes `ENDPOINTS`, `EXPORTS`, `LLMS_TXT`, `MCP_TOOLS`, `LICENCE`, `BASE` (in the module). The journeys link to the anchors `#schema`, `#exports`, `#llm`: they must exist as `id`s.

**What the page shows:**

- An introduction: read-only, no account, JSON; "django-ninja is already a dependency of the tracker and would also generate the interactive documentation (OpenAPI)"; the base address `BASE`, with the fictional label.
- A table of contents: the endpoints, "Exports", "For language models", "Licence".
- "Endpoints" (`h2`): per endpoint a `<section class="endpoint" id="<anchor>">` with `h3`: the method in `<span class="endpoint__method">` and the path in `<code>`; the summary; "Request" and "Response" as `<pre class="code-sample">`.
- "Exports" (`h2`, `id="exports"`): the three exports as a table (Name, Address, For), and a sentence that the study shortlist offers the codebook and the blueprints today as a mock-up (link to `journeys:shortlist`).
- "For language models" (`h2`, `id="llm"`): what an `llms.txt` file is, in one sentence, and `LLMS_TXT` in a `code-sample`; "An MCP server over the API would offer these tools:" and the tools as a definition list; a sentence on why that matters here (an assistant can then answer "which platform tells me what people searched for?" from the tracker's own data).
- "Snapshots": one sentence and a link to `journeys:snapshots`.
- "Licence" (`h2`, `id="licence"`): the text `LICENCE`.

- [ ] **Step 1: Write the failing tests**

  `ddp_tracker/journeys/tests/test_api.py`:

  ```python
  """M6, the API overview: endpoints with examples, exports, access for language models."""

  import json

  from django.test import SimpleTestCase, TestCase
  from django.urls import reverse

  from ddp_tracker.journeys.content import ROLES
  from ddp_tracker.journeys.mockups.api import BASE, ENDPOINTS, EXPORTS, MCP_TOOLS

  PAGE = reverse("journeys:api")


  class ApiDataTests(SimpleTestCase):
      def test_every_example_answer_is_json(self):
          for endpoint in ENDPOINTS:
              with self.subTest(endpoint=endpoint.path):
                  json.loads(endpoint.response)
                  self.assertIn(BASE, endpoint.request)

      def test_the_address_is_an_example_address(self):
          self.assertIn("example.org", BASE)  # nothing points at the live site


  class ApiPageTests(TestCase):
      def test_the_endpoints_with_their_examples(self):
          response = self.client.get(PAGE)
          for endpoint in ENDPOINTS:
              with self.subTest(endpoint=endpoint.path):
                  self.assertContains(response, f'id="{endpoint.anchor}"')
                  self.assertContains(response, endpoint.path)
          self.assertContains(response, "&quot;name&quot;: &quot;Watched video&quot;")
          self.assertContains(response, "django-ninja")

      def test_the_anchors_the_journeys_link_to(self):
          response = self.client.get(PAGE)
          fragments = {
              step.fragment
              for role in ROLES
              for step in role.steps
              if step.url_name == "journeys:api" and step.fragment
          }
          self.assertEqual(fragments, {"schema", "exports", "llm"})
          for fragment in fragments:
              self.assertContains(response, f'id="{fragment}"')

      def test_exports_language_models_and_licence(self):
          response = self.client.get(PAGE)
          for export in EXPORTS:
              self.assertContains(response, export.name)
          for name, _ in MCP_TOOLS:
              self.assertContains(response, name)
          self.assertContains(response, "llms.txt")
          self.assertContains(response, "CC BY 4.0")
          self.assertContains(response, reverse("journeys:shortlist"))
          self.assertContains(response, reverse("journeys:snapshots"))

      def test_explainers_for_participants(self):
          response = self.client.get(PAGE)
          self.assertContains(response, 'id="explainers"')
          self.assertContains(response, "donation tool")
  ```

- [ ] **Step 2: Run and see them fail.**

- [ ] **Step 3: Replace the view**

  ```python
  def api_overview(request: HttpRequest) -> HttpResponse:
      """M6: what a read-only API could offer."""
      context = {
          "base": BASE,
          "endpoints": ENDPOINTS,
          "exports": EXPORTS,
          "llms_txt": LLMS_TXT,
          "mcp_tools": MCP_TOOLS,
          "licence": LICENCE,
      }
      return render_mockup(request, "api", "journeys/prototype/api.html", context)
  ```

- [ ] **Step 4: Write the template** after "What the page shows". Example text goes into `<pre class="code-sample">{{ endpoint.response }}</pre>` (autoescaping keeps it safe; do not mark anything safe).

- [ ] **Step 5: Run the tests, reformat, look** (the code blocks scroll sideways inside their box at phone width).

- [ ] **Step 6: Task gate and commit**

  ```bash
  git add ddp_tracker/journeys
  uv run pre-commit run
  git commit -m "feat(journeys): add the API overview mock-up (M6)"
  ```

**Acceptance:** the tests pass; the page has no link to the live site's address.

---

## Task 3.6: Screenshots and check-in (coordinator)

- [ ] Fresh database, seed, server, screenshots tool (as in task 2.3). No PROBLEM lines.
- [ ] Walk the core story by hand in the browser pane, once as a visitor: landing page, "Substantive researcher", step 1 to step 5; then "Research engineer", step 1 to step 5. Every link must land where the step says.
- [ ] Phase gate.
- [ ] Check in with Hekmat. Show: the concept view (two fields), a concept detail, the shortlist with its previews, the TikTok changelog, the API page. Ask the one question. Also ask: is the shortlist's blueprint close enough to what the track means by a DDM File Blueprint, or should it be labelled differently?
