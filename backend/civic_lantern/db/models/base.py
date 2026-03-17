from sqlalchemy.orm import declarative_base

# NOTE: When adding a new model, remember to add the table name to the trigger list
# in the migration file.
Base = declarative_base()

# Separate base for read-only database views (materialized views, etc.).
# Models that inherit from ViewBase are excluded from Base.metadata, so they
# are invisible to Alembic autogenerate and integration test create_all/drop_all.
ViewBase = declarative_base()


def enum_values_callable(enum_class):
    """Extract enum values for SQLAlchemy."""
    return [e.value for e in enum_class]
