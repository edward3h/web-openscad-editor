# Agents

Mark any AI-generated commits with `Co-Authored-By`.

## Documentation

When a PR adds or changes a configuration option, the README.md must be updated as part of the same PR. Add a short example with an explanatory comment to the appropriate section under **Editor Configuration**, matching the style of the existing entries.

Do not document native OpenSCAD features (e.g. `use <fonts/...>`) in the README. The editor renders OpenSCAD files as-is, so built-in OpenSCAD functionality does not need separate documentation here.

## Tests

Do not modify `sys.path` in test files. The project uses `uv` with pytest, which already makes `src/` importable without path manipulation.
