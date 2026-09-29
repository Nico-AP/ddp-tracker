# DDP Tracker

Platforms such as TikTok, Instagram or YouTube let you download the data they hold about you: a
**data download package (DDP)**, also called a data takeout. The DDP Tracker helps you understand
what these packages contain:

- **what** is in a platform's DDP: which files, which fields, what kind of values;
- **what it means**: a plain description of each piece of information;
- **how platforms compare**: the same concept (say, "user watched video") on different platforms;
- **how it changes**: what platforms add, rename or remove over time.

It learns all of this from DDPs that people upload, but it keeps only their **structure**, never
the data in them (unless users provide their explicit consent to include them).
See [Privacy](guide/privacy.md).

## How it works

1. Someone requests their DDP from a platform and [uploads it](guide/uploading.md).
2. The DDP Tracker reads the file, notes its structure (which fields exist, what type they are)
   and deletes the file.
3. The structure is compared with what is already known about the platform: what is
   [new, known, changed or missing](guide/reviewing.md).
4. Curators [describe what each data point means](guide/annotating.md) and
   [what lists' entries represent, in terms shared across platforms](guide/representations.md).
5. Everyone can [explore the result](guide/exploring.md), platform by platform.

## Where to go

| I want to…                                    | Go to                                                               |
|-----------------------------------------------|---------------------------------------------------------------------|
| see what a platform's DDP contains            | [Exploring platforms](guide/exploring.md)                           |
| find out what a field means                   | [Exploring platforms › Annotations](guide/exploring.md#annotations) |
| compare platforms                             | [Representations](guide/representations.md)                         |
| upload my own DDP                             | [Uploading a DDP](guide/uploading.md)                               |
| understand the review of my upload            | [Reviewing an upload](guide/reviewing.md)                           |
| describe data points or suggest improvements  | [Annotating](guide/annotating.md)                                   |
| know what happens to my data                  | [Privacy](guide/privacy.md)                                         |
| look up a term                                | [Glossary](guide/glossary.md)                                       |

Exploring is open to everyone. Uploading, annotating and suggesting need an account,
which can be created through the signup form.

For developers and researchers working with the underlying data, the
[technical reference](tracker/concepts.md) has the precise definitions and the
[parser's schema format](ddp_parser/index.md).
