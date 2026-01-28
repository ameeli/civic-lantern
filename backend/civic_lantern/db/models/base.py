from sqlalchemy.orm import declarative_base

# NOTE: When adding a new model, remember to add the table name to the trigger list
# in the migration file.
Base = declarative_base()


def enum_values_callable(enum_class):
    """Extract enum values for SQLAlchemy."""
    return [e.value for e in enum_class]
