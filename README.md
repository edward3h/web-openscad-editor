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
- `umami-track-render`: List of model parameter names to track when model is rendered (optional, default: `null`)
- `umami-track-export`: List of model parameter names to track when model is exported/downloaded as STL (optional, default: `null`)

### Umami Analytics Tracking

You can track user interactions with your OpenSCAD models using [Umami](https://umami.is) analytics. First, include the Umami script in your project configuration:

```toml
[project]
head-extra = '<script defer src="https://your-umami-instance.com/script.js" data-website-id="your-website-id"></script>'
```

Then configure which model parameters to track for each model:

```toml
[[model]]
file = "models/box.scad"
# Track render events with specific parameters
umami-track-render = ["width", "height", "depth"]
# Track export events with different parameters
umami-track-export = ["width", "height", "depth", "material"]
```

**Tracking behavior:**
- `null` (default): No tracking for this event
- `[]` (empty array): Track the event with no parameter data
- `["param1", "param2"]`: Track the event with the current values of specified parameters

When configured, the following events are tracked:
- `"render"`: Triggered when the model is successfully rendered in the 3D viewer
- `"export-stl"`: Triggered when the user downloads the STL file

The event data will include the current values of the specified model parameters, allowing you to understand which parameter combinations are most popular with your users.


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
