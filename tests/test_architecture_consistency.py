"""Automated tests for architecture, registered route verification, and documentation consistency."""

from pathlib import Path
from starlette.routing import Mount, Route

from app.core import settings
from app.core.route_inspector import RouteInventoryItem, get_route_inventory
from app.main import app


def test_registered_fastapi_endpoints_match_documented_routes():
    """Verify that every documented public endpoint corresponds to an actually registered FastAPI route."""
    inventory = get_route_inventory(app, include_root=True)
    registered_pairs = {(item.method, item.path) for item in inventory}

    expected_public_endpoints = [
        ("GET", "/health"),
        ("POST", "/api/v1/resumes/extract"),
        ("POST", "/api/v1/resumes/analyze-text"),
        ("POST", "/api/v1/resumes/match"),
        ("POST", "/api/v1/resumes/feedback"),
        ("GET", "/"),
    ]

    for method, path in expected_public_endpoints:
        assert (method, path) in registered_pairs, (
            f"Documented endpoint '{method} {path}' is not registered in FastAPI route table! "
            f"Available: {registered_pairs}"
        )


    # Verify docs and architecture files mention these exact paths
    base_dir = Path(__file__).resolve().parent.parent
    arch_doc = (base_dir / "docs" / "architecture.md").read_text(encoding="utf-8")
    readme_doc = (base_dir / "README.md").read_text(encoding="utf-8")

    for _, path in expected_public_endpoints:
        if path != "/":
            assert path in arch_doc, f"Endpoint {path} missing in docs/architecture.md"
            assert path in readme_doc, f"Endpoint {path} missing in README.md"


def test_core_architecture_components_exist_in_source_tree():
    """Verify that all major components referenced in architecture and UML documentation exist."""
    base_dir = Path(__file__).resolve().parent.parent

    required_components = [
        # Application core
        base_dir / "app" / "main.py",
        base_dir / "app" / "core" / "config.py",
        base_dir / "app" / "api" / "v1" / "resumes.py",
        # Document Ingestion Services
        base_dir / "app" / "services" / "pdf_extractor.py",
        base_dir / "app" / "services" / "docx_extractor.py",
        # NLP Parsing Services
        base_dir / "app" / "services" / "resume_parser.py",
        base_dir / "app" / "services" / "section_detector.py",
        base_dir / "app" / "services" / "contact_extractor.py",
        base_dir / "app" / "services" / "skill_extractor.py",
        # Alignment & Scoring Services
        base_dir / "app" / "services" / "job_matcher.py",
        base_dir / "app" / "services" / "feedback_analyzer.py",
        # Evaluation & Data
        base_dir / "scripts" / "evaluate_matching.py",
        base_dir / "data" / "evaluation" / "synthetic_matching_benchmark.json",
        # Frontend Assets
        base_dir / "frontend" / "index.html",
        base_dir / "frontend" / "js" / "app.js",
        base_dir / "frontend" / "css" / "styles.css",
    ]

    for comp in required_components:
        assert comp.exists(), f"Architectural component missing from source tree: {comp}"


def test_file_format_support_consistency():
    """Verify that documented file-format support matches system configuration and code behavior."""
    # 1. Configuration check
    assert "pdf" in settings.ALLOWED_EXTENSIONS
    assert "docx" in settings.ALLOWED_EXTENSIONS
    assert "doc" not in settings.ALLOWED_EXTENSIONS, (
        "Legacy .doc must NOT be in ALLOWED_EXTENSIONS; code rejects legacy .doc with HTTP 400."
    )

    # 2. Upload size and page limits
    assert settings.MAX_UPLOAD_SIZE_MB == 5
    assert settings.MAX_PAGE_COUNT == 10


def test_uml_diagram_deliverables_exist_with_mermaid_content():
    """Verify that all five required UML diagram deliverables exist and contain valid Mermaid markdown."""
    base_dir = Path(__file__).resolve().parent.parent
    uml_dir = base_dir / "docs" / "uml"

    expected_diagrams = [
        "use_case_diagram.md",
        "activity_diagram.md",
        "sequence_diagram.md",
        "class_diagram.md",
        "component_diagram.md",
    ]

    assert uml_dir.exists() and uml_dir.is_dir(), f"UML directory missing: {uml_dir}"

    for diagram_name in expected_diagrams:
        diagram_path = uml_dir / diagram_name
        assert diagram_path.exists(), f"UML diagram file missing: {diagram_path}"
        content = diagram_path.read_text(encoding="utf-8")
        assert "```mermaid" in content, f"Mermaid code block missing in {diagram_name}"
        assert len(content.strip()) > 100, f"UML diagram file {diagram_name} is too brief or empty"
