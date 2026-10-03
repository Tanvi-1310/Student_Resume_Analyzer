"""Canonical FastAPI route inventory and inspection service.

This module provides a framework-version-safe mechanism to extract, validate,
filter, and deterministically sort registered routes from a FastAPI application.
It relies exclusively on public, stable runtime attributes and the application's
public OpenAPI schema, completely eliminating dependencies on private framework internals.

Fail-closed semantics
----------------------
- If the application has no callable ``openapi`` attribute, direct-route discovery
  proceeds without OpenAPI. This is a capability check, not exception swallowing.
- If a callable ``openapi()`` exists and raises any exception during execution,
  a ``RouteInventoryValidationError`` is raised immediately. The inventory is never
  returned in a partial state.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field
from starlette.routing import Match


class RouteInventoryItem(BaseModel):
    """Canonical structured representation of a registered HTTP route."""

    model_config = ConfigDict(frozen=True)

    method: str = Field(..., description="Uppercase HTTP method (e.g., GET, POST)")
    path: str = Field(..., description="Exact final registered route path")
    name: Optional[str] = Field(default=None, description="Route name if available")
    source: Optional[str] = Field(default=None, description="Optional module or handler identifier")


class DuplicateRouteError(Exception):
    """Raised when duplicate (method, path) route registrations are detected."""

    def __init__(self, conflicts: Dict[Tuple[str, str], List[Optional[str]]]) -> None:
        self.conflicts = conflicts
        formatted = []
        for (method, path), names in sorted(conflicts.items()):
            names_str = ", ".join(repr(n) for n in sorted(names, key=lambda x: (x is None, x or "")))
            formatted.append(f"{method} {path} (conflicting names: {names_str})")
        msg = f"Duplicate route registration detected: {'; '.join(formatted)}"
        super().__init__(msg)


class UnregisteredRouteError(Exception):
    """Raised when an OpenAPI operation does not correspond to an active registered route."""


class RouteInventoryValidationError(Exception):
    """Raised when a documentable route candidate cannot be validated due to an unexpected error.

    This is a fail-closed condition: the inspector encountered an unexpected runtime
    error and cannot safely accept or exclude the candidate. The route is never
    silently omitted -- callers receive this error and must handle it explicitly.

    Attributes:
        method: HTTP method of the candidate being validated.
        path: Path of the candidate being validated.
        stage: Human-readable description of the validation stage that failed.
        cause: The underlying exception that triggered this error, if any.
    """

    def __init__(self, method: str, path: str, stage: str, cause: Optional[Exception] = None) -> None:
        self.method = method
        self.path = path
        self.stage = stage
        self.cause = cause
        cause_msg = f": {cause}" if cause is not None else ""
        super().__init__(
            f"Route inventory validation failed for '{method} {path}' "
            f"during [{stage}]{cause_msg}"
        )


# Framework-generated OpenAPI documentation paths (intentional policy exclusions)
FRAMEWORK_DOCS_PATHS: Set[str] = {
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
}

# Standard HTTP methods to document
HTTP_METHODS: Set[str] = {
    "GET",
    "POST",
    "PUT",
    "DELETE",
    "PATCH",
    "OPTIONS",
    "TRACE",
}


def _extract_source_identifier(endpoint: Any) -> Optional[str]:
    """Safely extract the module and function name of a route endpoint."""
    if endpoint is None:
        return None
    module = getattr(endpoint, "__module__", None)
    name = getattr(endpoint, "__name__", None) or getattr(endpoint, "__qualname__", None)
    if module and name:
        return f"{module}.{name}"
    if module:
        return module
    if name:
        return name
    return None


def _verify_route_registered_at_runtime(
    app: FastAPI, method: str, path: str
) -> None:
    """Verify that (method, path) corresponds to an active registered route.

    Uses public, stable runtime mechanisms only:
    1. Direct route object path inspection when route.path is available.
    2. Starlette's public BaseRoute.matches(scope) API.

    This function is fail-closed:
    - If no route matches: raises UnregisteredRouteError.
    - If every matchable route raises an unexpected exception: raises
      RouteInventoryValidationError rather than silently returning False.

    Raises:
        UnregisteredRouteError: If no matching runtime registration is found.
        RouteInventoryValidationError: If runtime verification raises unexpectedly.
    """
    # 1. Direct path equality check -- always safe, no exceptions possible
    for r in app.routes:
        if getattr(r, "path", None) == path:
            route_methods = getattr(r, "methods", None)
            if route_methods and method in {m.upper() for m in route_methods}:
                return  # Confirmed registered

    # 2. Public route matching via Starlette's BaseRoute.matches(scope)
    scope = {"type": "http", "method": method, "path": path}
    last_exc: Optional[Exception] = None
    any_callable = False

    for r in app.routes:
        if not (hasattr(r, "matches") and callable(r.matches)):
            continue
        any_callable = True
        try:
            match, _ = r.matches(scope)
            if match == Match.FULL:
                return  # Confirmed registered
        except Exception as exc:  # noqa: BLE001
            # Record the most recent unexpected error; do NOT silently continue.
            last_exc = exc

    # Fail-closed: if every route that supports matches() raised, we cannot
    # safely determine registration. Raise rather than silently returning False.
    if any_callable and last_exc is not None:
        raise RouteInventoryValidationError(
            method=method,
            path=path,
            stage="runtime route.matches() verification",
            cause=last_exc,
        )

    # No route matched cleanly; the OpenAPI operation has no runtime backing.
    raise UnregisteredRouteError(
        f"OpenAPI defines endpoint '{method} {path}' but it does not "
        f"correspond to an active registered route in the application runtime."
    )


def get_route_inventory(
    app: FastAPI,
    include_docs: bool = False,
    include_static: bool = False,
    include_root: bool = True,
) -> List[RouteInventoryItem]:
    """Derive a canonical, validated, deterministically ordered route inventory.

    Framework-Version-Safe Discovery Strategy
    ------------------------------------------
    1. Direct Public Route Object Inspection:
       Inspects public runtime routes in app.routes. Obtains final path, methods,
       name, and endpoint when directly available on route objects.
    2. Public OpenAPI Representation (capability-checked, fail-closed):
       Checks whether the app exposes a callable ``openapi`` attribute. If it does,
       invokes it and uses the returned ``paths`` dict to cover registered API
       operations in included routers whose top-level wrapper objects do not expose
       direct route attributes. If ``openapi()`` raises for any reason, propagates
       the failure as ``RouteInventoryValidationError`` -- never silently continues.
       If no callable ``openapi`` attribute exists, direct-route discovery proceeds
       alone (appropriate for bare Starlette apps without openapi() defined).
    3. Runtime Registration Cross-Check (fail-closed):
       Every OpenAPI-derived documentable endpoint is verified against the live route
       table using Starlette's public route.matches(scope) API.
       - A phantom endpoint raises UnregisteredRouteError.
       - An unexpected verification failure raises RouteInventoryValidationError.
       - A route is NEVER silently omitted due to a validation error.
    4. Safe Name and Source Fallback:
       Where a route name or source cannot be obtained through stable public APIs,
       it safely defaults to None rather than accessing private framework internals.
    5. Duplicate Detection:
       Detects duplicate (method, path) registrations, raising DuplicateRouteError.
    6. Deterministic Ordering:
       Sorts inventory items deterministically by (path, method, name).

    Intentional Policy Exclusions vs. Validation Failures
    -------------------------------------------------------
    Policy exclusions are routes intentionally filtered by caller configuration:
      - Framework OpenAPI docs (/openapi.json, /docs, /redoc, /docs/oauth2-redirect)
        excluded unless include_docs=True.
      - Static filesystem mounts (/css, /js) excluded unless include_static=True.
      - Frontend root (/) included by default; excludable via include_root=False.
    These are always filtered AFTER validation and never raise errors.

    Validation failures are unexpected errors while verifying a documentable candidate.
    These always raise RouteInventoryValidationError -- never silently dropped.

    Args:
        app: The initialized FastAPI application instance.
        include_docs: Whether to include framework documentation routes.
        include_static: Whether to include static filesystem mounts.
        include_root: Whether to include the user-facing landing route (/). Default True.

    Returns:
        A deterministically sorted list of RouteInventoryItem objects.

    Raises:
        DuplicateRouteError: If multiple route objects share the same (method, path).
        UnregisteredRouteError: If an OpenAPI operation has no active runtime backing.
        RouteInventoryValidationError: If openapi() raises during invocation, or if
            runtime verification raises unexpectedly (fail-closed: never silently skipped).
    """
    # Map from (method, path) -> list of names to detect duplicate registrations
    direct_registration_map: Dict[Tuple[str, str], List[Optional[str]]] = {}
    direct_routes_metadata: Dict[Tuple[str, str], Tuple[Optional[str], Optional[str]]] = {}
    static_mounts: List[Tuple[str, Optional[str], Optional[str]]] = []

    # Step 1: Inspect directly inspectable public route objects in app.routes
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        name = getattr(route, "name", None)
        endpoint = getattr(route, "endpoint", None)
        source = _extract_source_identifier(endpoint)

        if path is not None and methods:
            http_methods = {m.upper() for m in methods if m.upper() != "HEAD"}
            for method in http_methods:
                if method in HTTP_METHODS:
                    key = (method, path)
                    direct_registration_map.setdefault(key, []).append(name)
                    direct_routes_metadata[key] = (name, source)
        elif path is not None and not methods:
            # Mount or method-less route (e.g. StaticFiles)
            static_mounts.append((path, name, source))

    # Detect duplicate registrations from direct route objects
    duplicate_conflicts = {
        key: names for key, names in direct_registration_map.items() if len(names) > 1
    }
    if duplicate_conflicts:
        raise DuplicateRouteError(duplicate_conflicts)

    # Step 2: Use public OpenAPI representation for registered API routes.
    #
    # Fail-closed capability detection strategy:
    # 1. Check whether the app exposes a callable public 'openapi' attribute.
    #    - If it does not: the application has no OpenAPI capability (e.g. a bare
    #      Starlette app without openapi() defined). Proceed with direct-route
    #      discovery only. This is a capability check, not exception swallowing.
    # 2. If a callable openapi() exists, invoke it.
    #    - If invocation raises ANY exception, propagate it as a clear validation
    #      failure. Never silently continue with a partial inventory.
    openapi_routes: Dict[Tuple[str, str], Tuple[Optional[str], Optional[str]]] = {}
    openapi_fn = getattr(app, "openapi", None)
    if callable(openapi_fn):
        # openapi() capability confirmed. Any execution failure is an error.
        try:
            schema = openapi_fn()
        except (UnregisteredRouteError, RouteInventoryValidationError, DuplicateRouteError):
            raise
        except Exception as exc:
            raise RouteInventoryValidationError(
                method="*",
                path="*",
                stage="openapi() schema generation",
                cause=exc,
            ) from exc

        paths_dict = schema.get("paths", {})
        for path_key, path_item in paths_dict.items():
            if isinstance(path_item, dict):
                for method_key in path_item.keys():
                    method_upper = method_key.upper()
                    if method_upper not in HTTP_METHODS:
                        continue

                    # Policy exclusion: framework docs paths are valid, not errors.
                    # They are filtered later by include_docs; skip verification.
                    if path_key in FRAMEWORK_DOCS_PATHS:
                        openapi_routes[(method_upper, path_key)] = (None, None)
                        continue

                    # Fail-closed: raises UnregisteredRouteError or
                    # RouteInventoryValidationError -- never returns False silently.
                    _verify_route_registered_at_runtime(app, method_upper, path_key)

                    # Name and source default to None when derived via OpenAPI only
                    openapi_routes[(method_upper, path_key)] = (None, None)
    # else: no callable openapi() -- direct-route discovery is sufficient.

    # Step 3: Merge direct routes and OpenAPI routes.
    # Precedence: direct route metadata (richer name and source) takes precedence.
    merged_routes: Dict[Tuple[str, str], Tuple[Optional[str], Optional[str]]] = {}

    # Add all OpenAPI-derived routes first
    for key, (name, source) in openapi_routes.items():
        merged_routes[key] = (name, source)

    # Overlay direct routes (preserves rich metadata such as name and source)
    for key, (name, source) in direct_routes_metadata.items():
        merged_routes[key] = (name, source)

    # Step 4: Apply explicit policy filtering rules
    inventory: List[RouteInventoryItem] = []

    for (method, path), (name, source) in merged_routes.items():
        if not include_docs and path in FRAMEWORK_DOCS_PATHS:
            continue
        if not include_root and path == "/":
            continue
        inventory.append(
            RouteInventoryItem(
                method=method,
                path=path,
                name=name,
                source=source,
            )
        )

    # Add static mounts if requested
    if include_static:
        for path, name, source in static_mounts:
            inventory.append(
                RouteInventoryItem(
                    method="MOUNT",
                    path=path,
                    name=name,
                    source=source,
                )
            )

    # Step 5: Deterministic sort order: 1. path, 2. method, 3. name
    inventory.sort(key=lambda item: (item.path, item.method, item.name or ""))
    return inventory
