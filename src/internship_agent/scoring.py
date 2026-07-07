from __future__ import annotations

from internship_agent.models import FitScore, InternshipRole, UserProfile


DEFAULT_FIT_THRESHOLD = 70


def score_role(
    profile: UserProfile,
    role: InternshipRole,
    threshold: int = DEFAULT_FIT_THRESHOLD,
) -> FitScore:
    """Score a role using explicit profile and role evidence only."""

    score = 0
    reasons: list[str] = []
    concerns: list[str] = []

    profile_skills = _normalize_set(profile.skills)
    role_skills = _normalize_set(role.required_skills)
    matched_skills = sorted(profile_skills.intersection(role_skills))

    if role_skills:
        skill_points = round((len(matched_skills) / len(role_skills)) * 45)
        score += skill_points
        if matched_skills:
            reasons.append(f"Matches required skills: {', '.join(matched_skills)}.")
        missing_skills = sorted(role_skills.difference(profile_skills))
        if missing_skills:
            concerns.append(f"Missing listed skills: {', '.join(missing_skills)}.")
    else:
        concerns.append("Role has no explicit required skills to compare.")

    role_text = " ".join(
        value
        for value in [role.title, role.description or "", role.sponsorship_notes or ""]
        if value
    ).lower()
    matched_experience = [
        keyword for keyword in profile.experience_keywords if keyword.lower() in role_text
    ]
    if matched_experience:
        score += min(20, len(matched_experience) * 5)
        reasons.append(
            f"Role text matches experience keywords: {', '.join(matched_experience)}."
        )
    elif profile.experience_keywords:
        concerns.append("No profile experience keywords were found in the role text.")

    if _location_matches(profile, role):
        score += 15
        reasons.append("Location or remote preference matches.")
    elif profile.desired_locations:
        concerns.append("Location does not clearly match stated preferences.")

    if role.internship_term and _contains_normalized(profile.desired_terms, role.internship_term):
        score += 10
        reasons.append("Internship term matches stated preferences.")
    elif profile.desired_terms and role.internship_term:
        concerns.append("Internship term does not match stated preferences.")

    sponsorship_text = (role.sponsorship_notes or "").lower()
    if profile.requires_sponsorship is True:
        if any(term in sponsorship_text for term in ["sponsor", "cpt", "opt"]):
            score += 10
            reasons.append("Role includes sponsorship, CPT, or OPT notes.")
        else:
            concerns.append("Sponsorship compatibility is unknown.")
    elif profile.requires_sponsorship is False:
        score += 10

    bounded_score = max(0, min(100, score))
    if not reasons:
        concerns.append("No positive fit evidence was available.")

    return FitScore(
        company=role.company,
        role_title=role.title,
        score=bounded_score,
        threshold=threshold,
        reasons=reasons,
        concerns=concerns,
    )


def _normalize_set(values: list[str]) -> set[str]:
    return {value.strip().lower() for value in values if value.strip()}


def _contains_normalized(options: list[str], value: str) -> bool:
    normalized_value = value.strip().lower()
    return any(option.strip().lower() == normalized_value for option in options)


def _location_matches(profile: UserProfile, role: InternshipRole) -> bool:
    if role.remote is True and any(
        location.strip().lower() == "remote" for location in profile.desired_locations
    ):
        return True

    if not role.location:
        return False

    normalized_location = role.location.lower()
    return any(
        desired_location.strip().lower() in normalized_location
        for desired_location in profile.desired_locations
    )
