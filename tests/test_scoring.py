from internship_agent.models import InternshipRole, UserProfile
from internship_agent.scoring import score_role


def test_score_role_uses_explicit_evidence() -> None:
    profile = UserProfile(
        name="Test User",
        skills=["Python", "Playwright", "Pydantic"],
        experience_keywords=["automation", "recruiting"],
        desired_locations=["New York", "Remote"],
        desired_terms=["Summer 2027"],
        requires_sponsorship=False,
    )
    role = InternshipRole(
        company="Example Co",
        title="Software Engineering Intern",
        source="manual",
        location="New York, NY",
        internship_term="Summer 2027",
        required_skills=["Python", "Pydantic", "SQL"],
        description="Build recruiting automation tools.",
    )

    fit_score = score_role(profile, role)

    assert fit_score.score >= 70
    assert fit_score.below_threshold is False
    assert any("python" in reason.lower() for reason in fit_score.reasons)
    assert any("sql" in concern.lower() for concern in fit_score.concerns)


def test_score_role_records_unknown_evidence_as_concern() -> None:
    profile = UserProfile(name="Test User", skills=["Python"], desired_locations=["Remote"])
    role = InternshipRole(company="Example Co", title="Intern", source="manual")

    fit_score = score_role(profile, role)

    assert fit_score.below_threshold is True
    assert "Role has no explicit required skills to compare." in fit_score.concerns
    assert "Location does not clearly match stated preferences." in fit_score.concerns
