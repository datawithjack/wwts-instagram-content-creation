"""Publish the Finn Mellon 'Rider of the Day' carousel (Fiji 2026) to Instagram.

Reuses the exact DB-backed `data` built by preview_rod_finn.py, renders the
4 slides to PNG at 2x DPR, then publishes via the standard carousel flow.
Throwaway harness — mirrors the preview the user approved.
"""
import sys

from preview_rod_finn import data
from pipeline.renderer import render_rp_carousel
from pipeline.publisher import publish_carousel

CAPTION = (
    "\U0001f30a Windsurf World Tour Stats Rider of the Day is Finn Mellon \U0001f1ee\U0001f1ea\n\n"
    "Irish charger who started yesterday in Round 1 of the Challengers has made "
    "it through to the Quarter Final!\n\n"
    "Good luck tomorrow Finn! \U0001f919\n\n"
    "Full stats → windsurfworldtourstats.com\n\n"
    "#windsurfing #fiji #cloudbreak #waveriding #pwaworldtour #iwt #windsurfworldtourstats"
)

paths = render_rp_carousel(data, "output/png", base_name="rod_finn_fiji2026")
print("Rendered slides:")
for p in paths:
    print(" ", p)

if "--render-only" in sys.argv:
    print("Render-only: skipping publish.")
    sys.exit(0)

print("\nPublishing carousel to Instagram...")
result = publish_carousel(paths, CAPTION)
print(f"Published! Media ID: {result.get('media_id')}")
