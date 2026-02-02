import re
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from civic_lantern.db.models.enums import OfficeTypeEnum


class CandidateIn(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    office: Optional[OfficeTypeEnum] = None
    state: Optional[str] = None
    party: Optional[str] = None
    party_full: Optional[str] = None
    district: Optional[str] = None
    incumbent_challenge: Optional[str] = None
    incumbent_challenge_full: Optional[str] = None
    candidate_status: Optional[str] = None
    active_through: Optional[int] = None
    cycles: List[int] = Field(default_factory=list)
    election_years: List[int] = Field(default_factory=list)
    federal_funds_flag: Optional[bool] = None
    has_raised_funds: Optional[bool] = None
    first_file_date: Optional[date] = None
    last_f2_date: Optional[date] = None
    last_file_date: Optional[date] = None
    load_date: Optional[datetime] = None

    model_config = ConfigDict(str_strip_whitespace=True)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, v: Any) -> str:
        if not isinstance(v, str) or not v.strip():
            return v
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")

        UPPER_SUFFIXES = {
            "II",
            "III",
            "IV",
            "V",
            "VI",
            "VII",
            "VIII",
            "IX",
            "X",
            "PHD",
            "MD",
        }
        TITLE_SUFFIXES = {"JR", "SR", "ESQ"}

        def title_with_apostrophe(text: str) -> str:
            t = text.title()
            return re.sub(
                r"([a-zA-Z]')([a-z])", lambda m: m.group(1) + m.group(2).upper(), t
            )

        if "," not in v:
            words = v.split()
            return " ".join(title_with_apostrophe(w) for w in words)

        parts = [p.strip() for p in v.split(",")]
        last_name = parts[0]
        other_words = " ".join(parts[1:]).split()

        clean_words = []
        found_suffixes = []

        for w in other_words:
            norm = w.upper().rstrip(".")
            if norm in UPPER_SUFFIXES:
                found_suffixes.append(norm)
            elif norm in TITLE_SUFFIXES:
                found_suffixes.append(norm.title())
            else:
                clean_words.append(w)

        core_name_parts = clean_words + [last_name]
        full_name = " ".join(title_with_apostrophe(w) for w in core_name_parts)

        if found_suffixes:
            return f"{full_name} {' '.join(found_suffixes)}"

        return full_name

    @field_validator("office", mode="before")
    @classmethod
    def normalize_office(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v

    @field_validator("district")
    @classmethod
    def pad_district(cls, v: Optional[str]) -> Optional[str]:
        """Ensures district '9' becomes '09'."""
        if v and v.isdigit():
            return v.zfill(2)
        return v
