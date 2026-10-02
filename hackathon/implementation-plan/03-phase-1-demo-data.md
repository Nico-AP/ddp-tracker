# 03. Phase 1: demo data

Output: `uv run manage.py seed_demo` turns a freshly migrated database into a demo, through the site's own code paths. Two tasks. Background: `../handoff-user-journeys/07-demo-data.md`.

What this phase creates (all verified in a scratch database, see `README.md`):

| Kind | What |
|---|---|
| Users | `demo-admin@example.org` (staff, superuser) and `demo-curator@example.org` (not staff), both with a verified e-mail address |
| Platforms | Facebook, Instagram, TikTok, YouTube |
| Uploads | TikTok requested 15 March 2026 (approved as the first of its kind); TikTok 15 September 2026 (passes by itself, similarity 0.97); Instagram and Facebook 15 September 2026 (approved); YouTube 15 September 2026 by the demo curator (**held**, waiting for approval) |
| Annotations | 28 (TikTok 12, Instagram 8, Facebook 8); "Watched video" covers the old and the new TikTok path |
| Representations | 9, with metadata links |
| Example values | 21, on 18 data points |
| For the queues | 1 open suggestion and 1 suggested vocabulary term ("liked") from the demo curator; 1 upload to approve |

What the September TikTok review then shows: 38 new data points, of which 33 are recognised as moved from the older section names and 5 are new outright (Tiktok Live); 1 changed (the date format of the like list); 1 missing (`likesReceived`).

---

## Task 1.1: App skeleton and fictional packages

**Review:** full.

**Files:**

- Create: `ddp_tracker/journeys/__init__.py` (empty)
- Create: `ddp_tracker/journeys/apps.py`
- Create: `ddp_tracker/journeys/demo/__init__.py` (empty)
- Create: `ddp_tracker/journeys/demo/ddps.py`
- Create: `ddp_tracker/journeys/tests/__init__.py` (empty)
- Create: `ddp_tracker/journeys/tests/test_demo_ddps.py`
- Modify: `config/settings/base.py` (one line in `LOCAL_APPS`)

**Interfaces:**

- Consumes: the generator `C:\Users\hekma\Documents\Projects\DDP-Tracker-docs\sample-ddps\make_sample_ddps.py` (read it; it is the source of `ddps.py`), and `ddp_parser.parse`, `ddp_parser.walk` in the tests.
- Produces, in `ddp_tracker.journeys.demo.ddps`:

  ```python
  SEPTEMBER: datetime            # datetime(2026, 9, 15, 10, 30, tzinfo=UTC)
  MARCH: datetime                # datetime(2026, 3, 15, 10, 30, tzinfo=UTC)
  TIKTOK_FILE = "user_data_tiktok.json"
  type Files = dict[str, Any]    # zip member name → bytes (as is), str (UTF-8 text), or JSON data
  def tiktok(request_date: datetime = SEPTEMBER) -> Files
  def tiktok_march() -> Files
  def instagram() -> Files
  def facebook() -> Files
  def youtube() -> Files
  def build_zip(files: Files) -> bytes
  ```

**Why a module and not zip files:** no binary files and no personal-looking data go into git. The packages are built in memory each time, from a fixed seed.

- [ ] **Step 1: Create the app skeleton**

  `ddp_tracker/journeys/apps.py`:

  ```python
  from django.apps import AppConfig


  class JourneysConfig(AppConfig):
      default_auto_field = "django.db.models.BigAutoField"
      name = "ddp_tracker.journeys"
      verbose_name = "User journeys (prototype)"
  ```

  In `config/settings/base.py`, add the app at the end of `LOCAL_APPS`:

  ```python
      "ddp_tracker.users",
      "ddp_tracker.journeys",
  ]
  ```

  Create the three empty `__init__.py` files.

- [ ] **Step 2: Write the failing tests**

  `ddp_tracker/journeys/tests/test_demo_ddps.py`:

  ```python
  """The fictional packages that seed_demo uploads (demo/ddps.py): the same on every run, and
  parsed by the real parser into the paths the demo data relies on."""

  import hashlib
  import io
  import json
  import re
  import zipfile

  from django.test import SimpleTestCase

  from ddp_parser import parse, walk
  from ddp_tracker.journeys.demo import ddps

  T = "/user_data_tiktok.json"
  BUILDERS = (ddps.tiktok, ddps.tiktok_march, ddps.instagram, ddps.facebook, ddps.youtube)
  LIKE_DATE = f"{T}/Likes and Favorites/Like List/ItemFavoriteList/[]/date"


  def paths(files, name="export.zip"):
      """The paths the parser makes of a package."""
      return {node.path for node in walk(parse(ddps.build_zip(files), name=name).root)}


  class BuildZipTests(SimpleTestCase):
      def test_a_package_is_the_same_on_every_run(self):
          for build in BUILDERS:
              with self.subTest(package=build.__name__):
                  first = hashlib.sha256(ddps.build_zip(build())).hexdigest()
                  self.assertEqual(hashlib.sha256(ddps.build_zip(build())).hexdigest(), first)

      def test_building_other_packages_in_between_changes_nothing(self):
          alone = ddps.build_zip(ddps.instagram())
          ddps.tiktok()
          ddps.facebook()
          self.assertEqual(ddps.build_zip(ddps.instagram()), alone)

      def test_members_are_written_by_their_kind(self):
          data = ddps.build_zip({"a.csv": "x,y\n1,2\n", "b.bin": b"\x00\x01", "c.json": {"k": 1}})
          with zipfile.ZipFile(io.BytesIO(data)) as archive:
              self.assertEqual(archive.read("a.csv"), b"x,y\n1,2\n")
              self.assertEqual(archive.read("b.bin"), b"\x00\x01")
              self.assertEqual(json.loads(archive.read("c.json")), {"k": 1})


  class PackageTests(SimpleTestCase):
      def test_tiktok_september(self):
          found = paths(ddps.tiktok())
          for path in (
              f"{T}/Your Activity/Watch History/VideoList/[]/Date",
              f"{T}/Your Activity/Searches/SearchList/[]/SearchTerm",
              LIKE_DATE,
              f"{T}/Direct Message/Direct Messages/ChatHistory/Chat History with {{*}}/[]/Content",
              f"{T}/Tiktok Live/Go Live History/GoLiveList",
          ):
              self.assertIn(path, found)
          self.assertNotIn(f"{T}/Activity", found)

      def test_tiktok_march_is_the_older_shape(self):
          files = ddps.tiktok_march()
          document = parse(ddps.build_zip(files), name="export.zip")
          formats = {node.path: getattr(node, "format", None) for node in walk(document.root)}
          self.assertIn(f"{T}/Activity/Video Browsing History/VideoList/[]/Date", formats)
          self.assertIn(f"{T}/Profile And Settings/Profile Info/ProfileMap/likesReceived", formats)
          self.assertNotIn(f"{T}/Your Activity", formats)
          self.assertFalse([path for path in formats if "Tiktok Live" in path])
          self.assertEqual(formats[LIKE_DATE], "%Y-%m-%dT%H:%M:%SZ")
          # its values are from before its own request date
          likes = files[ddps.TIKTOK_FILE]["Likes and Favorites"]["Like List"]["ItemFavoriteList"]
          self.assertLess(max(like["date"] for like in likes), "2026-03-16")

      def test_the_september_like_dates_have_no_time_zone_marker(self):
          document = parse(ddps.build_zip(ddps.tiktok()), name="export.zip")
          formats = {node.path: getattr(node, "format", None) for node in walk(document.root)}
          self.assertEqual(formats[LIKE_DATE], "%Y-%m-%d %H:%M:%S")

      def test_instagram(self):
          found = paths(ddps.instagram())
          for path in (
              "/your_instagram_activity/likes/liked_posts.json/[]/timestamp",
              "/your_instagram_activity/messages/inbox/{*}/message_1.json/messages/[]/content",
              "/connections/followers_and_following/following.json/relationships_following/[]/title",
              "/media/stories/{*}/{*}.jpg",
          ):
              self.assertIn(path, found)

      def test_facebook_loses_its_wrapper_folder(self):
          found = paths(ddps.facebook(), name="facebook-noorfictional-2026-09-15-AbCdEf12.zip")
          for path in (
              "/your_facebook_activity/comments_and_reactions/comments.json/comments_v2/[]/timestamp",
              "/logged_information/search/your_search_history.json/searches_v2/[]/data/[]/text",
              "/security_and_login_information/logins_and_logouts.json/{*}/[]/ip_address",
          ):
              self.assertIn(path, found)
          self.assertFalse([path for path in found if path.startswith("/facebook-")])

      def test_youtube(self):
          found = paths(ddps.youtube())
          root = "/Takeout/YouTube and YouTube Music"
          for path in (
              f"{root}/history/watch-history.json/[]/time",
              f"{root}/history/search-history.json/[]/title",
              f"{root}/subscriptions/subscriptions.csv/[]/Channel Title",
          ):
              self.assertIn(path, found)

      def test_every_e_mail_address_is_fictional(self):
          for build in BUILDERS:
              text = json.dumps(
                  {name: data for name, data in build().items() if not isinstance(data, bytes)}
              )
              for address in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
                  self.assertTrue(address.endswith("@example.org"), address)
  ```

- [ ] **Step 3: Run the tests and see them fail**

  ```bash
  DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest ddp_tracker/journeys/tests/test_demo_ddps.py -q -p no:sugar --no-cov
  ```

  Expected: an import error (`cannot import name 'ddps'`).

- [ ] **Step 4: Write `ddp_tracker/journeys/demo/ddps.py`**

  Start from `make_sample_ddps.py`. It builds three packages from one shared random generator, in a fixed order. Here each package needs its own generator, so that it is the same whatever was built before. The shape of the module:

  ```python
  """Fictional data download packages (DDPs) for the demo data (``manage.py seed_demo``), built
  in memory: no binary file and nothing that looks personal is kept in the repository.

  Everything in them is invented: the persona "Noor Vermeulen", her friends, messages, searches
  and IDs. E-mail addresses use example.org, IP addresses the ranges reserved for documentation
  (RFC 5737). The structure (folders, file names, keys, value formats) follows what real
  Facebook, Instagram, TikTok and YouTube exports looked like in 2026.
  """

  import io
  import json
  import random
  import uuid
  import zipfile
  from datetime import UTC, datetime, timedelta
  from typing import Any

  type Files = dict[str, Any]  # zip member name → bytes (as is), str (UTF-8 text), or JSON data

  SEED = 20260930
  SEPTEMBER = datetime(2026, 9, 15, 10, 30, tzinfo=UTC)
  MARCH = datetime(2026, 3, 15, 10, 30, tzinfo=UTC)
  TIKTOK_FILE = "user_data_tiktok.json"
  TIKTOK_DATE = "%Y-%m-%d %H:%M:%S"

  # PERSONA, FRIENDS, HANDLES, SEARCH_TERMS, TOPICS, ADVERTISERS, EMOJI_TEXT, UA: as in the generator
  CHANNELS = (
      "Fictional Cycling Channel",
      "Plant Care Daily",
      "Utrecht City Walks",
      "Made-up News NL",
      "Coffee Lab",
  )


  def meta_text(s: str) -> str: ...  # as in the generator
  def tiny_jpeg() -> bytes: ...  # as in the generator


  class _Builder:
      """One package's builder. Each has its own random generator with the same seed, so a
      package is the same on every run, whatever was built before it."""

      def __init__(self, request_date: datetime) -> None:
          self.rng = random.Random(SEED)  # noqa: S311 - fictional demo data, nothing secret
          self.request_date = request_date

      def ts_between(self, start: datetime, end: datetime) -> datetime: ...
      def recent(self, n: int, days: int = 365) -> list[datetime]: ...
      def fake_ip(self) -> str: ...
      def fbid(self) -> str: ...
      def tiktok(self) -> Files: ...
      def instagram(self) -> Files: ...
      def facebook(self) -> Files: ...
      def youtube(self) -> Files: ...


  def tiktok(request_date: datetime = SEPTEMBER) -> Files:
      return _Builder(request_date).tiktok()


  def instagram() -> Files:
      return _Builder(SEPTEMBER).instagram()


  def facebook() -> Files:
      return _Builder(SEPTEMBER).facebook()


  def youtube() -> Files:
      return _Builder(SEPTEMBER).youtube()
  ```

  Move the generator's code into it with these changes and no others:

  1. `ts_between`, `recent`, `fake_ip`, `fbid` become methods. Inside them and inside the three package methods: `rng.` becomes `self.rng.`, `REQUEST_DATE` becomes `self.request_date`, and calls to those four helpers get `self.`. The inner helper functions of the packages (`link`, `chat`, `sld`, `label_item`, `post_url`, `ts`) stay inner functions.
  2. The format string `fmt` in `tiktok` becomes the module constant `TIKTOK_DATE`; the key `"user_data_tiktok.json"` becomes `TIKTOK_FILE`.
  3. Drop what is not used: `main`, `write_zip`, `tiny_mp4`, the inner function `smd` in `instagram`, the imports `sys` and `Path`, and `REQUEST_DATE`.
  4. Replace `timezone.utc` by `UTC`.
  5. Keep every `zip(...)` as it behaves today: add `strict=False` to each.
  6. Do not change the order of the calls to the random generator inside a package: the structure that comes out was checked against the parser.

  Add the YouTube package as a method of `_Builder`:

  ```python
  def youtube(self) -> Files:
      """A small Google Takeout: watch and search history as JSON (the timestamps carry a
      Z), subscriptions as CSV."""
      stamp = "%Y-%m-%dT%H:%M:%S.000Z"
      root = "Takeout/YouTube and YouTube Music/"
      watched = [
          {
              "header": "YouTube",
              "title": f"Watched Fictional video {number}",
              "titleUrl": f"https://www.youtube.com/watch?v=fictional{number:03d}",
              "subtitles": [
                  {
                      "name": channel,
                      "url": f"https://www.youtube.com/channel/UCfictional{CHANNELS.index(channel):04d}",
                  }
              ],
              "time": moment.strftime(stamp),
              "products": ["YouTube"],
              "activityControls": ["YouTube watch history"],
          }
          for number, (moment, channel) in enumerate(
              zip(self.recent(40, 90), self.rng.choices(CHANNELS, k=40), strict=True)
          )
      ]
      searched = [
          {
              "header": "YouTube",
              "title": f"Searched for {term}",
              "titleUrl": "https://www.youtube.com/results?search_query=" + term.replace(" ", "+"),
              "time": moment.strftime(stamp),
              "products": ["YouTube"],
              "activityControls": ["YouTube search history"],
          }
          for moment, term in zip(self.recent(12), self.rng.choices(SEARCH_TERMS, k=12), strict=True)
      ]
      subscriptions = "Channel Id,Channel Url,Channel Title\n" + "".join(
          f"UCfictional{number:04d},http://www.youtube.com/channel/UCfictional{number:04d},{channel}\n"
          for number, channel in enumerate(CHANNELS)
      )
      return {
          f"{root}history/watch-history.json": watched,
          f"{root}history/search-history.json": searched,
          f"{root}subscriptions/subscriptions.csv": subscriptions,
      }
  ```

  Add the March TikTok package and the zip builder as module functions:

  ```python
  def tiktok_march() -> Files:
      """The TikTok package as it looked six months earlier, so that the September one has
      something to differ from: the section Your Activity is still called Activity and its
      watch history Video Browsing History, there is no live section, the like list's dates
      are ISO 8601 with a Z, and the profile has a field that was dropped since."""
      data = tiktok(MARCH)[TIKTOK_FILE]
      activity = data.pop("Your Activity")
      activity["Video Browsing History"] = activity.pop("Watch History")
      data["Activity"] = activity
      del data["Tiktok Live"]
      for like in data["Likes and Favorites"]["Like List"]["ItemFavoriteList"]:
          liked_at = datetime.strptime(like["date"], TIKTOK_DATE).replace(tzinfo=UTC)
          like["date"] = liked_at.strftime("%Y-%m-%dT%H:%M:%SZ")
      data["Profile And Settings"]["Profile Info"]["ProfileMap"]["likesReceived"] = "57"
      return {TIKTOK_FILE: data}


  def build_zip(files: Files) -> bytes:
      """The package as a zip. Members get a fixed timestamp, so the same files always give the
      same bytes."""
      buffer = io.BytesIO()
      with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
          for name, content in sorted(files.items()):
              info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
              info.compress_type = zipfile.ZIP_DEFLATED
              if not isinstance(content, (bytes, str)):
                  content = json.dumps(content, indent=2, ensure_ascii=True)  # noqa: PLW2901
              archive.writestr(info, content)
      return buffer.getvalue()
  ```

  (If ruff does not report `PLW2901` there, remove the `noqa`; if it does, give it a reason: `- the member's content, as text`. Or use a second variable.)

- [ ] **Step 5: Run the tests and see them pass**

  Same command as step 3. Expected: 10 passed.

- [ ] **Step 6: Lint**

  ```bash
  uv run ruff check ddp_tracker/journeys --fix && uv run ruff format ddp_tracker/journeys && uv run mypy .
  ```

  The generator was written as a script, so ruff will report things. Fix them in the code: annotate the inner functions; give the three probabilities names (`0.2`, `0.15`, `0.5`) or compare against named constants. Where a rule does not fit fictional data, a `# noqa: <code> - <reason>` on the line is fine. Do not add a per-file ignore to `pyproject.toml`. After fixing, run the tests again: they must still pass (you did not change the order of the random calls).

- [ ] **Step 7: Run the task gate and commit**

  ```bash
  git add ddp_tracker/journeys config/settings/base.py
  uv run pre-commit run
  git commit -m "feat(journeys): add the app and fictional DDPs for demo data"
  ```

**Acceptance:**

- The ten tests pass, and the rest of the suite is as at the baseline.
- `git status` shows no zip file and nothing outside the listed files.
- `uv run ruff check .`, `uv run mypy .` clean.

---

## Task 1.2: `seed_demo`

**Review:** full.

**Files:**

- Create (copy): `ddp_tracker/journeys/demo/spec.py` from `starter-files/ddp_tracker/journeys/demo/spec.py`
- Create (copy): `ddp_tracker/journeys/demo/seed.py` from `starter-files/ddp_tracker/journeys/demo/seed.py`
- Create: `ddp_tracker/journeys/management/__init__.py`, `ddp_tracker/journeys/management/commands/__init__.py` (both empty)
- Create: `ddp_tracker/journeys/management/commands/seed_demo.py`
- Create: `ddp_tracker/journeys/tests/utils.py`
- Create: `ddp_tracker/journeys/tests/test_seed_demo.py`

**Interfaces:**

- Consumes: `ddp_tracker.journeys.demo.ddps` (task 1.1); the functions in `01-design.md`, table 5.6.
- Produces:
  - `ddp_tracker.journeys.demo.seed.seed(password: str) -> Counter[str]`, `reset() -> Counter[str]`, `SeedError`
  - `ddp_tracker.journeys.demo.spec`: `ADMIN_EMAIL`, `CURATOR_EMAIL`, `DEMO_PASSWORD`, `PLATFORMS`, `UPLOADS`, `ANNOTATIONS`, `REPRESENTATIONS`, `EXAMPLES`, `SUGGESTION_PATH`
  - the command `seed_demo [--reset] [--force]`
  - `ddp_tracker.journeys.tests.utils.seed_demo(**options)` and `SeededTestCase` (a `TestCase` whose database holds the demo data), which every later test of a page with data uses

**About the two copied files.** They were run against the parser and an in-memory database while planning: first run creates 2 users, 4 platforms, 5 uploads, 28 annotations, 9 representations, 21 example values, 1 suggested term and 1 suggestion; a second run creates nothing; `reset` leaves nothing behind. Read them before you write the tests: `seed.py` shows how an upload goes through the real parse task and the plausibility checks. If a copied file fails here (the parser changed, a name moved), adapt the copy and report it as a deviation.

- [ ] **Step 1: Copy the two files and create the empty packages**

  ```bash
  P="/c/Users/hekma/Documents/Projects/DDP-Tracker-docs/implementation-plan/starter-files/ddp_tracker/journeys"
  cp "$P/demo/spec.py" "$P/demo/seed.py" ddp_tracker/journeys/demo/
  mkdir -p ddp_tracker/journeys/management/commands
  touch ddp_tracker/journeys/management/__init__.py ddp_tracker/journeys/management/commands/__init__.py
  ```

- [ ] **Step 2: Write the test helper**

  `ddp_tracker/journeys/tests/utils.py`:

  ```python
  """Shared by the journeys tests: a database with the demo data in it."""

  import io
  import tempfile
  from pathlib import Path

  from django.core.management import call_command
  from django.test import TestCase, override_settings


  def seed_demo(*, force=True, **options):
      """Run ``seed_demo`` as tests need it: DEBUG is off under test (hence ``force``), and the
      fictional packages wait in a temporary folder, where none may be left afterwards (an
      uploaded package is never kept). Returns what the command printed."""
      out = io.StringIO()
      with tempfile.TemporaryDirectory() as incoming, override_settings(DDP_INCOMING_DIR=incoming):
          call_command("seed_demo", force=force, stdout=out, **options)
          left = list(Path(incoming).iterdir())
      assert not left, f"seed_demo kept uploaded files: {left}"
      return out.getvalue()


  class SeededTestCase(TestCase):
      """A test case whose database holds the demo data (seeded once per class)."""

      @classmethod
      def setUpTestData(cls):
          seed_demo()
  ```

- [ ] **Step 3: Write the failing tests**

  `ddp_tracker/journeys/tests/test_seed_demo.py`:

  ```python
  """``manage.py seed_demo``: an empty database becomes a demo, through the site's own code."""

  from datetime import date

  from django.core.management import call_command
  from django.core.management.base import CommandError
  from django.test import TestCase, override_settings

  from allauth.account.models import EmailAddress

  from ddp_tracker.annotations.models import Annotation
  from ddp_tracker.core.tests.utils import parsed_upload
  from ddp_tracker.ddps.models import Platform, Upload
  from ddp_tracker.journeys.demo.spec import (
      ADMIN_EMAIL,
      ANNOTATIONS,
      CURATOR_EMAIL,
      DEMO_PASSWORD,
      EXAMPLES,
      REPRESENTATIONS,
      SUGGESTION_PATH,
  )
  from ddp_tracker.journeys.tests.utils import SeededTestCase, seed_demo
  from ddp_tracker.proposals.models import Proposal
  from ddp_tracker.proposals.templatetags.proposal_tags import proposals_waiting
  from ddp_tracker.representations.models import ActivityType, Representation
  from ddp_tracker.reviews.services import NEW, review, scopes
  from ddp_tracker.schemas.examples import USER_INPUT
  from ddp_tracker.schemas.models import Location, Observation
  from ddp_tracker.users.models import User

  T = "/user_data_tiktok.json"
  MODELS = (User, Platform, Upload, Location, Observation, Annotation, Representation, Proposal)


  def counts():
      return {model.__name__: model.objects.count() for model in MODELS}


  class DemoDataTests(SeededTestCase):
      """What the demo data is (seeded once for the class)."""

      def test_users(self):
          admin = User.objects.get(email=ADMIN_EMAIL)
          self.assertTrue(admin.is_staff and admin.is_superuser)
          self.assertFalse(User.objects.get(email=CURATOR_EMAIL).is_staff)
          # accounts sign in with a verified address
          self.assertEqual(EmailAddress.objects.filter(verified=True, primary=True).count(), 2)

      def test_platforms_and_uploads(self):
          self.assertEqual(
              set(Platform.objects.values_list("slug", flat=True)),
              {"facebook", "instagram", "tiktok", "youtube"},
          )
          registered = Upload.objects.filter(registered_at__isnull=False)
          self.assertEqual(
              sorted(registered.values_list("platform__slug", "requested_at")),
              [
                  ("facebook", date(2026, 9, 15)),
                  ("instagram", date(2026, 9, 15)),
                  ("tiktok", date(2026, 3, 15)),
                  ("tiktok", date(2026, 9, 15)),
              ],
          )
          # stored as any upload is: the name anonymised, the structure only
          self.assertTrue(all(upload.document for upload in registered))
          self.assertNotIn("noor", " ".join(registered.values_list("file_name", flat=True)))

      def test_one_upload_waits_for_approval(self):
          held = Upload.objects.get(platform__slug="youtube")
          self.assertEqual(held.plausibility, Upload.Plausibility.AWAITING)
          self.assertEqual(held.plausibility_reason, Upload.Reason.FIRST)
          self.assertIsNone(held.registered_at)
          self.assertEqual(held.uploaded_by, User.objects.get(email=CURATOR_EMAIL))

      def test_the_september_tiktok_upload_has_something_to_show(self):
          september = Upload.objects.get(platform__slug="tiktok", requested_at=date(2026, 9, 15))
          self.assertEqual(september.plausibility, Upload.Plausibility.PASSED)  # by itself
          new = set(
              Location.objects.filter(pk__in=scopes(september)[NEW]).values_list("path", flat=True)
          )
          self.assertIn(f"{T}/Tiktok Live/Go Live History/GoLiveList", new)
          watch = f"{T}/Your Activity/Watch History/VideoList/[]"
          self.assertIn(watch, new)
          # recognised as the older section's list, moved
          moved = september.observations.get(location__path=watch).suggestions[0]
          self.assertEqual(moved["path"], f"{T}/Activity/Video Browsing History/VideoList/[]")
          found = review(september)
          self.assertEqual(
              {item.observation.location.path: item.fields for item in found.changed},
              {f"{T}/Likes and Favorites/Like List/ItemFavoriteList/[]/date": ["format"]},
          )
          self.assertEqual(
              [item.location.path for item in found.missing],
              [f"{T}/Profile And Settings/Profile Info/ProfileMap/likesReceived"],
          )

      def test_annotations(self):
          self.assertEqual(Annotation.objects.count(), len(ANNOTATIONS))
          for spec in ANNOTATIONS:
              with self.subTest(annotation=f"{spec.platform}: {spec.name}"):
                  annotation = Annotation.objects.get(platform__slug=spec.platform, name=spec.name)
                  self.assertEqual(annotation.pii, spec.pii)
                  self.assertEqual(
                      set(annotation.locations.values_list("path", flat=True)), set(spec.paths)
                  )
          # one data point at two paths: the old section name and the new one
          watched = Annotation.objects.get(platform__slug="tiktok", name="Watched video")
          self.assertEqual(watched.locations.count(), 2)

      def test_representations(self):
          self.assertEqual(Representation.objects.count(), len(REPRESENTATIONS))
          watched = Representation.objects.get(
              location__platform__slug="tiktok", name="Watched a video"
          )
          self.assertEqual(watched.statement, "user · viewed · video")
          self.assertEqual(
              {
                  (link.relative_path, link.role.slug, link.subject)
                  for link in watched.metadata_links.all()
              },
              {("Date", "when", "activity"), ("Link", "identifier", "object")},
          )
          # public representations only use approved terms
          self.assertFalse(Representation.objects.filter(activity__approved=False).exists())

      def test_example_values_are_a_curators(self):
          for spec in EXAMPLES:
              location = Location.objects.get(platform__slug=spec.platform, path=spec.path)
              self.assertEqual(
                  location.example_values,
                  [{"value": value, "source": USER_INPUT} for value in spec.examples],
              )

      def test_the_queues_are_not_empty(self):
          self.assertEqual(proposals_waiting()["annotations"], 1)
          suggestion = Proposal.objects.get()
          self.assertEqual(
              suggestion.location, Location.objects.get(platform__slug="tiktok", path=SUGGESTION_PATH)
          )
          self.assertEqual(suggestion.proposed_by, User.objects.get(email=CURATOR_EMAIL))
          self.assertTrue(suggestion.is_open)
          liked = ActivityType.objects.get(slug="liked")
          self.assertFalse(liked.approved)  # waits for an administrator


  class SeedDemoCommandTests(TestCase):
      def test_refuses_to_run_without_debug(self):
          with self.assertRaisesMessage(CommandError, "DEBUG is off"):
              call_command("seed_demo")
          self.assertFalse(Platform.objects.exists())

      def test_says_what_it_created_and_how_to_log_in(self):
          output = seed_demo()  # the helper also checks that no package file is left behind
          self.assertIn("Created: 2 users, 4 platforms, 5 uploads, 28 annotations", output)
          self.assertIn(ADMIN_EMAIL, output)
          self.assertIn("Password", output)

      def test_running_it_again_creates_nothing(self):
          seed_demo()
          before = counts()
          output = seed_demo()
          self.assertEqual(counts(), before)
          self.assertIn("Created: nothing.", output)
          self.assertIn("exist already", output)

      def test_it_leaves_what_a_person_changed(self):
          seed_demo()
          annotation = Annotation.objects.get(platform__slug="tiktok", name="Search term")
          annotation.name = "Search text"
          annotation.save()
          before = counts()
          seed_demo()
          self.assertEqual(counts(), before)
          self.assertFalse(Annotation.objects.filter(platform__slug="tiktok", name="Search term"))

      def test_the_documented_password_needs_debug(self):
          seed_demo()  # DEBUG is off under test: a random password
          self.assertFalse(User.objects.get(email=ADMIN_EMAIL).check_password(DEMO_PASSWORD))

      @override_settings(DEBUG=True)
      def test_with_debug_the_password_is_the_documented_one(self):
          seed_demo(force=False)  # no need to force it: DEBUG is on
          for email in (ADMIN_EMAIL, CURATOR_EMAIL):
              self.assertTrue(User.objects.get(email=email).check_password(DEMO_PASSWORD))

      def test_reset_removes_the_demo_data(self):
          terms = ActivityType.objects.count()
          seed_demo()
          output = seed_demo(reset=True)
          self.assertEqual(set(counts().values()), {0})
          self.assertEqual(ActivityType.objects.count(), terms)  # the vocabulary is as before
          self.assertIn("Removed:", output)

      def test_reset_keeps_a_platform_that_others_uploaded_to(self):
          seed_demo()
          tiktok = Platform.objects.get(slug="tiktok")
          someone = User.objects.create_user("someone@example.org")
          theirs = parsed_upload(tiktok, {"a.json": b'{"x": 1}'}, register=True, user=someone)
          seed_demo(reset=True)
          self.assertEqual(list(Upload.objects.all()), [theirs])
          self.assertEqual(list(Platform.objects.values_list("slug", flat=True)), ["tiktok"])
          self.assertFalse(Annotation.objects.exists())
  ```

- [ ] **Step 4: Run the tests and see them fail**

  ```bash
  DJANGO_SETTINGS_MODULE=config.settings.cicd uv run pytest ddp_tracker/journeys/tests/test_seed_demo.py -q -p no:sugar --no-cov
  ```

  Expected: every test fails with `Unknown command: 'seed_demo'`.

- [ ] **Step 5: Write the command**

  `ddp_tracker/journeys/management/commands/seed_demo.py`:

  ```python
  import secrets
  from collections import Counter
  from typing import Any

  from django.conf import settings
  from django.core.management.base import BaseCommand, CommandError, CommandParser

  from ddp_tracker.journeys.demo.seed import SeedError, reset, seed
  from ddp_tracker.journeys.demo.spec import ADMIN_EMAIL, CURATOR_EMAIL, DEMO_PASSWORD


  class Command(BaseCommand):
      """Fictional demo data for a local DDP Tracker (``journeys/demo``): two users, four
      platforms, five uploads, annotations, representations, and a few open items for the
      queues. It only adds what is missing, so it is safe to run again::

          uv run manage.py seed_demo            # create what is missing
          uv run manage.py seed_demo --reset    # remove what it created

      For local demos: it refuses to run when DEBUG is off, unless forced, and then the demo
      users get a random password instead of the documented one.
      """

      help = "Create fictional demo data (platforms, uploads, annotations, representations)."

      def add_arguments(self, parser: CommandParser) -> None:
          parser.add_argument(
              "--reset", action="store_true", help="Remove the demo data instead of creating it."
          )
          parser.add_argument("--force", action="store_true", help="Run although DEBUG is off.")

      def handle(self, *args: Any, **options: Any) -> None:
          if not settings.DEBUG and not options["force"]:
              msg = "seed_demo is for local demos and DEBUG is off. Use --force if you are sure."
              raise CommandError(msg)
          if options["reset"]:
              self._report("Removed", reset())
              return
          password = DEMO_PASSWORD if settings.DEBUG else secrets.token_urlsafe(12)
          try:
              created = seed(password)
          except SeedError as error:
              raise CommandError(str(error)) from error
          self._report("Created", created)
          users = f"{ADMIN_EMAIL} (staff) or {CURATOR_EMAIL} (not staff)"
          if created["users"]:
              self.stdout.write(f"Log in as {users}. Password for both: {password}")
          else:
              self.stdout.write(
                  f"The demo users exist already: {users}. Their passwords are unchanged."
              )

      def _report(self, verb: str, counts: Counter[str]) -> None:
          found = [f"{count} {kind}" for kind, count in counts.items() if count]
          self.stdout.write(f"{verb}: {', '.join(found)}." if found else f"{verb}: nothing.")
  ```

- [ ] **Step 6: Run the tests and see them pass**

  Same command as step 4. Expected: all pass. If a path of `spec.py` does not exist, the command stops with a message that names it: check the path against the parser's output for the package (the helper `paths()` in `test_demo_ddps.py` lists them) and correct `spec.py`.

- [ ] **Step 7: Try it for real**

  ```bash
  rm -f demo.sqlite3
  DATABASE_URL=sqlite:///demo.sqlite3 USE_DOCKER=no uv run manage.py migrate -v 0
  DATABASE_URL=sqlite:///demo.sqlite3 USE_DOCKER=no uv run manage.py seed_demo
  DATABASE_URL=sqlite:///demo.sqlite3 USE_DOCKER=no uv run manage.py seed_demo
  ```

  Expected: the first run prints "Created: 2 users, 4 platforms, 5 uploads, 28 annotations, 9 representations, 21 example values, 1 suggested terms, 1 suggestions." and the login line with the documented password (the local settings have DEBUG on); the second prints "Created: nothing." Leave `demo.sqlite3` in place for the coordinator.

- [ ] **Step 8: Run the task gate and commit**

  ```bash
  git add ddp_tracker/journeys
  uv run pre-commit run
  git commit -m "feat(journeys): add seed_demo, fictional demo data through the real code paths"
  ```

**Acceptance:**

- All tests of `test_seed_demo.py` pass; the suite is otherwise as at the baseline; coverage is not lower than 95%.
- Step 7 gives the two outputs above.
- No e-mail address other than the two demo addresses appears in the command's output.
- `var/incoming/` holds no file after seeding (`ls var/incoming` is empty or the folder does not exist).

**For the coordinator after this task:** start the site on `demo.sqlite3`, log in at `/accounts/login/` as the demo admin, and look at `/platforms/tiktok/`, `/uploads/approvals/` (one YouTube upload waits) and `/proposals/annotations/` (one suggestion). This is the data every later page builds on.
