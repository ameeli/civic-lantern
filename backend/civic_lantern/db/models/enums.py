from enum import Enum


class OfficeTypeEnum(str, Enum):
    """Federal office types."""

    HOUSE = "H"
    SENATE = "S"
    PRESIDENT = "P"


class SupportOpposeEnum(str, Enum):
    """Independent expenditure support/oppose indicator."""

    SUPPORT = "S"
    OPPOSE = "O"


class CommitteeTypeEnum(str, Enum):
    """FEC committee type codes."""

    COMMUNICATION_COST = "C"
    DELEGATE = "D"
    ELECTIONEERING = "E"
    HOUSE = "H"
    INDEPENDENT_EXPENDITURE = "I"
    PAC_NONQUALIFIED = "N"
    SUPER_PAC = "O"
    PRESIDENTIAL = "P"
    PAC_QUALIFIED = "Q"
    SENATE = "S"
    SINGLE_CANDIDATE = "U"
    PAC_NONCONTRIBUTION_NONQUALIFIED = "V"
    PAC_NONCONTRIBUTION_QUALIFIED = "W"
    PARTY_NONQUALIFIED = "X"
    PARTY_QUALIFIED = "Y"
    NATIONAL_PARTY = "Z"
