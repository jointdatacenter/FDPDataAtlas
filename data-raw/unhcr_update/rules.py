"""Keyword rules that reproduce the atlas's hand-coded flags from catalog text.

Imported by evaluate.py (checks the rules against the existing hand-labelled
studies) and build.py (applies them to studies that are new to the atlas).
"""
import re

# Each topic tag is set when any pattern matches the study's notes (scope) text.
TAG_PATTERNS = {
    "food_insecurity": r"food|nutrition|hunger|\bdiet|\bmeals?\b|\bfcs\b|rcsi|\brations?\b",
    "health": r"health|nutrition|disab|vaccin|immuni|illness|disease|medical|mental|morbidity|anthropometr|maternal|covid|hand-washing|defecation",
    "water_sanitation": r"water|sanitation|hygiene|wash\b|latrine|toilet",
    "education": r"educat|school|literacy|learning",
    "welfare": r"welfare|poverty|consumption|expenditure|well-being|wellbeing|living standard|income",
    "labor_employment": r"employ|labou?r|occupation|\bwork|\bjobs?\b",
    "finance_credit_debt": r"financ|credit|debt|loan|saving|bank|borrow",
    "protection": r"protect|documentation|legal|civil status|registration|gbv|sgbv|violence|abuse|child protection",
    "gender": r"gender|women|woman|female|girls|empowerment",
    "safety_security_conflict": r"safety|(?<!food )(?<!food and nutrition )security|conflict|crime|\bmines?\b|explosive|threat|arrest|peace",
    "housing_assets": r"housing|asset|dwelling|land and property|hlp\b|property",
    "shocks": r"shock",
    "agriculture_livestock_fishery": r"agricultur|livestock|farm|crop|fish|cultivat",
    "subjective_poverty": r"subjective|life satisfaction|happiness",
    "coping_mechanisms": r"coping",
    "demographics": r"demograph|household composition|age and sex|household members",
    "social": r"social cohesion|social capital|social network|community relations",
    "remmitance": r"remit",
    "child_labor": r"child labou?r",
    "migration": r"migrat|mobility",
}
TAG_RES = {k: re.compile(v, re.I) for k, v in TAG_PATTERNS.items()}

# Project-specific studies monitor one programme or its beneficiaries, rather
# than describing a population.
PROJECT_RE = re.compile(
    r"post[- ]distribution|\bpdm\b|beneficiar|programme monitoring|program monitoring"
    r"|project monitoring|cash[- ]based intervention|cash assistance|baseline and endline"
    r"|endline|end-line|impact evaluation|monitoring of .*(cash|assistance|distribution)"
    r"|livelihoods? (programme|program)|energy monitoring framework|monitoring of the .*programme"
    r"|distribution monitoring|end user survey",
    re.I,
)

IDP_RE = re.compile(r"\bidps?\b|internally displaced|internal displacement", re.I)


def tags_for(notes):
    text = notes or ""
    return {k: int(bool(rx.search(text))) for k, rx in TAG_RES.items()}


def is_project_specific(title, series):
    return int(bool(PROJECT_RE.search(f"{title} {series}")))


def is_idp(title, universe):
    return int(bool(IDP_RE.search(f"{title} {universe}")))
