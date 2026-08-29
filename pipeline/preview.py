"""Open rendered carousel slides in the browser.

Pulled out of ``generate.py`` so ``pick_photos.py`` can show the post it has just
chosen photos for without shelling out to another command. The slide plan itself
still lives in the per-template builders; this only knows how to put finished
slides on screen.
"""

import os
import tempfile
import webbrowser

from pipeline.templates import render_template

# Slides are authored at 1080x1350. Halving them in the browser makes a whole
# carousel readable on a laptop without scrolling each slide.
PREVIEW_ZOOM = 'style="zoom: 0.5;"'


def slide_html(slides) -> list[str]:
    """Each slide as finished HTML, unscaled.

    The post flow reviews slides inline on its own page rather than opening a
    tab per slide, so it needs the markup rather than a file to open.
    """
    return [render_template(f"carousel/slide_{slide['type']}", slide)
            for slide in slides]


def open_slide_previews(slides, announce=True) -> list[str]:
    """Render each slide to a temp file and open it. Returns the paths."""
    paths = []
    for html in slide_html(slides):
        html = html.replace("<body>", f"<body {PREVIEW_ZOOM}>")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".html", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(html)
            paths.append(fh.name)
        if announce:
            print(f"Preview: {paths[-1]}")
        webbrowser.open("file:///" + paths[-1].replace(os.sep, "/"))
    return paths
