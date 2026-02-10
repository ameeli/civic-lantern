from sqlalchemy import DDL, Column, DateTime, event, func
from sqlalchemy.orm import declarative_mixin

CREATE_FUNC_DDL = DDL("""
    CREATE OR REPLACE FUNCTION set_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
    END;
    $$ language 'plpgsql';
""")


@declarative_mixin
class TimestampMixin:
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    @classmethod
    def __declare_last__(cls):
        """Hook into the end of class declaration to attach triggers."""

        trigger_ddl = DDL(f"""
            CREATE TRIGGER set_updated_at_{cls.__tablename__}
            BEFORE UPDATE ON {cls.__tablename__}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """)

        event.listen(
            cls.__table__.metadata,
            "before_create",
            CREATE_FUNC_DDL.execute_if(dialect="postgresql"),
        )

        event.listen(
            cls.__table__, "after_create", trigger_ddl.execute_if(dialect="postgresql")
        )
