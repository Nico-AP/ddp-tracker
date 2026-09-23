"""Field-name and shape policy for safe enum ``values`` in schema modes.

Edit this module when adjusting which keys/shapes may keep unique values.
The describe/unify engines import these constants; they do not hard-code lists.
"""

from __future__ import annotations

# Drop ``values`` once a field takes more distinct members than this (safe mode).
MAX_ENUM_VALUES = 40
# Don't preserve long strings even if rare (likely free text / paths with ids).
MAX_PRESERVE_LEN = 96

SENSITIVE_SHAPES = frozenset(
    {
        "email",
        "phone",
        "url",
        "uuid",
        "unix_timestamp",
        "datetime",
        "date",
        "hex",
        "decimal",  # measurements / continuous numbers, not labels
        "ip_address",
        "cookie",
    }
)

# Field titles under which enum ``values`` must never be preserved (PII).
BLOCKED_VALUE_FIELDS_EXACT = frozenset(
    {
        "name",
        "names",
        "city",
        "cities",
        "town",
        "hometown",
        "firstname",
        "lastname",
        "fullname",
        "displayname",
        "username",
        "vorname",
        "nachname",
        "stadt",  # common DE labels in DDPs
        "title",
        "titles",
        "titel",
        "thread_path",
        "thread_paths",
        "threadpath",
        "threadpaths",
        "region",
        "regions",
        "country",
        "countries",
        "land",
        "länder",
        "lander",
        "cookie",
        "cookies",
        "ip",
        "ip_address",
        "ip_addresses",
        "ipaddress",
        "ipaddresses",
        "ipv4",
        "ipv6",
        "remote_addr",
        "remote_address",
        "actor",
        "actors",
        "author",
        "authors",
        "comment_author",
        "comment_authors",
        "from",
        "poster",
        "writer",
        "payment",
        "payments",
        "payment_value",
        "payment_values",
        "amount",
        "amounts",
        "price",
        "prices",
        "cost",
        "costs",
        "currency_amount",
        "transaction_amount",
        "total",
        "totals",
        "balance",
        "balances",
        "fee",
        "fees",
        "content",
        "contents",
        "original_content_owner",
        "hashtagname",
        "hashtag_name",
        "hashtag",
        "hashtags",
        "searchterm",
        "search_term",
        "search_terms",
        "searchquery",
        "search_query",
        "voting_location",
        "voting_locations",
        "votinglocation",
    }
)

# Allowlisted *_name keys that are schema identifiers, not personal names.
NAME_KEY_ALLOW = frozenset(
    {
        "field_name",
        "file_name",
        "type_name",
        "attr_name",
        "key_name",
        "column_name",
        "ent_field_name",
        "property_name",
        "metric_name",
        "event_name",
        "setting_name",
        "param_name",
        "parameter_name",
    }
)

BLOCKED_VALUE_FIELD_SUFFIXES = (
    "_title",
    "_titles",
    "_region",
    "_country",
    "_cookie",
    "_cookies",
    "_ip",
    "_ip_address",
    "_thread_path",
    "_actor",
    "_author",
    "_comment_author",
    "_payment",
    "_payment_value",
    "_amount",
    "_price",
    "_cost",
    "_balance",
    "_fee",
    "_content",
    "_hashtag",
    "_hashtag_name",
    "_search_term",
    "_search_query",
    "_content_owner",
    "_voting_location",
)

BLOCKED_VALUE_FIELD_PREFIXES = (
    "title_",
    "region_",
    "country_",
    "cookie_",
    "ip_",
    "thread_path_",
    "actor_",
    "author_",
    "comment_author_",
    "payment_",
    "amount_",
    "price_",
    "cost_",
    "content_",
    "hashtag_",
    "search_term_",
    "search_query_",
    "voting_location_",
)

# Path segments that, together, block enum values (ad preference catalogues).
AD_PREFERENCES_FILENAMES = frozenset(
    {
        "ad_preferences.json",
    }
)
AD_PREFERENCES_BLOCKED_CHILD = "label_values"
