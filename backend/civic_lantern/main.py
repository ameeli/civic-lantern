from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from civic_lantern.api.routers import candidate_spending, candidates, election_spending
from civic_lantern.utils.logging import configure_logging

configure_logging()

app = FastAPI(
    title="The Civic Lantern",
    description="Campaign finance transparency platform tracking outside spending.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    # TODO: update to actual domain in production.
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(candidates.router, prefix="/api/v1")
app.include_router(candidate_spending.router, prefix="/api/v1")
app.include_router(election_spending.router, prefix="/api/v1")
