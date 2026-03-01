# web-openscad-editor

## Project purpose

Generator that transforms OpenSCAD files into self-contained web exports (HTML + JS worker + OpenSCAD WASM). Creates browser-based 3D model editors with parametric customisation. Also published as a GitHub Action.

## Commands

```bash
uv sync --frozen           # install dependencies
uv run pytest              # run all tests
uv run python src/generate.py --config editor.toml  # run generator locally
uv run datamodel-codegen   # regenerate src/config_generated.py from config-schema.json
```

## Architecture

Three-layer system:

1. **Config/models** — `config-schema.json` defines the TOML config schema; `src/config_generated.py` is auto-generated from it via `datamodel-codegen`; `src/model.py` provides the Jinja2 template context objects.
2. **Generator pipeline** — `src/generate.py` reads the TOML config, downloads binaries (OpenSCAD AppImage, WASM), runs OpenSCAD to extract parameters, and renders Jinja2 templates to `out/`.
3. **Frontend templates** — `src/index.html.jinja2` and `src/worker.js.jinja2` are the browser-side UI; the worker JS is embedded inline in the generated HTML.

### Critical file relationships

- `config-schema.json` → *(datamodel-codegen)* → `src/config_generated.py`
- `editor.toml` → `src/generate.py` → `out/` directory
- `src/worker.js.jinja2` is embedded into the output of `src/index.html.jinja2`

## Key conventions

- **Auto-generated file**: never manually edit `src/config_generated.py`; edit `config-schema.json` and regenerate instead.
- **Template inheritance**: Jinja2 templates use a base/child pattern; check existing templates before adding new blocks.
- **Parameter metadata**: OpenSCAD parameter descriptions and grouping are driven by JSON sidecar files (`additional-params`) merged with the SCAD file's own parameter comments.
- **Output is self-contained**: the generated `out/` HTML must work without any external network requests (all assets inlined).
