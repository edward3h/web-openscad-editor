
from generate import load_scad_recursively


def test_load_scad_recursively_with_binary_font(tmp_path):
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir()
    font_file = fonts_dir / "Underdog-Regular.ttf"
    font_file.write_bytes(bytes(range(256)))

    scad_file = tmp_path / "model.scad"
    scad_file.write_text('use <fonts/Underdog-Regular.ttf>\n')

    fs = {}
    load_scad_recursively(str(scad_file), str(tmp_path), fs)

    assert "/model.scad" in fs
    assert "/fonts/Underdog-Regular.ttf" in fs
