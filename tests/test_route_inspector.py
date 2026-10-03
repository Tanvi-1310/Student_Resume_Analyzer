"""Comprehensive unit tests for the canonical FastAPI route inspector."""

from pathlib import Path
import pytest
from fastapi import APIRouter, FastAPI
from pydantic import ValidationError

from app.core.route_inspector import (
    DuplicateRouteError,
    RouteInventoryItem,
    RouteInventoryValidationError,
    UnregisteredRouteError,
    get_route_inventory,
)
from app.main import app as live_app


# ---------------------------------------------------------------------------
# 1. Canonical Schema Verification
# ---------------------------------------------------------------------------

def test_route_inventory_item_schema_valid():
    """Verify that RouteInventoryItem validates required fields and preserves types."""
    item = RouteInventoryItem(
        method="POST",
        path="/api/v1/test",
        name="test_endpoint",
        source="tests.test_route_inspector.dummy_handler",
    )
    assert item.method == "POST"
    assert item.path == "/api/v1/test"
    assert item.name == "test_endpoint"
    assert item.source == "tests.test_route_inspector.dummy_handler"


def test_route_inventory_item_optional_attributes():
    """Verify that optional attributes (name, source) default to None and do not crash."""
    item = RouteInventoryItem(method="GET", path="/ping")
    assert item.name is None
    assert item.source is None
    assert item.method == "GET"
    assert item.path == "/ping"


def test_route_inventory_item_validation_errors():
    """Verify that missing required fields trigger Pydantic validation errors."""
    with pytest.raises(ValidationError):
        # Missing path
        RouteInventoryItem(method="GET")

    with pytest.raises(ValidationError):
        # Missing method
        RouteInventoryItem(path="/health")


# ---------------------------------------------------------------------------
# 2. Strict Prohibition of Private Framework Internals
# ---------------------------------------------------------------------------

def test_no_private_framework_internals_referenced():
    """Verify that the route inspector module does not reference private FastAPI/Starlette internals."""
    inspector_file = Path(__file__).resolve().parent.parent / "app" / "core" / "route_inspector.py"
    assert inspector_file.exists(), f"Missing file: {inspector_file}"
    content = inspector_file.read_text(encoding="utf-8")

    forbidden_tokens = [
        "_IncludedRouter",
        "effective_candidates",
        "effective_route_contexts",
        "include_context",
        "original_router",
        "starlette_route",
    ]

    for token in forbidden_tokens:
        assert token not in content, (
            f"Private framework internal '{token}' was found in app/core/route_inspector.py! "
            f"The route inspector must only use stable, public framework APIs."
        )


# ---------------------------------------------------------------------------
# 3. Runtime Discovery on Real FastAPI Application
# ---------------------------------------------------------------------------

def test_live_app_route_discovery():
    """Verify that get_route_inventory derives all expected public application routes from live_app."""
    inventory = get_route_inventory(live_app, include_root=True)
    assert len(inventory) >= 6

    # Verify every item is a canonical RouteInventoryItem with uppercase method and non-empty path
    for item in inventory:
        assert isinstance(item, RouteInventoryItem)
        assert item.method == item.method.upper()
        assert item.path.startswith("/")
        assert len(item.path) > 0

    route_map = {(item.method, item.path): item.name for item in inventory}

    # Verify core application API endpoints exist
    assert ("GET", "/health") in route_map
    assert ("POST", "/api/v1/resumes/extract") in route_map
    assert ("POST", "/api/v1/resumes/analyze-text") in route_map
    assert ("POST", "/api/v1/resumes/match") in route_map
    assert ("POST", "/api/v1/resumes/feedback") in route_map
    assert ("GET", "/") in route_map

    # Direct routes should retain their public names
    assert route_map[("GET", "/health")] == "health_check"
    assert route_map[("GET", "/")] == "serve_index"

    # OpenAPI-derived routes without public route object attributes safely have name=None
    assert route_map[("POST", "/api/v1/resumes/extract")] is None


# ---------------------------------------------------------------------------
# 4. Router Prefix Correctness (No Manual String Concatenation)
# ---------------------------------------------------------------------------

def test_router_prefix_correctness_without_manual_reconstruction():
    """Verify that routes included via APIRouter prefixes are discovered with their full final path."""
    test_app = FastAPI()
    test_router = APIRouter(prefix="/v2/analytics")

    @test_router.get("/metrics", name="get_metrics")
    def sample_metrics():
        return {"ok": True}

    @test_router.post("/events", name="post_event")
    def sample_events():
        return {"created": True}

    test_app.include_router(test_router)

    inventory = get_route_inventory(test_app)
    paths = {item.path for item in inventory}
    assert "/v2/analytics/metrics" in paths
    assert "/v2/analytics/events" in paths

    pairs = {(item.method, item.path): item.name for item in inventory}
    assert ("GET", "/v2/analytics/metrics") in pairs
    assert ("POST", "/v2/analytics/events") in pairs


# ---------------------------------------------------------------------------
# 5. OpenAPI Fallback & Missing Names
# ---------------------------------------------------------------------------

def test_openapi_fallback_for_routes_and_unnamed_fallback():
    """Verify that routes discovered via OpenAPI fallback correctly default name and source to None."""
    test_app = FastAPI()
    router = APIRouter(prefix="/api/test")

    @router.get("/data")
    def get_data():
        return {"value": 42}

    test_app.include_router(router)

    inventory = get_route_inventory(test_app)
    assert len(inventory) == 1
    assert inventory[0].method == "GET"
    assert inventory[0].path == "/api/test/data"
    # When extracted via OpenAPI fallback, name is safely None rather than using private wrapper internals
    assert inventory[0].name in [None, "get_data"]
    assert inventory[0].source in [None, f"{__name__}.get_data"]


def test_openapi_unregistered_phantom_route_detected_and_rejected():
    """Verify that if OpenAPI contains an unbacked route, UnregisteredRouteError is raised."""
    test_app = FastAPI()

    @test_app.get("/valid")
    def valid_route():
        return {"ok": True}

    # Inject a phantom endpoint into openapi schema without registering a route
    original_openapi = test_app.openapi

    def mock_openapi():
        schema = original_openapi()
        schema["paths"]["/phantom/unregistered"] = {
            "post": {"summary": "Phantom endpoint", "responses": {"200": {"description": "OK"}}}
        }
        return schema

    test_app.openapi = mock_openapi

    with pytest.raises(UnregisteredRouteError) as exc_info:
        get_route_inventory(test_app)

    assert "POST /phantom/unregistered" in str(exc_info.value)
    assert "does not correspond to an active registered route" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 6. Explicit Documentable-Route Filtering
# ---------------------------------------------------------------------------

def test_filtering_framework_docs_routes():
    """Verify that OpenAPI documentation routes are excluded by default and included only on request."""
    inv_default = get_route_inventory(live_app, include_docs=False)
    paths_default = {item.path for item in inv_default}
    assert "/openapi.json" not in paths_default
    assert "/docs" not in paths_default
    assert "/redoc" not in paths_default

    inv_with_docs = get_route_inventory(live_app, include_docs=True)
    paths_docs = {item.path for item in inv_with_docs}
    assert "/openapi.json" in paths_docs
    assert "/docs" in paths_docs


def test_filtering_root_route():
    """Verify that the landing route (/) can be optionally included or excluded deterministically."""
    inv_with_root = get_route_inventory(live_app, include_root=True)
    assert any(item.path == "/" for item in inv_with_root)

    inv_without_root = get_route_inventory(live_app, include_root=False)
    assert not any(item.path == "/" for item in inv_without_root)


def test_filtering_static_mounts():
    """Verify that static file mounts (/css, /js) are excluded from HTTP routes by default."""
    inv_no_static = get_route_inventory(live_app, include_static=False)
    assert not any(item.method == "MOUNT" for item in inv_no_static)
    assert not any(item.path in ["/css", "/js"] for item in inv_no_static)

    inv_with_static = get_route_inventory(live_app, include_static=True)
    static_paths = {item.path for item in inv_with_static if item.method == "MOUNT"}
    assert "/css" in static_paths or "/js" in static_paths


# ---------------------------------------------------------------------------
# 7. Duplicate Route Detection
# ---------------------------------------------------------------------------

def test_duplicate_route_same_method_and_path_raises_error():
    """Verify that duplicate registrations with identical (method, path) raise DuplicateRouteError."""
    dup_app = FastAPI()

    @dup_app.get("/items", name="get_items_first")
    def handler_one():
        return []

    @dup_app.get("/items", name="get_items_second")
    def handler_two():
        return []

    with pytest.raises(DuplicateRouteError) as exc_info:
        get_route_inventory(dup_app)

    err_msg = str(exc_info.value)
    assert "Duplicate route registration detected" in err_msg
    assert "GET /items" in err_msg
    assert "get_items_first" in err_msg
    assert "get_items_second" in err_msg


def test_distinct_methods_on_same_path_accepted():
    """Verify that different HTTP methods on the same path are accepted as distinct valid routes."""
    multi_method_app = FastAPI()

    @multi_method_app.get("/resource", name="read_resource")
    def get_resource():
        return {}

    @multi_method_app.post("/resource", name="create_resource")
    def post_resource():
        return {}

    @multi_method_app.delete("/resource", name="delete_resource")
    def delete_resource():
        return {}

    inventory = get_route_inventory(multi_method_app)
    assert len(inventory) == 3

    methods = {item.method for item in inventory}
    assert methods == {"GET", "POST", "DELETE"}
    assert all(item.path == "/resource" for item in inventory)


def test_duplicate_route_diagnostics_deterministic():
    """Verify that DuplicateRouteError formats conflicts deterministically regardless of insertion order."""
    conflict_dict = {
        ("POST", "/data"): ["beta_handler", "alpha_handler"],
        ("GET", "/alpha"): ["first", "second"],
    }
    err = DuplicateRouteError(conflict_dict)
    err_str = str(err)

    # In sorted order, GET /alpha must precede POST /data
    alpha_idx = err_str.index("GET /alpha")
    data_idx = err_str.index("POST /data")
    assert alpha_idx < data_idx

    # In sorted names, 'alpha_handler' must precede 'beta_handler'
    alpha_handler_idx = err_str.index("'alpha_handler'")
    beta_handler_idx = err_str.index("'beta_handler'")
    assert alpha_handler_idx < beta_handler_idx


# ---------------------------------------------------------------------------
# 8. Deterministic Ordering
# ---------------------------------------------------------------------------

def test_deterministic_route_inventory_ordering():
    """Verify that inventory is deterministically sorted by (path, method, name) across repeated calls."""
    run1 = get_route_inventory(live_app)
    run2 = get_route_inventory(live_app)
    run3 = get_route_inventory(live_app)

    assert run1 == run2 == run3

    # Verify sort invariant: path -> method -> name
    for i in range(len(run1) - 1):
        curr_key = (run1[i].path, run1[i].method, run1[i].name or "")
        next_key = (run1[i + 1].path, run1[i + 1].method, run1[i + 1].name or "")
        assert curr_key <= next_key, f"Sorting violation: {curr_key} > {next_key}"


# ---------------------------------------------------------------------------
# 9. Framework Safety & Unnamed Routes
# ---------------------------------------------------------------------------

def test_unnamed_routes_do_not_crash():
    """Verify that routes created without an explicit name do not cause attribute errors."""
    app_no_names = FastAPI()

    @app_no_names.get("/unnamed")
    def handler():
        return {}

    inventory = get_route_inventory(app_no_names)
    assert len(inventory) == 1
    assert inventory[0].path == "/unnamed"
    assert inventory[0].method == "GET"
    assert inventory[0].name in ["handler", None]


# ---------------------------------------------------------------------------
# 10. Fail-Closed Validation: Silent Omission Is Never Allowed
# ---------------------------------------------------------------------------

def test_validation_failure_raises_route_inventory_validation_error():
    """Verify that a route.matches() explosion for ALL routes raises RouteInventoryValidationError.

    The inspector must NEVER silently skip a documentable candidate when validation
    fails unexpectedly -- it must raise RouteInventoryValidationError so the caller
    is informed rather than receiving an incomplete inventory.
    """
    from app.core.route_inspector import _verify_route_registered_at_runtime
    from unittest.mock import MagicMock
    from types import SimpleNamespace

    # Build a minimal duck-typed app: only needs a .routes iterable.
    # Every route has path=None (skips direct check) but has matches() that raises.
    boom_route = MagicMock()
    boom_route.path = None  # not directly inspectable
    boom_route.matches = MagicMock(side_effect=RuntimeError("unexpected internal error"))

    fake_app = SimpleNamespace(routes=[boom_route])

    with pytest.raises(RouteInventoryValidationError) as exc_info:
        _verify_route_registered_at_runtime(fake_app, "GET", "/legit")

    err = exc_info.value
    assert err.method == "GET"
    assert err.path == "/legit"
    assert "runtime route.matches() verification" in err.stage
    assert isinstance(err.cause, RuntimeError)
    assert "Route inventory validation failed" in str(err)
    assert "GET /legit" in str(err)


def test_validation_error_class_attributes():
    """Verify RouteInventoryValidationError carries structured metadata and cause."""
    cause = ValueError("something broke")
    err = RouteInventoryValidationError(
        method="POST",
        path="/api/v1/test",
        stage="openapi cross-check",
        cause=cause,
    )
    assert err.method == "POST"
    assert err.path == "/api/v1/test"
    assert err.stage == "openapi cross-check"
    assert err.cause is cause
    assert "POST /api/v1/test" in str(err)
    assert "openapi cross-check" in str(err)
    assert "something broke" in str(err)


def test_validation_error_without_cause():
    """Verify RouteInventoryValidationError works correctly when cause is None."""
    err = RouteInventoryValidationError(
        method="GET",
        path="/health",
        stage="direct path inspection",
        cause=None,
    )
    assert err.cause is None
    assert "GET /health" in str(err)
    assert "direct path inspection" in str(err)
    # No trailing colon/cause fragment should appear
    assert str(err).endswith("[direct path inspection]")


def test_legitimate_policy_exclusions_never_raise():
    """Verify that intentionally excluded routes (docs, static, root) do not raise errors.

    Policy exclusions must be filtered cleanly without triggering validation errors.
    They are not 'missing' routes -- they are intentionally omitted by caller policy.
    """
    # All three exclusion types must complete without any exception
    inv1 = get_route_inventory(live_app, include_docs=False, include_static=False, include_root=False)
    inv2 = get_route_inventory(live_app, include_docs=True, include_static=True, include_root=True)
    inv3 = get_route_inventory(live_app, include_static=True, include_root=False)

    # include_docs=False: docs paths absent
    paths1 = {item.path for item in inv1}
    for doc_path in ["/docs", "/redoc", "/openapi.json"]:
        assert doc_path not in paths1
    # Root excluded
    assert "/" not in paths1

    # include_docs=True: docs paths present
    paths2 = {item.path for item in inv2}
    assert "/docs" in paths2 or "/openapi.json" in paths2

    # Static mounts present when requested
    mounts3 = {item.path for item in inv3 if item.method == "MOUNT"}
    assert len(mounts3) > 0  # /css and/or /js


def test_real_application_produces_complete_inventory_without_validation_errors():
    """Verify the current real application succeeds under the fail-closed implementation.

    The live application must return its expected complete route inventory without
    triggering RouteInventoryValidationError or UnregisteredRouteError.
    """
    # Must not raise
    inventory = get_route_inventory(live_app)

    route_map = {(item.method, item.path): item.name for item in inventory}

    expected = [
        ("GET", "/"),
        ("GET", "/health"),
        ("POST", "/api/v1/resumes/analyze-text"),
        ("POST", "/api/v1/resumes/extract"),
        ("POST", "/api/v1/resumes/feedback"),
        ("POST", "/api/v1/resumes/match"),
    ]
    for key in expected:
        assert key in route_map, f"Expected route {key} missing from inventory"

    # No duplicate (method, path) identities
    seen = set()
    for item in inventory:
        identity = (item.method, item.path)
        assert identity not in seen, f"Duplicate identity in inventory: {identity}"
        seen.add(identity)

    # Deterministic across repeated runs
    run2 = get_route_inventory(live_app)
    assert inventory == run2


# ---------------------------------------------------------------------------
# 11. OpenAPI Capability Detection: Fail-Closed Semantics
# ---------------------------------------------------------------------------

def test_no_openapi_capability_uses_direct_routes_without_error():
    """Verify that an app-like object with no callable openapi attribute uses direct
    route discovery without raising any error.

    This tests the capability-check path: the absence of openapi() is detected
    via callable() check, not via exception swallowing.
    """
    from types import SimpleNamespace

    # Direct route with fully public attributes
    direct_route = SimpleNamespace(
        path="/ping",
        methods={"GET"},
        name="ping_handler",
        endpoint=None,
    )

    # App with routes but NO openapi attribute at all
    fake_app = SimpleNamespace(routes=[direct_route])
    assert not hasattr(fake_app, "openapi")

    inventory = get_route_inventory(fake_app)

    assert len(inventory) == 1
    assert inventory[0].method == "GET"
    assert inventory[0].path == "/ping"
    assert inventory[0].name == "ping_handler"


def test_callable_openapi_raising_attribute_error_fails_explicitly():
    """Verify that a callable openapi() that raises AttributeError propagates as
    RouteInventoryValidationError and does NOT fall back silently.

    The old implementation swallowed AttributeError from app.openapi(), which could
    silently omit included-router routes if a schema-building step failed with
    AttributeError. This test pins that the new implementation fails explicitly.
    """
    from types import SimpleNamespace

    direct_route = SimpleNamespace(
        path="/direct",
        methods={"GET"},
        name="direct_handler",
        endpoint=None,
    )

    def bad_openapi_attr():
        raise AttributeError("schema attribute missing during generation")

    fake_app = SimpleNamespace(routes=[direct_route], openapi=bad_openapi_attr)

    with pytest.raises(RouteInventoryValidationError) as exc_info:
        get_route_inventory(fake_app)

    err = exc_info.value
    assert "openapi() schema generation" in err.stage
    assert isinstance(err.cause, AttributeError)
    assert "schema attribute missing" in str(err.cause)


def test_callable_openapi_raising_runtime_error_fails_explicitly():
    """Verify that a callable openapi() that raises RuntimeError (or any other
    unexpected exception) propagates as RouteInventoryValidationError.
    """
    from types import SimpleNamespace

    direct_route = SimpleNamespace(
        path="/direct",
        methods={"GET"},
        name="direct_handler",
        endpoint=None,
    )

    def bad_openapi_runtime():
        raise RuntimeError("schema serialisation failure")

    fake_app = SimpleNamespace(routes=[direct_route], openapi=bad_openapi_runtime)

    with pytest.raises(RouteInventoryValidationError) as exc_info:
        get_route_inventory(fake_app)

    err = exc_info.value
    assert "openapi() schema generation" in err.stage
    assert isinstance(err.cause, RuntimeError)
    assert "schema serialisation failure" in str(err.cause)


def test_openapi_failure_does_not_produce_partial_inventory():
    """Verify that when openapi() raises, no partial inventory is returned.

    A route discoverable only via the OpenAPI fallback (included router) must not
    silently disappear -- the whole call raises rather than returning a partial list.
    """
    from types import SimpleNamespace

    # A direct route that would be found without openapi
    direct_route = SimpleNamespace(
        path="/direct",
        methods={"GET"},
        name="direct_handler",
        endpoint=None,
    )

    call_count = {"n": 0}

    def failing_openapi():
        call_count["n"] += 1
        raise RuntimeError("openapi generation failed mid-way")

    fake_app = SimpleNamespace(routes=[direct_route], openapi=failing_openapi)

    # Must raise, not return a partial list containing only /direct
    with pytest.raises(RouteInventoryValidationError):
        get_route_inventory(fake_app)

    # openapi() was called exactly once (not retried or skipped)
    assert call_count["n"] == 1
