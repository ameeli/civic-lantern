from sqlalchemy.orm import declarative_base

Base = declarative_base()


def enum_values_callable(enum_class):
    """Extract enum values for SQLAlchemy."""
    return [e.value for e in enum_class]
