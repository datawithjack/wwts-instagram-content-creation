"""Claim reels: the pure spine planner. Render and ffmpeg passes are verified by running."""
import json

from pipeline.claim_reel_edit import CARDS, SPINES, plan_reel

PRO = {"profile_start": 4.5, "profile_end": 14.0, "board_start": 14.8, "board_end": 22.0}


def test_pro_reel_claims_on_the_profile_then_joins_the_board():
    plan = plan_reel("pro", {"pro": PRO})
    assert [i[1] if i[0] == "card" else i[-1] for i in plan] == [
        "pro_hook", "pro_who", "pro_claim", "profile", "pro_join", "board",
        "pro_why", "pro_cta",
    ]
    assert ("footage", "pro", 4.5, 14.0, "profile") in plan


def test_coach_reel_cuts_each_segment_from_its_own_take():
    plan = plan_reel("coach", {
        "coach-board": {"board_start": 2.5, "board_end": 10.6},
        "coach-form": {"form_start": 6.0, "form_end": 14.0},
    })
    footage = [i for i in plan if i[0] == "footage"]
    assert footage == [
        ("footage", "coach-board", 2.5, 10.6, "board"),
        ("footage", "coach-form", 6.0, 14.0, "form"),
    ]


def test_a_missing_take_drops_its_slot_and_keeps_the_rest():
    """The coach form take cannot be filmed until the coach flag is removed."""
    plan = plan_reel("coach", {"coach-board": {"board_start": 2.5, "board_end": 10.6}})
    assert [i[-1] if i[0] == "footage" else i[1] for i in plan] == [
        "coach_hook", "board", "coach_next", "coach_cta",
    ]


def test_every_card_in_a_spine_has_copy_without_em_dashes():
    for spine in SPINES.values():
        for item in spine:
            if item[0] == "card":
                card = CARDS[item[1]]
                assert "—" not in json.dumps(card, ensure_ascii=False)
