"""Cut the profile-claim reels (#26 pro, #27 coach): cards intercut with live footage.

    pro:    HOOK -> FANTASY -> WHO COUNTS -> CLAIM -> [profile, claim form] -> JOIN -> [Pros board]
            -> WHY -> BONUS -> CTA
    coach:  HOOK -> FANTASY -> WHO COUNTS -> GET LISTED -> [profile, listing form] -> CHECK OUT
            -> [Coaches board] -> WHY -> COMING SOON -> CTA
    podium: HOOK -> [Sylt wave podium picked] -> BONUS -> [Heat Team step, blurred
            under 'continue as normal'] -> CTA
            (#29, short on purpose)

Footage comes from pipeline/screen_record_claim.py. The pro reel is one take; the coach
reel is two (board signed out, form signed in), so each footage slot names the take it
is cut from. A missing take drops its slots rather than failing the build.

Card copy lives here rather than in a content module: it is static, and there is no
data to fetch.

Usage:
    python -m pipeline.claim_reel_edit --reel pro
    python -m pipeline.claim_reel_edit --reel coach
    python -m pipeline.claim_reel_edit --reel podium
"""
import argparse
import json
import os
import shutil
import subprocess
import tempfile

from pipeline.reel_edit import DEFAULT_H, DEFAULT_W, concat_clips_cmd, trim_clip_cmd
from pipeline.rtf_reel_edit import _with_quality

URL = "windsurfworldtourstats.com"
HANDLE = "@windsurfworldtourstats"

# screen id -> card copy. `title` breaks on \n. No em dashes in any of it.
CARDS = {
    "pro_hook": {
        "eyebrow": "Windsurf Fantasy League",
        "title": "ARE YOU A\nPRO RIDER?",
    },
    # No headline: the question IS the card.
    "fantasy": {
        "lead": "Do you play (or want to play) Windsurf Fantasy League?",
    },
    "pro_who": {
        "lead": "Have you competed at a PWA event, or at a recent 4 or 5-star PWA "
                "or WWT event?",
    },
    "pro_claim": {"eyebrow": "Step 1", "title": "SIGN UP AND\nCLAIM YOUR\nPROFILE"},
    "pro_join": {"eyebrow": "Once approved", "title": "CHECK OUT THE\nLEADERBOARD"},
    "pro_why": {
        "eyebrow": "Why",
        "points": [
            "Bragging rights among your peers.",
            "A verified badge next to your name.",
            "Your socials show on the leaderboard.",
            "Weekend warriors get to play against their heroes.",
        ],
    },
    # The bonus sits on its own card: it is an offer, not another reason.
    "pro_bonus": {
        "eyebrow": "Bonus",
        "title": "FREE END OF\nSEASON REPORT",
        "title_px": 150,  # two lines: at the default 200 "SEASON REPORT" wraps
        "sub": "Every claimed pro gets a full breakdown: results, heats, rankings, "
               "moves, and video links where we have them.",
    },
    "pro_cta": {
        "eyebrow": "Claim your profile",
        "title": "PLAY THE PROS",
        "title_px": 165,  # one line: at the default 200 it wraps
        "sub": "Open your profile and click \"Claim your athlete profile\"",
        "cta": True,
    },
    "coach_hook": {
        "eyebrow": "Windsurf Fantasy League",
        "title": "ARE YOU A\nCOACH?",
    },
    "coach_who": {
        "lead": "Do you run clinics, camps or lessons?",
    },
    "coach_claim": {"eyebrow": "Step 1", "title": "GET\nLISTED"},
    "coach_join": {"eyebrow": "Once approved", "title": "CHECK OUT THE\nLEADERBOARD"},
    "coach_why": {
        "eyebrow": "Why",
        "points": [
            "Your own spot on the Coaches board.",
            "A link to your site or socials.",
            "Players find you right after watching the comp.",
            "Free, and it stays free.",
        ],
    },
    # The coach reel's answer to pro_bonus: what listing is worth by next season.
    "coach_soon": {
        "eyebrow": "Coming next season",
        "title": "COACH BRANDED\nPRIVATE LEAGUES",
        "title_px": 130,
        "sub": "With a notice board for your clinic dates, messages and anything "
               "else your riders should see.",
    },
    "coach_cta": {
        "eyebrow": "Get listed",
        "title": "GET FOUND",
        "sub": "Open your profile and click \"Get listed on the Coaches board\"",
        "cta": True,
    },
    # Predict the podium (#29). Points from the app's utils/rankedPodiumScale.ts.
    "podium_hook": {
        "eyebrow": "New in Session mode",
        "title": "CALL THE\nPODIUM",
    },
    # Medal colours are the app's (utils/podiumMedal.ts: captain-400, slate-300, bronze-600).
    "podium_points": {
        "eyebrow": "Podium bonus",
        "title": "CALL IT RIGHT",
        "title_px": 170,
        "points_centered": True,
        "points": [
            {"n": "1ST", "text": "correct: +25 pts", "color": "#facc15"},
            {"n": "2ND", "text": "correct: +15 pts", "color": "#cbd5e1"},
            {"n": "3RD", "text": "correct: +10 pts", "color": "#cd7f32"},
        ],
        "sub": "Right rider, wrong spot: +5 pts",
    },
    "podium_cta": {
        "eyebrow": "Sylt wave",
        "title": "START BUILDING\nYOUR TEAM",
        "title_px": 150,
        "cta": True,
    },
}

CARD_HOLD_MS = {"pro_who": 3200, "pro_why": 5200, "pro_bonus": 3800,
                "coach_soon": 3800, "coach_why": 5200,
                "podium_hook": 1200,
                # The three lines land 0.9s apart before the sub, so it needs the room.
                "podium_points": 4400,
                "podium_cta": 2000}
DEFAULT_HOLD_MS = 2600
# Dead frames at the head of every card recording, measured: text lands at 0.8s.
CARD_HEAD_S = 0.6

# ("card", screen) or ("footage", take, segment).
SPINES = {
    "pro": [
        ("card", "pro_hook"),
        ("card", "fantasy"),
        ("card", "pro_who"),
        ("card", "pro_claim"),
        ("footage", "pro", "profile"),
        ("card", "pro_join"),
        ("footage", "pro", "board"),
        ("card", "pro_why"),
        ("card", "pro_bonus"),
        ("card", "pro_cta"),
    ],
    "coach": [
        ("card", "coach_hook"),
        ("card", "fantasy"),
        ("card", "coach_who"),
        ("card", "coach_claim"),
        ("footage", "coach-form", "profile"),
        ("card", "coach_join"),
        ("footage", "coach-board", "board"),
        ("card", "coach_why"),
        ("card", "coach_soon"),
        ("card", "coach_cta"),
    ],
    "podium": [
        ("card", "podium_hook"),
        ("footage", "podium", "podium"),
        ("card", "podium_points"),
        ("footage", "podium", "heat"),
        ("card", "podium_cta"),
    ],
}

FOOTAGE_SPEED = {"board": 1.25, "form": 1.0, "profile": 1.25, "podium": 2.0,
                 "heat": 1.0}


def plan_reel(reel: str, markers_by_take: dict) -> list:
    """Resolve a spine into clips, dropping footage whose take or markers are missing.

    Returns ("card", screen) and ("footage", take, start, end) tuples in order.
    """
    plan = []
    for item in SPINES[reel]:
        if item[0] == "card":
            plan.append(item)
            continue
        _, take, seg = item
        markers = markers_by_take.get(take) or {}
        start, end = markers.get(f"{seg}_start"), markers.get(f"{seg}_end")
        if start is not None and end is not None:
            plan.append(("footage", take, start, end, seg))
    return plan


def _render_card_clip(screen: str, out_path: str) -> str:
    from pipeline.renderer import render_to_video
    from pipeline.templates import render_template

    hold = CARD_HOLD_MS.get(screen, DEFAULT_HOLD_MS)
    html = render_template("claim_reel", {
        "card": CARDS[screen], "handle": HANDLE, "url": URL,
        "width": DEFAULT_W, "height": DEFAULT_H, "hold_ms": hold,
    })
    raw = out_path + ".raw.mp4"
    total_s = (hold + 1600) / 1000
    render_to_video(html, raw, width=DEFAULT_W, height=DEFAULT_H, dpr=1,
                    duration_ms=hold + 1600)
    # The recording opens on the empty background: the font wait plus most of the
    # fade-in. Eight cards' worth of it was six seconds of the reel.
    subprocess.run(_with_quality(trim_clip_cmd(raw, CARD_HEAD_S, total_s, out_path)),
                   capture_output=True, check=True)
    os.remove(raw)
    return out_path


def build_claim_reel(reel: str, out_path: str, footage_dir: str = "output/mp4") -> str:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to build the reel")
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    paths, markers = {}, {}
    for take in {i[1] for i in SPINES[reel] if i[0] == "footage"}:
        path = os.path.join(footage_dir, f"claim_{take}_raw.mp4")
        if os.path.exists(path + ".markers.json"):
            paths[take] = path
            with open(path + ".markers.json", encoding="utf-8") as f:
                markers[take] = json.load(f)
        else:
            print(f"No footage for take {take}, its slots are dropped.")

    work = tempfile.mkdtemp()
    try:
        clips = []
        for n, item in enumerate(plan_reel(reel, markers)):
            clip = os.path.join(work, f"{n:02d}.mp4")
            if item[0] == "card":
                print(f"Rendering card: {item[1]} ...")
                _render_card_clip(item[1], clip)
            else:
                _, take, start, end, seg = item
                print(f"Trimming {take} [{seg}] {start}-{end}s ...")
                subprocess.run(
                    _with_quality(trim_clip_cmd(paths[take], start, end, clip,
                                                speed=FOOTAGE_SPEED[seg])),
                    capture_output=True, check=True,
                )
            clips.append(clip)
        subprocess.run(_with_quality(concat_clips_cmd(clips, out_path)),
                       capture_output=True, check=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print("Saved:", out_path)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a profile-claim reel")
    parser.add_argument("--reel", required=True, choices=sorted(SPINES))
    parser.add_argument("--out", help="Output mp4 (default output/mp4/claim_{reel}_reel.mp4)")
    args = parser.parse_args()
    build_claim_reel(args.reel, args.out or f"output/mp4/claim_{args.reel}_reel.mp4")


if __name__ == "__main__":
    main()
