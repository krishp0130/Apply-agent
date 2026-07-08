from __future__ import annotations

from internship_agent.parsing import (
    UNKNOWN,
    HtmlRoleParserConfig,
    parse_internship_roles_from_html,
)


def test_parse_internship_roles_extracts_configured_html_fields() -> None:
    html = """
    <section>
      <article class="job">
        <h2 class="title">Software Engineering Intern</h2>
        <p class="company">Example Co</p>
        <p class="location">Remote - US</p>
        <p class="term">Summer 2027</p>
        <ul class="skills">
          <li>Python</li>
          <li>SQL, Python</li>
        </ul>
        <p class="summary">Build internal data tools.</p>
        <a class="apply" href="/internships/software">Apply</a>
      </article>
    </section>
    """
    parser_config = HtmlRoleParserConfig(
        role_selector=".job",
        company_selector=".company",
        title_selector=".title",
        application_url_selector=".apply",
        location_selector=".location",
        internship_term_selector=".term",
        required_skills_selector=".skills li",
        description_selector=".summary",
    )

    roles = parse_internship_roles_from_html(
        html,
        source_name="example careers",
        source_url="https://example.com/careers/",
        parser_config=parser_config,
    )

    assert len(roles) == 1
    role = roles[0]
    assert role.company == "Example Co"
    assert role.title == "Software Engineering Intern"
    assert str(role.application_url) == "https://example.com/internships/software"
    assert role.source == "example careers"
    assert role.location == "Remote - US"
    assert role.remote is True
    assert role.internship_term == "Summer 2027"
    assert role.required_skills == ["Python", "SQL"]
    assert role.description == "Build internal data tools."


def test_parse_internship_roles_preserves_unknowns_without_guessing() -> None:
    html = """
    <article data-internship-role>
      <p data-location>New York, NY</p>
      <a href="not a url">Apply</a>
    </article>
    """

    roles = parse_internship_roles_from_html(
        html,
        source_name="minimal source",
    )

    assert len(roles) == 1
    role = roles[0]
    assert role.company == UNKNOWN
    assert role.title == UNKNOWN
    assert role.application_url is None
    assert role.location == "New York, NY"
    assert role.remote is None
    assert role.internship_term is None
    assert role.required_skills == []
    assert role.description is None


def test_parse_internship_roles_returns_empty_for_no_configured_cards() -> None:
    roles = parse_internship_roles_from_html(
        "<p>No configured role cards here.</p>",
        source_name="empty source",
    )

    assert roles == []
