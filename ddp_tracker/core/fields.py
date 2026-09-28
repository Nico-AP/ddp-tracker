"""Model fields shared between apps."""

from typing import Any

from django.db import models
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models.expressions import Expression


class OrderedJSONField(models.JSONField):
    """A ``JSONField`` that keeps the order of object keys.

    Django stores JSON as ``jsonb`` on PostgreSQL, which sorts object keys (by length, then
    bytewise), so ``{"Datum": …, "Link": …}`` comes back as ``{"Link": …, "Datum": …}``. Where the
    order carries meaning (a schema document: the keys' order in the file), this stores ``json``,
    which keeps the text as it was sent. There are no ``jsonb`` operators on it (no equality, no
    indexes); other databases are unaffected.
    """

    def db_type(self, connection: BaseDatabaseWrapper) -> str | None:
        if connection.vendor == "postgresql":
            return "json"
        return super().db_type(connection)

    def get_db_prep_value(
        self,
        value: Any,  # noqa: ANN401 - any JSON value
        connection: BaseDatabaseWrapper,
        prepared: bool = False,
    ) -> Any:  # noqa: ANN401
        adapted = super().get_db_prep_value(value, connection, prepared)
        if connection.vendor == "postgresql":
            from psycopg.types.json import Json, Jsonb  # noqa: PLC0415 - PostgreSQL only

            if isinstance(adapted, Jsonb):  # sent as jsonb, it would be sorted on the way in
                return Json(adapted.obj, dumps=adapted.dumps)
        return adapted

    def from_db_value(
        self,
        value: Any,  # noqa: ANN401 - any JSON value
        expression: Expression,
        connection: BaseDatabaseWrapper,
    ) -> Any:  # noqa: ANN401
        if value is not None and not isinstance(value, str):
            return value  # psycopg decodes json itself (Django only asks for jsonb as text)
        return super().from_db_value(value, expression, connection)
