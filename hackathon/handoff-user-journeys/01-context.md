# 01. Context

## The hackathon

- **Event:** DDP2026 Hackathon, infrastructure track. Aim: further develop the DDP Tracker.
- **Hekmat's role:** member of the infrastructure track (postdoctoral researcher, Erasmus University Rotterdam).
- **Infrastructure track contributors (from the hackathon document):**
  - Nico Pfiffner (University of Zurich), the tool's main developer;
  - Lion Wedel (Weizenbaum Institute);
  - Hekmat Alrouh (Erasmus University Rotterdam);
  - Danielle McCool (Utrecht University);
  - Daniel Jurg (Vrije Universiteit Brussel);
  - Deike Schulz (NHL Stenden UAS);
  - Nir Grinberg (Ben-Gurion University).
- **A second group** in the same document lists Thomas Friemel and Sina Horner (University of Zurich).
- **Stage:** the team is working at the conceptual level: which features each user role needs. The prototype in this handoff is Hekmat's way of making that concrete.

## The tool

The **DDP Tracker** (https://www.ddp-tracker.org/) tracks how platforms' **data download packages** (DDPs, also called data takeouts) change over time.

- People upload the DDP they requested from a platform (TikTok, Instagram, Facebook, YouTube, …).
- The app parses it into a schema of files and data points, keeps only the structure, and deletes the file.
- Curators then:
  - **annotate** data points (what a value means);
  - describe **representations** (what a list's items mean, in a vocabulary shared across platforms: actor, activity, object, target).
- Everyone can explore the result per platform.

The tool is built by the Data Donation Lab at the University of Zurich (https://datadonation.uzh.ch/en/). The same group built the Data Donation Module (DDM), a tool for collecting data donations, described in Pfiffner, Witlox and Friemel (2024), *Computational Communication Research* 6(2), https://doi.org/10.5117/CCR2024.2.4.PFIF.

The DDM is relevant here. Researchers configure DDM "File Blueprints", which specify for each file:

- the expected file name;
- the required fields;
- extraction rules.

That is exactly the information the tracker holds, which is why an "export as DDM blueprint" step appears in the journeys.

## User groups (from the hackathon document)

- Researchers interested in concepts
- Researchers setting up parsing
- Policy people
- (Participants, Students)
- AI readable (API endpoints to disclose schema and structures)

The features analysis expands these into **eight roles**:

1. substantive researcher;
2. research engineer;
3. policy stakeholder;
4. contributor (uploader);
5. curator or platform moderator;
6. instance administrator;
7. machine consumer (scripts, tools, LLMs);
8. learner (participants, students, the public).

See `../DDP-Tracker_features-by-role.md`, section 2.

## The key tension

Research engineers want an **exhaustive** list: every path, type, format and variant. Substantive researchers want a **digestible** list of the variables and representations relevant to their research question.

The agreed principle is **"two views, one model, and a hand-off"**:

- a *concept view* for researchers;
- the existing *structure view* (explorer) for engineers;
- a *study shortlist*, built in the concept view and exported from the structure view as a codebook and extraction specification.

The prototype should make this visible.

## Other ideas raised in the hackathon document (30 September version)

- **Datetime and time zones:**
  - which datetime standard HTML exports use;
  - whose time zone a timestamp represents. The team proposes a `tz_whos` attribute, and notes that TikTok appears to use UTC.
- **Data logs as data donations** (open question).
- **Field-specific top-level ontology:** different research areas want different labels.
- **Default public page versus user or community page:** perhaps an explore view "without annotation mask".
- **API endpoints** for researchers and LLMs.
- **Sorting and prioritising:**
  - sort data point lists by most used or most relevant;
  - prioritise the annotations that matter most (annotating is labour-intensive).
- **Refined focus:** research and engineering perspectives, also for education.
- **Official platform documentation:**
  - use it to seed annotations, possibly as a separate annotation kind;
  - report the gaps between that documentation and actual DDPs.
- **Seeding sources:** pairing HTML and JSON exports; data structure documentation.
- **Governance:**
  - DDP hubs responsible for single platforms, with moderators;
  - seeding workload, possibly with AI-flagged labels checked over time;
  - funding.
- **Translations:** people adding translations of field names to build a multilingual dictionary.
- **Examples as a table:** show example values as a table with title and value, and allow annotating specific labels.
- **Paired donation sets:** uploads that differ in one aspect only, such as language or HTML versus JSON.
- **Second group's feature requests:**
  - edit your own suggestions;
  - time zone origin;
  - recognising "no data" markers such as "No data available".
- **Issues reported:**
  - file paths anonymised when values repeat;
  - "earliest date" upload confusing;
  - no "Other" download option (ChatGPT privacy centre);
  - CSV upload for Twitter missing;
  - language matching of paths;
  - registration e-mail says example.com;
  - TikTok chat history not anonymised.

## Sources

- Repository: https://github.com/Nico-AP/ddp-tracker (branch `dev`)
- Documentation: https://www.ddp-tracker.org/docs/
- Data Donation Lab: https://datadonation.uzh.ch/en/
- Hackathon document: https://docs.google.com/document/d/1OxUawA7hqIjOCjSmRn8rTSojv0jCSojuSXnBeLAvFRs/edit
- Paper: Pfiffner, N., Witlox, P. and Friemel, T. N. (2024). Data Donation Module: A web application for collecting and enriching data donations. *Computational Communication Research*, 6(2), 1–19.
