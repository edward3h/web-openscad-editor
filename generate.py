import argparse
import os
import tempfile
import typing
import re
import subprocess
import json
import base64
import jinja2
import shutil
import hashlib
import functools


def run_openscad(*params: str):
    print("Running OpenSCAD:", *params)
    subprocess.run(["openscad"] + list(params), check=True)


ParamSet = typing.Sequence[typing.Mapping[str, typing.Any]]


class ScadContext:
    def __init__(self, file: str, additional_params: typing.Sequence[str] = (),
                 description_extra_html: typing.Optional[str] = None):
        self.file = file
        self.additional_params = additional_params
        self.description_extra_html = description_extra_html
        self.html_file = self.name() + ".html"
        self.link = self.html_file

    @functools.cache
    def load_own_params(self) -> ParamSet:
        with tempfile.NamedTemporaryFile(mode="r", suffix=".json", delete=False) as f:
            run_openscad("-o", f.name, "--export-format=param", self.file)
            return json.load(f)["parameters"]

    @functools.cache
    def load_additional_params(self) -> ParamSet:
        seq = []
        for path in self.additional_params:
            with open(path, "r", encoding="utf-8") as f:
                seq.extend(json.load(f)["parameters"])
        return seq

    @functools.cache
    def combined_params(self) -> ParamSet:
        combined = []

        def add(param, origin):
            param = dict(param)
            # if a parameter exists twice, drop the first one, but keep that default value.
            for i, existing in enumerate(combined):
                if existing["name"] == param["name"]:
                    combined.pop(i)
                    param["initial"] = existing["initial"]
                    break
            param["origin"] = origin
            combined.append(param)

        for p in self.load_own_params():
            add(p, "own")
        for p in self.load_additional_params():
            add(p, "additional")
        return combined

    def name(self):
        return os.path.basename(self.file).removesuffix(".scad")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scad",
        type=str,
        required=False,
        help="Input SCAD file",
    )
    parser.add_argument(
        "--scad-json",
        type=str,
        required=False,
        help=(
            "JSON array of objects: [{file: <scad>, additional-params: [<param.json>, ...], description-extra-html: <html>}, ...]. "
            "If prefixed with '@', the remainder is treated as a path to a JSON file."
        ),
    )
    parser.add_argument(
        "--additional-params",
        type=str,
        action="append",
        default=[],
        help=(
            "Additional param metadata JSON file(s) (same format as --export-format=param). "
            "Only supported when a single --scad input is used (use --scad-json for multi-input)."
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        required=False,
        default="out",
        help="Output directory (default: out)",
    )
    parser.add_argument(
        "--openscad-wasm",
        type=str,
        required=True,
        help="Path to OpenSCAD WebAssembly library",
    )
    parser.add_argument("--project-name", type=str, required=False, default=None)
    parser.add_argument("--project-uri", type=str, required=False, default=None)
    parser.add_argument(
        "--description-extra-html",
        type=str,
        required=False,
        default="",
        help=(
            "Optional additional HTML appended to the description paragraph (e.g. a docs link)."
        ),
    )
    parser.add_argument(
        "--export-filename-prefix", type=str, required=False, default=None
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["single", "multi"],
        required=False,
        default="single",
        help="Output mode: single (index.html) or multi (per-file HTML + index list)",
    )
    parser.add_argument(
        "--clean-urls",
        action="store_true",
        help="When linking to generated pages, omit the .html extension",
    )
    args = parser.parse_args()

    gh_repo = os.environ.get("GITHUB_REPOSITORY")
    gh_repo_name = gh_repo.split("/", 1)[1] if gh_repo and "/" in gh_repo else gh_repo
    gh_server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    gh_repo_uri = f"{gh_server_url}/{gh_repo}" if gh_repo else None

    if args.project_name is None:
        args.project_name = gh_repo_name or "PROJECT"
    if args.project_uri is None:
        args.project_uri = gh_repo_uri or "https://example.com/"
    if args.export_filename_prefix is None:
        args.export_filename_prefix = gh_repo_name or "openscad-export"

    contexts: typing.List[ScadContext] = []
    if args.scad_json:
        scad_json = args.scad_json
        if scad_json.startswith("@"):  # @path
            with open(scad_json[1:], "r", encoding="utf-8") as f:
                scad_json = f.read()
        for entry in json.loads(scad_json):
            contexts.append(ScadContext(file=entry["file"], additional_params=entry.get("additional-params", []),
                                        description_extra_html=entry.get("description-extra-html", None)))
    else:
        contexts.append(ScadContext(file=args.scad, additional_params=args.additional_params,
                                    description_extra_html=args.description_extra_html))

    scad_root = os.path.commonpath([os.path.dirname(p.file) for p in contexts])

    fs: typing.Dict[str, bytes] = {}
    for context in contexts:
        load_scad_recursively(context.file, scad_root, fs)
        context.relative = host_path_to_virtual(scad_root, context.file)
        if args.clean_urls:
            context.link = context.link.removesuffix(".html")

    # Bundle a minimal fontconfig setup and a small font set.
    # The OpenSCAD WASM build does not include a system-wide fontconfig config,
    # so without this, text() rendering emits:
    #   Fontconfig error: Cannot load default config file
    # and then falls back to missing fonts.
    try:
        add_default_fonts(fs)
    except Exception as e:
        print(f"Warning: failed to bundle fonts: {e}")
    try:
        os.makedirs(args.output)
    except FileExistsError:
        pass
    j2env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + "/src"),
        undefined=jinja2.StrictUndefined
    )
    j2env.filters["json_dump"] = json.dumps
    variables_base: typing.Dict[str, typing.Any] = {
        "fs": {k: base64.b64encode(v).decode("ascii") for k, v in fs.items()},
        "args": args,
        "contexts": contexts,
    }

    worker_source = j2env.get_template("worker.js.jinja2").render(**variables_base)
    worker_hash = hashlib.sha256(worker_source.encode("utf-8")).hexdigest()[:12]
    worker_script_name = f"worker.{worker_hash}.js"
    variables_base["worker_script_name"] = worker_script_name

    with open(os.path.join(args.output, worker_script_name), "w") as f:
        f.write(worker_source)

    if args.mode == "single":
        if len(contexts) != 1:
            raise SystemExit("--mode=single requires exactly one --scad input (use --mode=multi instead)")

        contexts[0].html_file = "index.html"
    else:
        with open(os.path.join(args.output, "index.html"), "w") as f:
            f.write(j2env.get_template("multi_index.html.jinja2").render(**variables_base))

    for ctx in contexts:
        with open(os.path.join(args.output, ctx.html_file), "w") as f:
            f.write(j2env.get_template("index.html.jinja2").render(
                ctx=ctx,
                **variables_base
            ))

    try:
        shutil.rmtree(args.output + "/openscad-wasm")
    except FileNotFoundError:
        pass
    shutil.copytree(args.openscad_wasm, args.output + "/openscad-wasm")


pattern_include = re.compile(r"^\s*(?:include|use)\s+<(.+)>\s*$")


def host_path_to_virtual(root: str, host_path: str) -> str:
    rel = os.path.relpath(host_path, root)
    rel = rel.replace(os.sep, "/")
    if rel == ".":
        rel = os.path.basename(host_path)
    return "/" + rel.lstrip("./")


def load_scad_recursively(host_path: str, root: str, fs: typing.Dict[str, bytes]):
    virtual_path = host_path_to_virtual(root, host_path)
    if virtual_path in fs:
        return
    print(f"Including {virtual_path}")
    with open(host_path, "rb") as f:
        binary = f.read()
    fs[virtual_path] = binary
    text = binary.decode("utf-8")
    for line in text.splitlines():
        include = pattern_include.match(line)
        if include:
            load_scad_recursively(
                os.path.normpath(
                    os.path.join(os.path.dirname(host_path), include.group(1))
                ),
                root,
                fs,
            )


def add_default_fonts(fs: typing.Dict[str, bytes]):
    # Provide a minimal fontconfig config file.
    # This is intentionally tiny (the heavy lifting is the font files).
    if "/fonts/fonts.conf" not in fs:
        fs["/fonts/fonts.conf"] = (
            b'<?xml version="1.0" encoding="UTF-8"?>\n'
            b'<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">\n'
            b"<fontconfig>\n"
            b"  <dir>/fonts</dir>\n"
            b"  <cachedir>/tmp/fontconfig</cachedir>\n"
            b"</fontconfig>\n"
        )

    font_source = (os.environ.get("OPENSCAD_FONT_SOURCE") or "auto").strip().lower()
    if font_source not in {"auto", "appimage", "system"}:
        font_source = "auto"

    # Default behavior:
    # - GitHub Action/CI: use the AppImage bundled with the action.
    # - Local runs: you can set OPENSCAD_FONT_SOURCE=system to embed
    #   fonts from /usr/share/fonts (Arch Linux paths).
    if font_source in {"auto", "appimage"}:
        try:
            add_fonts_from_appimage(fs)
            return
        except Exception:
            if font_source == "appimage":
                raise

    add_fonts_from_system(fs)


def _collect_font_candidates(root: str) -> typing.List[str]:
    out: typing.List[str] = []
    if not os.path.isdir(root):
        return out
    for base, _, files in os.walk(root):
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext in [".ttf", ".otf", ".ttc"]:
                out.append(os.path.join(base, fn))
    return out


def _pick_common_fonts(candidates: typing.List[str]) -> typing.List[str]:
    # Prefer common families. On Arch, these typically come from packages like:
    # - ttf-dejavu
    # - ttf-liberation
    # - noto-fonts
    preferred_basenames = [
        "LiberationSans-Regular.ttf",
        "LiberationSans-Bold.ttf",
        "LiberationSans-Italic.ttf",
        "LiberationSans-BoldItalic.ttf",
        "LiberationSerif-Regular.ttf",
        "LiberationSerif-Bold.ttf",
        "LiberationMono-Regular.ttf",
        "LiberationMono-Bold.ttf",
        "DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf",
        "DejaVuSans-Oblique.ttf",
        "DejaVuSans-BoldOblique.ttf",
        "DejaVuSerif.ttf",
        "DejaVuSerif-Bold.ttf",
        "DejaVuSansMono.ttf",
        "DejaVuSansMono-Bold.ttf",
    ]

    by_base: typing.Dict[str, str] = {}
    for p in candidates:
        by_base.setdefault(os.path.basename(p), p)

    ordered: typing.List[str] = []
    for base in preferred_basenames:
        p = by_base.get(base)
        if p:
            ordered.append(p)

    if not ordered:
        ordered = sorted(candidates)[:16]
    return ordered[:32]


def _write_fonts_into_fs(fs: typing.Dict[str, bytes], paths: typing.List[str]):
    used_names: typing.Set[str] = set()
    for p in paths:
        name = os.path.basename(p)
        if name in used_names:
            stem, ext = os.path.splitext(name)
            i = 2
            while f"{stem}-{i}{ext}" in used_names:
                i += 1
            name = f"{stem}-{i}{ext}"
        used_names.add(name)
        with open(p, "rb") as f:
            fs["/fonts/" + name] = f.read()


def add_fonts_from_system(fs: typing.Dict[str, bytes]):
    # Arch Linux system font locations.
    candidates: typing.List[str] = []
    for root in [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.local/share/fonts"),
    ]:
        candidates.extend(_collect_font_candidates(root))
    if not candidates:
        raise RuntimeError("No system fonts found (checked /usr/share/fonts etc.)")
    _write_fonts_into_fs(fs, _pick_common_fonts(candidates))


def add_fonts_from_appimage(fs: typing.Dict[str, bytes]):
    appimage_path = os.environ.get("OPENSCAD_APPIMAGE")
    if not appimage_path:
        version = (
                os.environ.get("OPENSCAD_VERSION")
                or os.environ.get("openscad-version")
                or "2026.01.19"
        )
        appimage_path = os.path.join(
            os.getcwd(),
            ".openscad-cache",
            f"OpenSCAD-{version}-x86_64.AppImage",
        )
    if not os.path.exists(appimage_path):
        raise FileNotFoundError(
            f"OpenSCAD AppImage not found at {appimage_path}. Set OPENSCAD_APPIMAGE to override."
        )

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [appimage_path, "--appimage-extract"],
            check=True,
            cwd=tmp,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        squashfs_root = os.path.join(tmp, "squashfs-root")
        if not os.path.isdir(squashfs_root):
            raise RuntimeError("Failed to extract AppImage (missing squashfs-root)")

        candidates: typing.List[str] = []
        for base in [
            os.path.join(squashfs_root, "usr", "share", "fonts"),
            os.path.join(squashfs_root, "usr", "local", "share", "fonts"),
            os.path.join(squashfs_root, "usr", "lib", "fonts"),
        ]:
            candidates.extend(_collect_font_candidates(base))
        if not candidates:
            raise RuntimeError("No fonts found in extracted AppImage")
        _write_fonts_into_fs(fs, _pick_common_fonts(candidates))


if __name__ == "__main__":
    main()
