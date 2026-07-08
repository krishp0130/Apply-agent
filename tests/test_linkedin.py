from __future__ import annotations

from internship_agent.linkedin import (
    LINKEDIN_SOURCE,
    LinkedInSearchConfig,
    linkedin_browser_guardrails,
    parse_linkedin_html_snippet,
    parse_linkedin_job_cards,
    parse_linkedin_snippet,
    parse_linkedin_text_snippet,
)
from internship_agent.parsing import UNKNOWN


def test_parse_linkedin_job_cards_maps_known_fields_and_source() -> None:
    roles = parse_linkedin_job_cards(
        [
            {
                "job_title": "Software Engineering Intern",
                "company_name": "Example Robotics",
                "location": "San Francisco Bay Area",
                "job_url": "/jobs/view/123456789",
                "posted_at": "2 days ago",
                "skills": ["Python", "SQL", "Python"],
                "summary": "Build internal robotics tooling.",
            },
        ],
        config=LinkedInSearchConfig(
            search_terms=["software"],
            recency_days=7,
            location_filters=["san francisco"],
        ),
    )

    assert len(roles) == 1
    role = roles[0]
    assert role.company == "Example Robotics"
    assert role.title == "Software Engineering Intern"
    assert str(role.application_url) == "https://www.linkedin.com/jobs/view/123456789"
    assert role.source == LINKEDIN_SOURCE
    assert role.location == "San Francisco Bay Area"
    assert role.remote is None
    assert role.internship_term == UNKNOWN
    assert role.required_skills == ["Python", "SQL"]
    assert role.description == "Build internal robotics tooling."


def test_parse_linkedin_job_cards_preserves_unknowns_without_guessing() -> None:
    roles = parse_linkedin_job_cards([{"posted_at": "just posted"}])

    assert len(roles) == 1
    role = roles[0]
    assert role.company == UNKNOWN
    assert role.title == UNKNOWN
    assert role.application_url is None
    assert role.location == UNKNOWN
    assert role.internship_term == UNKNOWN
    assert role.required_skills == []
    assert role.description == UNKNOWN


def test_parse_linkedin_job_cards_applies_recent_scope_when_known() -> None:
    roles = parse_linkedin_job_cards(
        [
            {
                "title": "Backend Intern",
                "company": "Fresh Co",
                "location": "Remote",
                "posted": "3 days ago",
            },
            {
                "title": "Backend Intern",
                "company": "Old Co",
                "location": "Remote",
                "posted": "2 weeks ago",
            },
        ],
        config=LinkedInSearchConfig(search_terms=["backend"], recency_days=7),
    )

    assert [role.company for role in roles] == ["Fresh Co"]
    assert roles[0].remote is True


def test_parse_linkedin_html_snippet_extracts_linkedin_like_cards() -> None:
    html = """
    <ul>
      <li class="jobs-search-results__list-item" data-job-id="123">
        <a class="job-card-container__link" href="/jobs/view/123">
          Machine Learning Intern
        </a>
        <span class="job-card-container__primary-description">Model Co</span>
        <span class="job-card-container__metadata-item">New York, NY</span>
        <time>1 day ago</time>
      </li>
      <li class="jobs-search-results__list-item" data-job-id="456">
        <a class="job-card-container__link" href="/jobs/view/456">
          Machine Learning Intern
        </a>
        <span class="job-card-container__primary-description">Older Co</span>
        <span class="job-card-container__metadata-item">New York, NY</span>
        <time>1 month ago</time>
      </li>
    </ul>
    """

    roles = parse_linkedin_html_snippet(
        html,
        config=LinkedInSearchConfig(
            search_terms=["machine learning"],
            recency_days=7,
            location_filters=["new york"],
        ),
    )

    assert len(roles) == 1
    assert roles[0].company == "Model Co"
    assert roles[0].title == "Machine Learning Intern"
    assert str(roles[0].application_url) == "https://www.linkedin.com/jobs/view/123"
    assert roles[0].source == LINKEDIN_SOURCE
    assert roles[0].location == "New York, NY"


def test_parse_linkedin_text_snippet_handles_user_copied_text() -> None:
    text = """
    Data Science Intern
    Analytics Co
    Remote - United States
    4 days ago
    https://www.linkedin.com/jobs/view/999
    Work with product analytics data.
    """

    roles = parse_linkedin_text_snippet(
        text,
        config=LinkedInSearchConfig(search_terms=["data"], recency_days=7),
    )

    assert len(roles) == 1
    assert roles[0].company == "Analytics Co"
    assert roles[0].title == "Data Science Intern"
    assert roles[0].remote is True
    assert roles[0].description == "Work with product analytics data."


def test_parse_linkedin_snippet_dispatches_html_or_text() -> None:
    html_roles = parse_linkedin_snippet(
        """
        <article data-linkedin-job-card>
          <h3>Frontend Intern</h3>
          <p data-company>Interface Co</p>
          <p data-location>Remote</p>
          <p data-posted-at>today</p>
        </article>
        """,
    )
    text_roles = parse_linkedin_snippet(
        """
        Platform Intern
        Systems Co
        Austin, TX
        today
        """,
    )

    assert html_roles[0].company == "Interface Co"
    assert text_roles[0].company == "Systems Co"


def test_linkedin_browser_guardrails_forbid_unsafe_automation() -> None:
    guardrails = linkedin_browser_guardrails()

    assert guardrails.pause_on_login_or_auth is True
    assert guardrails.pause_on_captcha is True
    assert guardrails.pause_on_mfa is True
    assert guardrails.must_not_submit_applications is True
    assert guardrails.credentials_supported is False
    assert guardrails.login_bypass_supported is False
    assert guardrails.default_scraping_loop_supported is False
