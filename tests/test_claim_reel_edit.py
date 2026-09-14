"""Claim reels: the pure spine planner. Render and ffmpeg passes are verified by running."""
from pipeline.claim_reel_edit import CARDS, SPINES, plan_reel

PRO = {"board_start": 4.5, "board_end": 12.6, "form_start": 12.6, "form_end": 20.9}


def test_pro_reel_cuts_both_segments_from_its_one_take():
    plan = plan_reel("pro", {"pro": PRO})
    assert [i[0] for i in plan] == ["card", "card", "footage", "footage", "card", "card"]
    assert plan[2] == ("footage", "pro", 4.5, 12.6, "board")
    assert plan[3] == ("footage", "pro", 12.6, 20.9, "form")


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
                assert "—" not in " ".join(str(v) for v in card.values())
