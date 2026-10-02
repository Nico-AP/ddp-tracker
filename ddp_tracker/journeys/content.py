"""The eight user journeys: who comes to the DDP Tracker, what they want, and the steps that get
them there. Each step leads to a page that exists today or to a mock-up of a planned feature
(``mockups``). Kept as data, so that one template renders every journey and tests can check
every link.

A journey answers the hackathon's core questions: an aim, how to reach it (the steps), what the
interface looks like (each step's page) and which features it needs (with their status today).
"""

from dataclasses import dataclass

from django.urls import reverse

# a step's status: its page exists today, or it is a mock-up
AVAILABLE, PROTOTYPE = "available", "prototype"
STATUSES = (AVAILABLE, PROTOTYPE)

# who can use a step's page today
ANYONE, ACCOUNT, STAFF = "anyone", "account", "staff"
NEEDS = {ANYONE: "", ACCOUNT: "Needs an account", STAFF: "Staff only today"}

# a feature's status (as in the features analysis)
EXISTS, PARTIAL, GAP = "exists", "partial", "gap"
FEATURE_STATUSES = {EXISTS: "Exists", PARTIAL: "Partial", GAP: "Gap"}


def _url(name: str, args: tuple[str, ...], query: str = "", fragment: str = "") -> str:
    url = reverse(name, args=args)
    if query:
        url += f"?{query}"
    if fragment:
        url += f"#{fragment}"
    return url


@dataclass(frozen=True)
class Step:
    title: str
    text: str
    link_label: str
    url_name: str
    url_args: tuple[str, ...] = ()
    query: str = ""
    fragment: str = ""
    status: str = AVAILABLE
    needs: str = ANYONE
    missing: str = ""  # what the page cannot do yet
    # for a prototype step: the closest page that exists today
    today_label: str = ""
    today_url_name: str = ""
    today_url_args: tuple[str, ...] = ()
    demo_link: str = ""  # a link into the seeded demo data (targets.DEMO_LINK_KEYS)

    @property
    def url(self) -> str:
        return _url(self.url_name, self.url_args, self.query, self.fragment)

    @property
    def today_url(self) -> str:
        return _url(self.today_url_name, self.today_url_args) if self.today_url_name else ""

    @property
    def needs_label(self) -> str:
        return NEEDS[self.needs]


@dataclass(frozen=True)
class Feature:
    title: str
    status: str
    hackathon: bool = False  # first raised in the hackathon document
    note: str = ""

    @property
    def status_label(self) -> str:
        return FEATURE_STATUSES[self.status]


@dataclass(frozen=True)
class Role:
    slug: str
    name: str
    card_line: str  # completes "I want to …" on the landing page
    aim: str
    audience: str
    steps: tuple[Step, ...]
    features: tuple[Feature, ...]

    @property
    def available_count(self) -> int:
        return sum(step.status == AVAILABLE for step in self.steps)

    @property
    def prototype_count(self) -> int:
        return sum(step.status == PROTOTYPE for step in self.steps)


RESEARCHER = Role(
    slug="researcher",
    name="Substantive researcher",
    card_line="find which platform data can answer my research question",
    aim=(
        "Find which platform data can answer my research question, understand what it means, "
        "and hand a precise list to the person who builds the extraction."
    ),
    audience=(
        "Social scientists who design a data donation study. You should not have to read a "
        "file tree to find your variables."
    ),
    steps=(
        Step(
            title="Pick your research field and theme",
            text=(
                "Choose your field, for example communication science, and a theme such as "
                "News and politics. The concept view then shows what matters for that theme, "
                "in your field's own words."
            ),
            link_label="Open the concept view for News and politics",
            url_name="journeys:concepts",
            query="field=communication&theme=news-politics",
            status=PROTOTYPE,
            missing=(
                "Today there is one shared vocabulary. Labels per research field do not exist."
            ),
        ),
        Step(
            title="Browse concepts across platforms",
            text=(
                "See concepts such as Watched a video or Searched, sorted by how often studies "
                "use them, with the platforms that provide each one."
            ),
            link_label="Browse all concepts by relevance",
            url_name="journeys:concepts",
            query="sort=relevance",
            status=PROTOTYPE,
            missing="Today you can only search within one platform, by name or path.",
            today_label="Today: representations across platforms",
            today_url_name="representations:representations",
        ),
        Step(
            title="Understand a concept",
            text=(
                "Read what a concept means, where it appears on each platform, since when, "
                "whose time its timestamps show, and what example values look like."
            ),
            link_label="Read about Watched a video",
            url_name="journeys:concept",
            url_args=("watched-video",),
            status=PROTOTYPE,
            missing=(
                "Today the meaning is on the annotation page, per platform. Whose time zone "
                "a timestamp shows is not recorded."
            ),
            today_label="Today: TikTok's annotations",
            today_url_name="annotations:annotations",
            today_url_args=("tiktok",),
            demo_link="watched-video",
        ),
        Step(
            title="Build a study shortlist",
            text=(
                "Add the concepts your study needs, each with a note on why. The shortlist "
                "also tells you how many of them hold personal data, for your ethics "
                "application."
            ),
            link_label="Open the study shortlist",
            url_name="journeys:shortlist",
            status=PROTOTYPE,
            missing="There is no shortlist today.",
        ),
        Step(
            title="Hand over to your engineer",
            text=(
                "Copy a link to the shortlist for the person who builds the extraction, or "
                "download it as a codebook."
            ),
            link_label="Share the shortlist or download the codebook",
            url_name="journeys:shortlist",
            query="c=watched-video&c=searched&c=liked-content",
            fragment="share",
            status=PROTOTYPE,
            missing="There is no export of any kind today.",
        ),
    ),
    features=(
        Feature("Browse annotated variables per platform, in plain language", EXISTS),
        Feature(
            "Compare the same concept across platforms",
            PARTIAL,
            note="Representations exist; a side-by-side view does not.",
        ),
        Feature("Labels per research field (field-specific ontology)", GAP, hackathon=True),
        Feature("Sort by relevance or use", GAP, hackathon=True),
        Feature(
            "Whose time zone a timestamp shows",
            PARTIAL,
            hackathon=True,
            note="The parser records a time zone marker; whose time it is, is not recorded.",
        ),
        Feature(
            "Example values as a table of title and value",
            PARTIAL,
            hackathon=True,
            note="Examples exist as a flat list per data point.",
        ),
        Feature("Study shortlist, shareable with an engineer", GAP),
        Feature("Codebook export", GAP),
    ),
)

ENGINEER = Role(
    slug="engineer",
    name="Research engineer",
    card_line="know exactly where each variable is and how to extract it",
    aim=(
        "Know exactly where each variable is, in which format and variants, and get "
        "machine-readable specifications to build extraction code from."
    ),
    audience=(
        "People who build parsers, extraction scripts and donation pipelines, for example in "
        "the Data Donation Module or Port."
    ),
    steps=(
        Step(
            title="Open the researcher's shortlist",
            text=(
                "Start from the concepts the researcher chose: each one comes with its exact "
                "paths on every platform."
            ),
            link_label="Open a shared shortlist",
            url_name="journeys:shortlist",
            query="c=watched-video&c=searched&c=liked-content",
            status=PROTOTYPE,
            missing="Today researchers and engineers exchange lists by hand.",
        ),
        Step(
            title="Inspect exact paths, types and formats",
            text=(
                "Use the full tree, the side panel's profile and the JSON outline to see every "
                "path with its type, shape and format."
            ),
            link_label="Open TikTok's full structure",
            url_name="schemas:platform",
            url_args=("tiktok",),
        ),
        Step(
            title="Check variants and history",
            text=(
                "Filter by request date, language and format. This link shows TikTok as it "
                "was requested before July 2026: the watch history still sits under its "
                "older section name."
            ),
            link_label="See TikTok as requested before July 2026",
            url_name="schemas:platform",
            url_args=("tiktok",),
            query="requested_to=2026-06-30",
        ),
        Step(
            title="See what changed recently",
            text=(
                "Read what the platform added, moved, changed and removed between requests, "
                "without opening each upload's review."
            ),
            link_label="Read TikTok's changelog",
            url_name="journeys:changes",
            url_args=("tiktok",),
            status=PROTOTYPE,
            missing="Today changes are shown per upload, to its uploader and staff only.",
            demo_link="tiktok-review",
        ),
        Step(
            title="Download specifications",
            text=(
                "Get a JSON Schema, a CSV codebook or a File Blueprint for the Data Donation "
                "Module, from the shortlist or through the API."
            ),
            link_label="See the planned exports",
            url_name="journeys:api",
            fragment="exports",
            status=PROTOTYPE,
            missing="There is no export and no API today.",
        ),
    ),
    features=(
        Feature("Full data point tree with types, shapes, formats and lengths", EXISTS),
        Feature("Variants by request format, language and request date", EXISTS),
        Feature(
            "Explain what a {*} segment stands for",
            PARTIAL,
            hackathon=True,
            note="The parser collapses such segments; the explorer does not say what to expect.",
        ),
        Feature(
            "Platform-level changelog",
            PARTIAL,
            note="New, changed and missing exist per upload review.",
        ),
        Feature("Recognise values that mean no data", GAP, hackathon=True),
        Feature("Paired donation sets", GAP, hackathon=True),
        Feature("Machine-readable schema export (JSON Schema, CSV codebook)", GAP),
        Feature("Extraction specification for donation tools (DDM File Blueprints)", GAP),
        Feature("Read-only API", GAP, hackathon=True),
    ),
)

POLICY = Role(
    slug="policy",
    name="Policy stakeholder",
    card_line="see what platforms disclose and how that changes",
    aim="See what platforms disclose, compare them, follow changes, and cite a fixed state.",
    audience="Regulators, data protection bodies, NGOs and journalists. No account needed.",
    steps=(
        Step(
            title="Choose platforms",
            text="Pick the platforms to look at. Each shows how much has been collected so far.",
            link_label="See all platforms",
            url_name="schemas:platforms",
        ),
        Step(
            title="Compare what they disclose",
            text=(
                "Read a matrix of concepts by platforms, and a summary per platform: how "
                "people can request their data, in which formats, and how well it is "
                "documented."
            ),
            link_label="Compare the platforms side by side",
            url_name="journeys:compare",
            status=PROTOTYPE,
            missing="Today there is no side-by-side comparison.",
            today_label="Today: representations across platforms",
            today_url_name="representations:representations",
        ),
        Step(
            title="Follow changes over time",
            text="See what a platform added, changed or removed from one request to the next.",
            link_label="Follow TikTok's changes",
            url_name="journeys:changes",
            url_args=("tiktok",),
            status=PROTOTYPE,
            missing="The data is there; there is no public view of it.",
        ),
        Step(
            title="Cite a snapshot",
            text="Pick a dated release of the knowledge base and copy its citation.",
            link_label="Pick a snapshot to cite",
            url_name="journeys:snapshots",
            status=PROTOTYPE,
            missing="The tracker changes all the time; nothing fixes a state today.",
        ),
    ),
    features=(
        Feature("Public overview of what each platform discloses, without an account", EXISTS),
        Feature(
            "Platform-level timeline of what was added, changed or removed",
            PARTIAL,
            note="The observations exist; a view of them does not.",
        ),
        Feature(
            "Gaps between platform documentation and actual DDPs",
            GAP,
            hackathon=True,
        ),
        Feature("Comparison of platforms on disclosure", GAP),
        Feature("Citable snapshots (referencable archive)", GAP, hackathon=True),
    ),
)

CONTRIBUTOR = Role(
    slug="contributor",
    name="Contributor",
    card_line="donate the structure of my own data download safely",
    aim="Donate the structure of my own data download safely, and see what it added.",
    audience=(
        "Anyone who requests their data from a platform, including study participants. "
        "Uploading needs an account."
    ),
    steps=(
        Step(
            title="Request your data from the platform",
            text=(
                "Follow the steps for your platform to request a data download package, and "
                "choose JSON where the platform offers it."
            ),
            link_label="See how to request your TikTok data",
            url_name="journeys:request",
            url_args=("tiktok",),
            status=PROTOTYPE,
            missing="Today the upload guide gives general advice only.",
            today_label="Today: the upload guide",
            today_url_name="docs",
            today_url_args=("guide/uploading/",),
        ),
        Step(
            title="Read what happens to your data",
            text=(
                "Your file is parsed and deleted right away. Only its structure is kept, and "
                "names that could identify you are masked."
            ),
            link_label="Read the privacy guide",
            url_name="docs",
            url_args=("guide/privacy/",),
        ),
        Step(
            title="Upload your DDP",
            text=(
                "Fill in the platform, when and how you requested the package, and choose the file."
            ),
            link_label="Go to the upload form",
            url_name="ddps:upload-create",
            needs=ACCOUNT,
            missing="The ways of requesting a package are a fixed list, without Other.",
        ),
        Step(
            title="Check it before it counts",
            text=(
                "An upload that is the first of its kind, or unlike the others, is held. Open "
                "it from your uploads and choose Inspect to see what is known, matched, new "
                "and missing."
            ),
            link_label="Go to my uploads to inspect one",
            url_name="ddps:uploads",
            needs=ACCOUNT,
            demo_link="held-upload",
        ),
        Step(
            title="See what your upload added",
            text=(
                "Once it counts, the review shows what is new, known, changed and missing "
                "compared with earlier requests."
            ),
            link_label="Go to my uploads to open a review",
            url_name="ddps:uploads",
            needs=ACCOUNT,
            missing="An upload with the earliest request date shows everything as new.",
            demo_link="tiktok-review",
        ),
    ),
    features=(
        Feature("Upload with privacy by design (parse, then delete)", EXISTS),
        Feature("Inspect a held upload before it counts", EXISTS),
        Feature("Review of one's own upload", PARTIAL, hackathon=True),
        Feature("Platform-specific instructions for requesting a DDP", GAP),
        Feature(
            "Other ways of obtaining a DDP",
            PARTIAL,
            hackathon=True,
            note="Only app, browser and Portability API can be chosen.",
        ),
        Feature("Notification when an upload is approved or rejected", GAP),
        Feature("Recognition of contributions", GAP, hackathon=True),
    ),
)

CURATOR = Role(
    slug="curator",
    name="Curator or moderator",
    card_line="describe what data points mean and keep a platform up to date",
    aim=(
        "Keep a platform's knowledge up to date: describe new data points, decide on "
        "suggestions, and seed descriptions from sources that exist already."
    ),
    audience=(
        "Experts who annotate data points and describe representations for one or more "
        "platforms. Signed-in users suggest; staff decide."
    ),
    steps=(
        Step(
            title="Open your platforms dashboard",
            text=(
                "See, for the platforms you moderate, what waits for you: data points to "
                "triage, suggestions, uploads to approve, and what to annotate next."
            ),
            link_label="Open the moderator dashboard",
            url_name="journeys:moderate",
            status=PROTOTYPE,
            missing="Today there is one global staff role, not tied to platforms.",
        ),
        Step(
            title="Triage new data points",
            text=(
                "Link a data point to an annotation, create one, or mark it as not a data "
                "point. This link shows TikTok's data points without an annotation."
            ),
            link_label="Triage TikTok's open data points",
            url_name="schemas:platform",
            url_args=("tiktok",),
            query="show=annotations",
            needs=ACCOUNT,
        ),
        Step(
            title="Describe representations",
            text=(
                "Say what a list's items mean in the shared vocabulary, for example user "
                "viewed video, and which data points describe them."
            ),
            link_label="See TikTok's representations",
            url_name="representations:platform",
            url_args=("tiktok",),
        ),
        Step(
            title="Decide on suggestions",
            text="Accept or reject what other people suggested, with a reason.",
            link_label="Open the suggestion queue",
            url_name="proposals:annotations",
            needs=STAFF,
            missing="A suggestion cannot be edited in place, only replaced.",
        ),
        Step(
            title="Seed annotations from existing sources",
            text=(
                "Start from the platform's own documentation, from paired uploads, or from "
                "labels suggested by AI, and check them instead of writing everything by "
                "hand."
            ),
            link_label="Seed annotations from these sources",
            url_name="journeys:seed",
            status=PROTOTYPE,
            missing="Every annotation is written by hand today.",
        ),
    ),
    features=(
        Feature("Triage, annotate and describe representations", EXISTS),
        Feature("Suggestion queues and approvals", EXISTS, note="Staff only."),
        Feature("Edit one's own open suggestion", PARTIAL, hackathon=True),
        Feature("Moderator role for one or more platforms (DDP hubs)", GAP, hackathon=True),
        Feature(
            "Seed annotations from official platform documentation, as its own kind",
            GAP,
            hackathon=True,
        ),
        Feature("Seed from paired uploads and from AI suggestions", GAP, hackathon=True),
        Feature("Prioritise which annotations matter most", GAP, hackathon=True),
        Feature("Translations of field names", GAP, hackathon=True),
    ),
)

ADMIN = Role(
    slug="admin",
    name="Instance administrator",
    card_line="set up and run a DDP Tracker",
    aim="Set up and run a tracker: platforms, path rules, roles, retention and health.",
    audience="People who run and maintain a DDP Tracker. Staff with access to the admin.",
    steps=(
        Step(
            title="Add platforms and path rules",
            text=(
                "Add a platform, and tell the parser which keys to rename or keep so that "
                "no personal name ends up in a path."
            ),
            link_label="Manage platforms and path rules",
            url_name="journeys:roles",
            fragment="platforms",
            status=PROTOTYPE,
            missing="Today this is in the Django admin only.",
            today_label="Today: the Django admin",
            today_url_name="admin:index",
        ),
        Step(
            title="Assign roles and moderators",
            text="Give people a role, and make someone the moderator of one or more platforms.",
            link_label="Manage roles and moderators",
            url_name="journeys:roles",
            fragment="roles",
            status=PROTOTYPE,
            missing="Today a user is staff or not; there is nothing in between.",
        ),
        Step(
            title="Approve new vocabulary terms",
            text=(
                "Curators suggest new terms for the shared vocabulary. Staff see how many "
                "wait on the vocabulary page and approve them in the admin."
            ),
            link_label="Open the vocabulary",
            url_name="representations:vocabulary",
            needs=STAFF,
        ),
        Step(
            title="Check health and retention",
            text=(
                "The health check tells a monitor that the site answers. The uploaders' own "
                "values are deleted by a command that has to run every day."
            ),
            link_label="Open the health check",
            url_name="core:health",
            missing="The daily deletion is a command; nothing schedules it.",
        ),
    ),
    features=(
        Feature("Add platforms and path rules", PARTIAL, note="Django admin only."),
        Feature("Manage roles beyond staff", GAP),
        Feature("Vocabulary governance in the app", PARTIAL, note="Approval is in the admin."),
        Feature("Scheduled deletion of expired uploader values", PARTIAL),
        Feature("Health check", EXISTS),
        Feature("Several hubs sharing one knowledge base", GAP, hackathon=True),
    ),
)

MACHINE = Role(
    slug="machine",
    name="Machine consumer",
    card_line="read schemas and annotations in a stable format",
    aim="Read schemas and annotations in a stable, documented format.",
    audience="Scripts, other tools such as the Data Donation Module or Port, and LLM agents.",
    steps=(
        Step(
            title="Read the API overview",
            text="See which endpoints exist, in which formats, with examples.",
            link_label="Read the API overview",
            url_name="journeys:api",
            status=PROTOTYPE,
            missing="There is no API today.",
        ),
        Step(
            title="Fetch a platform's schema",
            text="Request every data point of a platform with its type, format and meaning.",
            link_label="See the schema endpoint",
            url_name="journeys:api",
            fragment="schema",
            status=PROTOTYPE,
        ),
        Step(
            title="Pin a snapshot",
            text="Use a dated release, so that a script gives the same result next year.",
            link_label="See how to pin a snapshot",
            url_name="journeys:snapshots",
            fragment="pin",
            status=PROTOTYPE,
        ),
        Step(
            title="Connect an LLM",
            text="Point a language model at an llms.txt file, or at an MCP server over the API.",
            link_label="See the access for LLMs",
            url_name="journeys:api",
            fragment="llm",
            status=PROTOTYPE,
        ),
    ),
    features=(
        Feature(
            "Read-only API for platforms, data points, annotations and vocabulary",
            GAP,
            hackathon=True,
        ),
        Feature("Standard export formats", GAP),
        Feature(
            "Stable identifiers and versions",
            PARTIAL,
            note="Identifiers exist; versioned releases do not.",
        ),
        Feature("Access for LLMs (llms.txt, MCP)", GAP, hackathon=True),
        Feature("Explainers for participants through the API", GAP, hackathon=True),
        Feature("A licence for the curated knowledge", GAP),
    ),
)

LEARNER = Role(
    slug="learner",
    name="Learner",
    card_line="understand what a platform keeps about me",
    aim=(
        "Understand what a platform keeps about me, in plain language, and learn to read a "
        "data download package."
    ),
    audience="Study participants, students, teachers and anyone curious. No account needed.",
    steps=(
        Step(
            title="Pick a platform you use",
            text="Choose a platform from the list.",
            link_label="Choose a platform",
            url_name="schemas:platforms",
        ),
        Step(
            title="See what it keeps about you",
            text=(
                "Read, in plain language, which kinds of information are in the package: "
                "what you did, your messages, ads, devices and your profile."
            ),
            link_label="See what TikTok keeps about you",
            url_name="journeys:learn",
            url_args=("tiktok",),
            status=PROTOTYPE,
            missing="Today there is the full tree and a user guide, but no summary.",
        ),
        Step(
            title="Look at one data point closely",
            text=(
                "Open the watch history in the explorer: select a row to read what it means, "
                "with examples."
            ),
            link_label="Open TikTok's watch history in the explorer",
            url_name="schemas:platform",
            url_args=("tiktok",),
            query="q=Watch+History",
            demo_link="watched-video",
        ),
        Step(
            title="Try a guided exercise",
            text="Answer three questions about a data download package, and check your answers.",
            link_label="Try the exercise",
            url_name="journeys:learn",
            url_args=("tiktok",),
            fragment="exercise",
            status=PROTOTYPE,
        ),
    ),
    features=(
        Feature("Public exploring and a plain user guide", EXISTS),
        Feature("Plain summary per platform of what it keeps about you", GAP),
        Feature("Guided exercises for teaching", GAP, hackathon=True),
    ),
)

ROLES: tuple[Role, ...] = (
    RESEARCHER,
    ENGINEER,
    POLICY,
    CONTRIBUTOR,
    CURATOR,
    ADMIN,
    MACHINE,
    LEARNER,
)
ROLES_BY_SLUG = {role.slug: role for role in ROLES}
