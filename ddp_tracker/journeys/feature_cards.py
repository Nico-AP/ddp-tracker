"""Planned features as feature cards, in the template of the hackathon document (title, problem,
description of solution, user group, technical implementation). Each card links to the mock-up
that shows what the feature could look like. The texts come from the features analysis
(section 7); the first two cards are in the hackathon document itself.
"""

from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class FeatureCard:
    slug: str
    title: str
    problem: str
    solution: str
    user_group: str
    technical: str
    see_label: str  # where the prototype shows it
    see_url_name: str
    see_url_args: tuple[str, ...] = ()
    see_query: str = ""
    from_hackathon_document: bool = False  # the card itself is in the hackathon document

    @property
    def see_url(self) -> str:
        url = reverse(self.see_url_name, args=self.see_url_args)
        return f"{url}?{self.see_query}" if self.see_query else url


CARDS: tuple[FeatureCard, ...] = (
    FeatureCard(
        slug="time-zone",
        title="Timestamps need to say what time is captured",
        problem=(
            "Platforms provide timestamps with or without time zone information, and it is "
            "not always clear whose time a timestamp shows: the user's, the server's or "
            "another."
        ),
        solution=(
            "A time zone attribute on date data points, labelled by curators, next to what "
            "the parser already detects."
        ),
        user_group="Substantive researchers, research engineers",
        technical=(
            "The parser already records each date format, including whether it carries Z or "
            "an offset. Add a tz_whos field on the annotation (UTC, the user's local time, "
            "server time, a zone the platform defines, unknown), changed through the normal "
            "suggestion workflow, and show it next to the detected format. TikTok looks like "
            "UTC."
        ),
        see_label="Concept detail: Whose time?",
        see_url_name="journeys:concept",
        see_url_args=("watched-video",),
        from_hackathon_document=True,
    ),
    FeatureCard(
        slug="paired-donation-sets",
        title="Paired donation sets",
        problem=(
            "Annotating each format, language or download route of the same file separately "
            "is slow and can be inconsistent."
        ),
        solution=(
            "Link uploads that differ in one aspect only, so that their schemas can be "
            "aligned and annotations carried across."
        ),
        user_group="All",
        technical=(
            "An optional pairing between uploads, with a field for what differs (language, "
            "format, request mode). The uploaders' values are deleted after a few days and "
            "never public, so alignment uses what is kept: list lengths, types, shapes and "
            "positions in the tree. JSON and CSV pairs can start now; HTML pairs need HTML "
            "parsing first."
        ),
        see_label="Seed annotations: Paired uploads",
        see_url_name="journeys:seed",
        see_query="source=pairs",
        from_hackathon_document=True,
    ),
    FeatureCard(
        slug="field-ontology",
        title="Field-specific labels for variables",
        problem=(
            "Researchers in different fields look for the same data under different "
            "concepts, and one shared vocabulary cannot serve them all."
        ),
        solution=(
            "Research areas keep their own label sets, which map onto annotations and the "
            "shared vocabulary."
        ),
        user_group="Substantive researchers, learners",
        technical=(
            "New models for an ontology per field and its labels, with a many-to-many link "
            "to annotations. The concept view filters and groups by ontology. Labels are "
            "suggested and approved through the existing proposal workflow."
        ),
        see_label="Concept view: research field and theme",
        see_url_name="journeys:concepts",
        see_query="field=health",
    ),
    FeatureCard(
        slug="relevance",
        title="Sort data points by relevance or use",
        problem=(
            "Alphabetical trees hide the variables that matter most, and curators do not "
            "know where to start."
        ),
        solution=(
            "Sort by how often a data point is present across uploads and by how often "
            "researchers select it."
        ),
        user_group="Substantive researchers, curators",
        technical=(
            "Presence across uploads can be computed from the observations that exist. "
            "Selection counts need the study shortlist. Add a sort option to the explorer "
            "and the annotation lists."
        ),
        see_label="Concept view: sorted by relevance; dashboard: Annotate next",
        see_url_name="journeys:concepts",
        see_query="sort=relevance",
    ),
    FeatureCard(
        slug="examples-table",
        title="Show example values as a table with title and value",
        problem=(
            "A flat list of example values makes it hard to see which value belongs to which field."
        ),
        solution=(
            "For objects and list items, show examples as rows of sibling fields, and allow "
            "labelling individual values."
        ),
        user_group="Substantive researchers, research engineers",
        technical=(
            "Examples are stored per data point today. Group the examples of sibling data "
            "points under their parent list item and show them as one table. Labels on "
            "single values need a small addition to the example structure."
        ),
        see_label="Concept detail: Examples",
        see_url_name="journeys:concept",
        see_url_args=("watched-video",),
    ),
    FeatureCard(
        slug="official-documentation",
        title="Seed annotations from platform documentation",
        problem=(
            "Annotating every data point by hand is labour-intensive, and platforms often "
            "document their packages already."
        ),
        solution=(
            "Import official documentation as a separate kind of annotation, and flag where "
            "it disagrees with the packages people upload."
        ),
        user_group="Curators, substantive researchers, policy stakeholders",
        technical=(
            "A source field on annotations (curator or official), with a link to the source "
            "document and the date it was retrieved. Show both where they exist. Comparing "
            "them with the observations gives a report: documented but never observed, and "
            "observed but undocumented."
        ),
        see_label="Seed annotations: Official documentation",
        see_url_name="journeys:seed",
        see_query="source=docs",
    ),
    FeatureCard(
        slug="no-data-markers",
        title="Recognise values that mean no data",
        problem=(
            "Platforms fill empty fields with phrases such as No data available, which "
            "parsers mistake for real values."
        ),
        solution="Keep a list of such markers per platform and flag data points where they occur.",
        user_group="Research engineers",
        technical=(
            "A curated list per platform and language, applied by the parser when it works "
            "out shapes, so that marker values count as empty. Show a flag in the profile "
            "and include the list in exports."
        ),
        see_label="Concept detail: No data markers (Wrote a comment)",
        see_url_name="journeys:concept",
        see_url_args=("commented",),
    ),
    FeatureCard(
        slug="other-request-mode",
        title="Allow other ways of obtaining a DDP",
        problem=(
            "The request mode only offers app, browser or Portability API, but some "
            "packages come through other routes, for example a privacy centre."
        ),
        solution="Add an option Other with a free-text description.",
        user_group="Contributors, research engineers",
        technical=(
            "A choice and a text field on the upload model and form. Staff can later turn "
            "frequent answers into new fixed choices."
        ),
        see_label="Request instructions (the upload form has no Other yet)",
        see_url_name="journeys:request",
        see_url_args=("tiktok",),
    ),
)
