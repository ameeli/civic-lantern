# Domain glossary

Terms used in the backend's ingestion code. Use these names in code, tests and reviews.

**Ingestion**: the declaration of one FEC entity: name, scope, endpoint, schema, table, optional corrections and summed fields. Lives in `jobs/ingestors/<entity>.py`; run by `jobs/pipeline.py`.

**Scope**: how an ingestion is bounded: a *date window* (resumes from the watermark) or *per cycle* (re-pulls one election cycle).

**Watermark**: the time of an entity's last successful date-window run; the next run starts there.

**Cycle readiness**: a cycle appears in the frontend once every per-cycle ingestion has succeeded for it and its tables have rows.

**Committee correction**: an override (add a committee FEC dropped) or a split (apportion a shared committee at a *split date*).

**Partial fetch**: some pages failed after retries. It's allowed only for ingestions whose rows don't combine several pieces.
