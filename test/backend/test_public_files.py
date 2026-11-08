"""Modules use each other only through their public files.

import-linter (uv run lint-imports) checks which module may import which.
This checks which file: a module may import another module's interface.py,
queries.py or types.py, and only app/registry.py may import a plugin.py.
See BackendArchitecture.md.
"""

from collections.abc import Iterable, Mapping

import grimp

PUBLIC_FILES = ("interface", "queries", "types")


def _owner(name: str) -> str | None:
    """The module a file belongs to: "wallet" for app.wallet.service."""
    parts = name.split(".")
    return parts[1] if len(parts) > 1 else None


def violations(
    modules: Iterable[str], imports: Mapping[str, Iterable[str]]
) -> list[str]:
    """Every import that breaks the rules, as "importer imports imported".

    modules is every Python module under app, and imports maps each one to
    the modules it imports directly. A module is a folder in app with a
    plugin.py, so app/core and app/scripts are not modules.
    """
    feature_modules = {
        _owner(name) for name in modules if name.endswith(".plugin")
    }
    found = []
    for importer in sorted(imports):
        for imported in sorted(imports[importer]):
            module = _owner(imported)
            if module not in feature_modules or _owner(importer) == module:
                continue
            if imported == f"app.{module}.plugin":
                allowed = importer == "app.registry"
            else:
                # The bare package is allowed too: "from app.wallet import
                # interface" can show up as an import of app.wallet.
                allowed = imported == f"app.{module}" or imported in {
                    f"app.{module}.{file}" for file in PUBLIC_FILES
                }
            if not allowed:
                found.append(f"{importer} imports {imported}")
    return found


def test_the_app_follows_the_public_file_rules() -> None:
    graph = grimp.build_graph("app")
    imports = {
        name: graph.find_modules_directly_imported_by(name)
        for name in graph.modules
    }

    assert violations(graph.modules, imports) == []


# The tests below check the rules themselves on made-up modules, so they
# work before trading exists.
MODULES = {
    "app.registry",
    "app.core.db",
    "app.scripts.seed_demo",
    "app.wallet.plugin",
    "app.wallet.interface",
    "app.wallet.queries",
    "app.wallet.types",
    "app.wallet.service",
    "app.wallet.routes",
    "app.trading.plugin",
    "app.trading.routes",
}


def test_public_files_and_a_modules_own_files_are_allowed() -> None:
    imports = {
        "app.trading.routes": {
            "app.wallet.interface",
            "app.wallet.queries",
            "app.wallet.types",
            "app.core.db",
        },
        "app.wallet.routes": {"app.wallet.service"},
        "app.registry": {"app.wallet.plugin", "app.trading.plugin"},
        "app.scripts.seed_demo": {"app.wallet.interface"},
    }

    assert violations(MODULES, imports) == []


def test_importing_another_modules_private_file_is_caught() -> None:
    imports = {"app.trading.routes": {"app.wallet.service"}}

    assert violations(MODULES, imports) == [
        "app.trading.routes imports app.wallet.service"
    ]


def test_importing_a_plugin_outside_the_registry_is_caught() -> None:
    imports = {"app.scripts.seed_demo": {"app.wallet.plugin"}}

    assert violations(MODULES, imports) == [
        "app.scripts.seed_demo imports app.wallet.plugin"
    ]