"""Tests for site_stats template and video rendering."""
import os

import pytest

from pipeline.templates import render_template, get_dummy_data


class TestSiteStatsTemplate:
    def setup_method(self):
        self.data = get_dummy_data("site_stats")
        self.html = render_template("site_stats", self.data)

    def test_returns_html_string(self):
        assert isinstance(self.html, str)
        assert "<html" in self.html

    def test_contains_stat_values_in_data_attributes(self):
        # Values are in data-target attributes; JS formats them at runtime
        assert 'data-target="359"' in self.html
        assert 'data-target="43515"' in self.html
        assert 'data-target="58"' in self.html

    def test_contains_stat_labels(self):
        html_upper = self.html.upper()
        assert "ATHLETES" in html_upper
        assert "SCORES" in html_upper
        assert "EVENTS" in html_upper

    def test_contains_site_title(self):
        assert "WINDSURF WORLD TOUR STATS" in self.html.upper()

    def test_contains_site_url(self):
        assert "windsurfworldtourstats.com" in self.html

    def test_contains_brand_fonts(self):
        assert "Bebas Neue" in self.html
        assert "Inter" in self.html

    def test_contains_animation_script(self):
        # The animated version needs JS for count-up
        assert "countUp" in self.html or "count-up" in self.html or "animate" in self.html


class TestSiteStatsDummyData:
    def test_has_required_fields(self):
        data = get_dummy_data("site_stats")
        for field in ("athletes_count", "scores_count", "events_count"):
            assert field in data, f"Missing field: {field}"

    def test_values_are_positive_integers(self):
        data = get_dummy_data("site_stats")
        for field in ("athletes_count", "scores_count", "events_count"):
            assert isinstance(data[field], int)
            assert data[field] > 0


class TestRenderToVideo:
    def test_creates_mp4_file(self, tmp_path):
        from pipeline.renderer import render_to_video

        data = get_dummy_data("site_stats")
        html = render_template("site_stats", data)
        output_path = str(tmp_path / "test_stats.mp4")

        result = render_to_video(
            html, output_path, width=1080, height=1350, dpr=1, duration_ms=3000
        )

        assert os.path.exists(result)
        assert result == output_path

    def test_output_has_reasonable_size(self, tmp_path):
        from pipeline.renderer import render_to_video

        data = get_dummy_data("site_stats")
        html = render_template("site_stats", data)
        output_path = str(tmp_path / "test_stats.mp4")

        render_to_video(
            html, output_path, width=1080, height=1350, dpr=1, duration_ms=3000
        )

        size = os.path.getsize(output_path)
        assert size > 10_000  # at least 10KB
