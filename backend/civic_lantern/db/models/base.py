from sqlalchemy.orm import DeclarativeBase


# NOTE: When adding a new model, remember to add the table name to the trigger list
# in the migration file.
class Base(DeclarativeBase):
    pass


# Separate base for read-only database views (materialized views, etc.).
# Models that inherit from ViewBase are excluded from Base.metadata, so they
# are invisible to Alembic autogenerate and integration test create_all/drop_all.
class ViewBase(DeclarativeBase):
    pass


def enum_values_callable(enum_class):
    """Extract enum values for SQLAlchemy."""
    return [e.value for e in enum_class]
