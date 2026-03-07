"""Tests for Playwright renderer."""
import os
import pytest

from pipeline.renderer import render_to_png
from pipeline.templates import render_template, get_dummy_data


@pytest.fixture
def output_dir(tmp_path):
    return str(tmp_path)


class TestRenderToPng:
    def test_creates_png_file(self, output_dir):
        data = get_dummy_data("head_to_head")
        html = render_template("head_to_head", data)
        output_path = os.path.join(output_dir, "test_h2h.png")

        result = render_to_png(html, output_path, width=1080, height=1350, dpr=2)

        assert os.path.exists(result)
        assert result == output_path

    def test_output_is_valid_png(self, output_dir):
        data = get_dummy_data("head_to_head")
        html = render_template("head_to_head", data)
        output_path = os.path.join(output_dir, "test_h2h.png")

        render_to_png(html, output_path, width=1080, height=1350, dpr=2)

        with open(output_path, "rb") as f:
            header = f.read(8)
        # PNG magic bytes
        assert header[:4] == b"\x89PNG"

    def test_output_has_reasonable_size(self, output_dir):
        data = get_dummy_data("head_to_head")
        html = render_template("head_to_head", data)
        output_path = os.path.join(output_dir, "test_h2h.png")

        render_to_png(html, output_path, width=1080, height=1350, dpr=2)

        size = os.path.getsize(output_path)
        assert size > 10_000  # at least 10KB for a real render
