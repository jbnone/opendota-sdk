"""Generate API reference pages from opendota_sdk's public exports.

Run this before `zensical build` / `zensical serve` (both the CI docs job and local
`uv run python docs/gen_ref_pages.py` do this) -- it is a plain pre-build step, not a
plugin. Zensical does not support the mkdocs-gen-files plugin (its usual home for this
kind of generation), so this writes real files straight to docs/api/ instead of going
through that plugin's virtual filesystem. That was confirmed against a live Zensical
build, not assumed: mkdocs-gen-files 0.6.1 and mkdocs-literate-nav 0.6.3 (2026-03-16)
added a dependency on a new package, "properdocs", that prints an urgent-sounding
warning urging a switch away from mkdocs at build time -- real news (MkDocs 1.x is
largely unmaintained, oprypin forked it as ProperDocs, Material for MkDocs' own team
moved on to Zensical), but not something to depend on unreviewed. Not depending on
either package at all -- this script replaces what mkdocs-gen-files did, and Zensical
reimplements mkdocs-literate-nav's SUMMARY.md convention natively -- sidesteps the
question entirely rather than just pinning around it.

Pages are built from `opendota_sdk.__all__` rather than by walking source files, so the
reference always matches the SDK's actual public surface (AGENTS.md §3.5) regardless of
which internal module a given symbol happens to be defined in -- `OpenDotaClientConfig`
and the error types live in underscore-prefixed modules (`_config.py`, `_errors.py`) but
are public API and must be documented like everything else re-exported from the package.
"""

from pathlib import Path

import opendota_sdk

# Maps a symbol's defining module (opendota_sdk.<key>) to the reference page it belongs
# on. Order here is the order pages appear in the generated nav.
PAGES: dict[str, tuple[str, str]] = {
    "client": ("client", "Client"),
    "_config": ("configuration", "Configuration"),
    "models": ("models", "Models"),
    "enums": ("enums", "Enums"),
    "_errors": ("errors", "Errors"),
}

groups: dict[str, list[str]] = {key: [] for key in PAGES}
for name in opendota_sdk.__all__:
    obj = getattr(opendota_sdk, name)
    module = getattr(obj, "__module__", "")
    key = module.removeprefix("opendota_sdk.")
    if key not in groups:
        raise RuntimeError(
            f"opendota_sdk.{name} is defined in {module!r}, which has no reference page "
            "mapping in docs/gen_ref_pages.py -- add one so it doesn't go undocumented."
        )
    groups[key].append(name)

api_dir = Path(__file__).parent / "api"
api_dir.mkdir(parents=True, exist_ok=True)
for existing in api_dir.glob("*.md"):
    existing.unlink()

nav_lines: list[str] = []
for key, (slug, title) in PAGES.items():
    names = groups[key]
    if not names:
        continue

    body = f"# {title}\n\n" + "".join(
        f"::: opendota_sdk.{name}\n\n" for name in sorted(names)
    )
    (api_dir / f"{slug}.md").write_text(body)
    nav_lines.append(f"- [{title}]({slug}.md)\n")

(api_dir / "SUMMARY.md").write_text("".join(nav_lines))
