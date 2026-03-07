"""Playwright-based HTML to PNG/video renderer."""
import os
import shutil
import tempfile

from playwright.sync_api import sync_playwright


def render_to_png(
    html: str,
    output_path: str,
    width: int = 1080,
    height: int = 1350,
    dpr: int = 2,
) -> str:
    """Render HTML string to PNG using headless Chromium via Playwright."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Write HTML to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html)
        temp_path = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(
                viewport={"width": width, "height": height},
                device_scale_factor=dpr,
            )

            page.goto(f"file:///{temp_path.replace(os.sep, '/')}")

            # Wait for fonts to load
            page.evaluate("() => document.fonts.ready")

            page.screenshot(path=output_path, full_page=False)
            browser.close()
    finally:
        os.unlink(temp_path)

    return output_path


def render_to_video(
    html: str,
    output_path: str,
    width: int = 1080,
    height: int = 1350,
    dpr: int = 1,
    duration_ms: int = 6000,
) -> str:
    """Render animated HTML to video using Playwright's video recording."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html)
        temp_html = f.name

    video_dir = tempfile.mkdtemp()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(
                viewport={"width": width, "height": height},
                device_scale_factor=dpr,
                record_video_dir=video_dir,
                record_video_size={"width": width * dpr, "height": height * dpr},
            )
            page = context.new_page()
            page.goto(f"file:///{temp_html.replace(os.sep, '/')}")

            # Wait for fonts then let animation play
            page.evaluate("() => document.fonts.ready")
            page.wait_for_timeout(duration_ms)

            # Close context to finalize video
            page.close()
            context.close()
            browser.close()

        # Find the recorded video and move to output path
        videos = [f for f in os.listdir(video_dir) if f.endswith(".webm")]
        if not videos:
            raise RuntimeError("Playwright did not produce a video file")

        recorded = os.path.join(video_dir, videos[0])
        # Convert webm to mp4 if ffmpeg available, otherwise copy as-is
        if output_path.endswith(".mp4") and shutil.which("ffmpeg"):
            import subprocess
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", recorded,
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart",
                    output_path,
                ],
                capture_output=True,
                check=True,
            )
        else:
            # Fallback: save as webm or copy raw
            if output_path.endswith(".mp4"):
                output_path = output_path.rsplit(".", 1)[0] + ".webm"
            shutil.copy2(recorded, output_path)
    finally:
        os.unlink(temp_html)
        shutil.rmtree(video_dir, ignore_errors=True)

    return output_path
