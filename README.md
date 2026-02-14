# web-openscad-editor

This repo contains a small generator that turns an OpenSCAD file into a self-contained web export (HTML + worker + OpenSCAD WASM). Try it out [here](https://web-openscad-editor.yawk.at/)!

Warning: Heavily vibe-coded.

## Use as a GitHub Action

Create a `web-openscad-editor.toml` file in your repository:

```toml
# Project metadata
[project]
name = "My OpenSCAD Project"
uri = "https://github.com/user/project"
export-filename-prefix = "my-project"
mode = "multi"  # "single" or "multi"

# Model files
[[model]]
file = "models/box.scad"
additional-params = ["params/box-extra.json"]

[[model]]
file = "models/cylinder.scad"
description-extra-html = "<p>A parametric cylinder.</p>"
```

Then use it in your workflow:

```yaml
name: Generate
on:
  workflow_dispatch:

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: yawkat/web-openscad-editor@v1
        with:
          config: web-openscad-editor.toml
      - uses: actions/upload-artifact@v4
        with:
          name: web-openscad-export
          path: out
```

## Configuration Reference

### TOML Configuration Schema

**Project metadata** (optional):
- `project.name`: Project name shown in the web interface
- `project.uri`: Project URI (link in the web interface)
- `project.export-filename-prefix`: Prefix for downloaded files
- `project.mode`: `"single"` or `"multi"` (default: `"single"`)
- `project.head-extra`: HTML injected at end of `<head>` tag (optional)

**OpenSCAD settings** (optional):
- `openscad.version`: OpenSCAD version to download (default: `"2026.01.19"`)
- `openscad.sha256-appimage`: SHA256 checksum of the OpenSCAD AppImage (optional)
- `openscad.sha256-wasm-web`: SHA256 checksum of the OpenSCAD WASM web zip (optional)
- `openscad.font-source`: `"auto"`, `"appimage"`, or `"system"` (default: `"auto"`)

**Model files** (required, array of tables):
Each `[[model]]` section defines one SCAD file:
- `file`: Path to SCAD file (required)
- `additional-params`: Array of parameter JSON files (optional)
- `description-extra-html`: Per-file HTML description (optional)

## Local usage

```bash
uv run python generate.py --config config.toml
```

### Output Modes

- `project.mode = "single"` (default): generates a single generator at `index.html`.
- `project.mode = "multi"`: generates one generator per model at `<file>.html` and an `index.html` that links to them. This also works with only one model file.

## Development

### Configuration Code Generation

The configuration classes are auto-generated from `config-schema.json` using Pydantic and datamodel-code-generator. Use `uv run datamodel-codegen` to regenerate them.

## License

While this repository is MIT-licensed, it bundles OpenSCAD binaries which are licensed under GPL. If you use this project, you must also follow the OpenSCAD terms.
