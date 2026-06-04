# WWT — 2026 Season Content Plan

> Source: `content-plan-2026.xlsx` → **Sheet1** (weekly grid, w/c Sun 31 May → Sun 13 Dec 2026).
> Column J ("In Comp Reporting Ideas") intentionally **excluded**. Column L used as the post-type key.

## How to use this doc
1. Each post is a checkbox. **Tick `[x]` once you've previewed and approved it.**
2. Preview with the listed `generate.py` command (`--dry-run --preview` opens dummy data in the browser — no DB/API needed).
3. Once approved, transfer the post to `content_backlog.yaml` with a real `scheduled_date` + final params. Suggested backlog `id` is noted on data-driven posts.
4. **🟠 BESPOKE** blocks have no template — fill in the TODO fields, then design manually.

## Post-type → template key (from column L)
| Column-L key | Type tag | Template | Notes |
|---|---|---|---|
| top 10 wave/jump — event | `top10` | `top_10_carousel` | `--event <ID>` (single event) |
| top 10 wave/jump — current season | `top10` | `top_10_carousel` | `--year 2026` (+ `--event` for that event's season) |
| top 10 wave/jump — all time | `top10` | `top_10_carousel` | no `--year`; `--event <ID>` for a location's all-time |
| h2h event | `h2h` | `h2h_carousel` | `--event --athlete1 --athlete2 --division` |
| rider profile event | `rider` | `rider_profile` | `--athlete1 --event --sex` |
| canaries lookback | `analysis` | `canary_kings` | Kings & Queens of the Canaries |
| athlete rise | `rise` | `athlete_rise` | `--athlete1 --location --sex` |
| fantasy post | `fantasy` | `fantasy_league_announce` | weekly updates may be bespoke |
| bespoke / JA Fantasy Picks | `bespoke` | — | manual design (placeholder block) |

> All `top_10_carousel` and `h2h_carousel` "Men & Women" rows = **two posts** (run once `--sex Men` / once `--sex Women`, or `--division`).
> **"Top 3" rows = three `rider_profile` posts** (1st / 2nd / 3rd place) per division — so "Top 3 Men & Women" = up to **6 posts**.
> `<ID>` / `<ATH>` = fill in real event/athlete IDs before going live.

## ✅ Resolved (2026-06-02)
- **Chile week (w/c 8 Nov)** "Sylt top 10…" was a copy/paste error → **corrected to Chile** below.
- **Tiree 4\* week (w/c 11 Oct):** Aloha content **kept as-is** — Tiree is a 4* (data uncertain); we want the Aloha all-time preview either way.
- **"Top 3" posts = three rider profiles** from that event, for the relevant year (1st / 2nd / 3rd place). "Men & Women" = run per division. Rebuilt as `rider_profile` posts below.
- **"Rp"** = **Rider Profile** (e.g. "Rp Top 3 Men Sylt 20XX" = 1st/2nd/3rd Sylt rider profiles).
- **`M28`/`N28` loose dates** — ignored.

## ⚠ Still open
- [ ] **`GC 5* TBC`** (w/c 28 Jun) — confirm Gran Canaria event dates/ID.
- [ ] **Year placeholders** (left with you): Köster's first Pozo title year; Sarah-Quita vs Iball year; Justyna Śniady profile year; Viticot vs Marc final (2024/2025); throwback Top-3 years (TFS Women `201x`, Sylt `20XX`, Chile `202X`); "top women 10 sylt" year (`201X`); year for each event's Top-3 rider profiles.
- [ ] **Fantasy League** weekly (Sat) — same announce graphic, or weekly leaderboard updates needing a new template? *(TBC)*

---

# JUNE

## Week of Sun 31 May — 🏆 Fiji 4*
- [ ] **Wed 03 Jun — JA Picks for Fiji** · `bespoke`
  > 🟠 **BESPOKE** — JA Fantasy Picks
  > - **Brief:** Jack's pre-event fantasy picks for Fiji
  > - **Assets needed:** rider photos, pick rationale copy
  > - **Data source:** TODO
  > - **Backlog id:** `fiji-ja-picks`

## Week of Sun 07 Jun
- [ ] **Mon 08 Jun — Fiji 1st-place rider profiles (Men & Women), 2026** · `rider` · `rider_profile`
  `python generate.py --template rider_profile --athlete1 <WINNER_ATH> --event <FIJI_ID> --sex Men --dry-run --preview`  *(1st place × Men & Women = 2 posts)*
  → backlog: `fiji2026-rp-m1`, `fiji2026-rp-w1`
- [ ] **Wed 10 Jun — Fiji Top 10 Men & Women Waves** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Wave --sex Men --event <FIJI_ID> --dry-run --preview`  *(repeat `--sex Women`)*
  → backlog: `fiji2026-mens-waves-top10`, `fiji2026-womens-waves-top10`
- [ ] **Fri 12 Jun — 1st vs 2nd Men, Head-to-Head** · `h2h` · `h2h_carousel`
  `python generate.py --template h2h_carousel --event <FIJI_ID> --athlete1 <ATH> --athlete2 <ATH> --division Men --dry-run --preview`
  → backlog: `fiji2026-1v2-men-h2h`
- [ ] **Sat 13 Jun — Fantasy League Public Launch?** · `fantasy` · `fantasy_league_announce`
  `python generate.py --template fantasy_league_announce --dry-run --preview`
  → backlog: `fantasy-public-launch` *(confirm launch date)*

## Week of Sun 14 Jun — Canaries lookback (3 weeks to GC)
- [ ] **Mon 15 Jun — "3 weeks until the Canaries": champions of the Canaries since 2006** · `analysis` · `canary_kings`
  `python generate.py --template canary_kings --dry-run --preview`
  → backlog: `canaries-champions-lookback`
- [~] **Wed 17 Jun — Köster's first Pozo title (age ?? + stats)** · `rider` · `rider_profile` — ❌ **SKIPPED**: no wave/heat score data before 2017 (his first title was 2011), so the profile renders empty.
  `python generate.py --template rider_profile --athlete1 <KOSTER_ID> --event <POZO_ID> --sex Men --dry-run --preview`
  *(needs title year — see open questions)* → backlog: `koster-first-pozo`
- [ ] **Fri 19 Jun — H2H: Philip vs Victor OR Philip vs Browne (CAREER)** · `h2h` · `h2h_carousel`
  `python generate.py --template h2h_carousel --athlete1 <ATH> --athlete2 <ATH> --division Men --dry-run --preview`
  *(career mode — no `--event`; pick which matchup)* → backlog: `career-h2h-philip-vX`
- [ ] **Sat 20 Jun — Fantasy Post** · `fantasy` · `fantasy_league_announce`
  `python generate.py --template fantasy_league_announce --dry-run --preview`

## Week of Sun 21 Jun — Women focus
- [ ] **Mon 22 Jun — Rise of Pozo local Alexia Kiefer?** · `rise` · `athlete_rise`
  `python generate.py --template athlete_rise --athlete1 <KIEFER_ID> --location "Pozo" --sex Women --dry-run --preview`
  → backlog: `kiefer-rise`
- [ ] **Wed 24 Jun — H2H: Sarah-Quita vs Iball (XX year?)** · `h2h` · `h2h_carousel`
  `python generate.py --template h2h_carousel --event <ID> --athlete1 <SQO_ID> --athlete2 <IBALL_ID> --division Women --dry-run --preview`
  *(confirm year/event)* → backlog: `sqo-vs-iball-h2h`
- [x] **Fri 26 Jun — Justyna Śniady rider profile** — ✅ GC/Pozo 2019, 2nd place (event 83, athlete 11). Pozo-throwback angle, "can she go one better in 2026". Backlog id `sniady-gc-2019-profile`.
  `python generate.py --template rider_profile --athlete1 11 --event 83 --division Women --preview`
  → backlog: `sniady-gc-2019-profile`
- [ ] **Sat 27 Jun — Fantasy Post** · `fantasy` · `fantasy_league_announce`

## Week of Sun 28 Jun — 🏆 GC 5* (TBC)
- [ ] **Mon 29 Jun — GC Top 10 Jump, all time** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Jump --event <GC_ID> --dry-run --preview`  *(all-time at GC: no `--year`)*
  → backlog: `gc-alltime-jumps-top10`
- [ ] **Wed 01 Jul — GC Top 10 Wave, all time** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Wave --event <GC_ID> --dry-run --preview`
  → backlog: `gc-alltime-waves-top10`
- [ ] **Fri 03 Jul — JA Fantasy Picks (Gregory)** · `bespoke`
  > 🟠 **BESPOKE** — JA Fantasy Picks
  > - **Brief:** Jack's GC fantasy picks (Gregory angle)
  > - **Assets needed:** TODO · **Data source:** TODO · **Backlog id:** `gc-ja-picks`
- [ ] **Sat 04 Jul — Fantasy Post** · `fantasy` · `fantasy_league_announce`

---

# JULY

## Week of Sun 05 Jul
*(no posts scheduled — GC competition window)*

## Week of Sun 12 Jul — GC recap
- [ ] **Mon 13 Jul — GC Top 3 rider profiles (1st/2nd/3rd, Men & Women), 2026** · `rider` · `rider_profile`
  `python generate.py --template rider_profile --athlete1 <PODIUM_ATH> --event <GC_ID> --sex Men --dry-run --preview`  *(repeat for 1st/2nd/3rd × Men & Women = 6 posts)*
  → backlog: `gc2026-rp-m1`, `gc2026-rp-m2`, `gc2026-rp-m3`, `gc2026-rp-w1`, `gc2026-rp-w2`, `gc2026-rp-w3`
- [ ] **Wed 15 Jul — GC Top 10 2026 Waves Men & Women** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Wave --sex Men --year 2026 --event <GC_ID> --dry-run --preview`  *(repeat `--sex Women`)*
  → backlog: `gc2026-mens-waves-top10`, `gc2026-womens-waves-top10`
- [ ] **Fri 17 Jul — GC Top 10 2026 Jumps Men & Women** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Jump --sex Men --year 2026 --event <GC_ID> --dry-run --preview`  *(repeat `--sex Women`)*
  → backlog: `gc2026-mens-jumps-top10`, `gc2026-womens-jumps-top10`
- [ ] **Sat 18 Jul — Fantasy League** · `fantasy` · `fantasy_league_announce`

## Week of Sun 19 Jul — Tenerife build-up
- [ ] **Mon 20 Jul — Bespoke TFS** · `bespoke`
  > 🟠 **BESPOKE** — Tenerife teaser
  > - **Brief:** TODO · **Assets:** TODO · **Data:** TODO · **Backlog id:** `tfs-teaser`
- [ ] **Wed 22 Jul — Former Duotone teammates meet in the final (2024?/2025?): Viticot vs Marc** · `h2h` · `h2h_carousel`
  `python generate.py --template h2h_carousel --event <ID> --athlete1 <VITICOT_ID> --athlete2 <MARC_ID> --division Men --dry-run --preview`
  *(confirm 2024 vs 2025 final)* → backlog: `viticot-vs-marc-final-h2h`
- [x] **Fri 24 Jul — Throwback 2024 TFS Women Top 3 rider profiles** — ✅ Tenerife 2024 (event 25): 1st Erpenstein (16), 2nd Iballa (178), 3rd Kiefer (12). Custom photos (@jcwindsurf/@pwaworldtour). 3 posts 09:00/09:30/10:00.
  `python generate.py --template rider_profile --athlete1 16 --event 25 --division Women --preview`  *(repeat 178, 12)*
  → backlog: `tfs2024-throwback-rp-erpenstein-1st`, `tfs2024-throwback-rp-iballa-2nd`, `tfs2024-throwback-rp-kiefer-3rd`
- [ ] **Sat 25 Jul — Fantasy League** · `fantasy` · `fantasy_league_announce`

## Week of Sun 26 Jul — 🏆 Tenerife 5*
- [ ] **Mon 27 Jul — TFS Top 10 Jump, all time** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Jump --event <TFS_ID> --dry-run --preview`
  → backlog: `tfs-alltime-jumps-top10`
- [ ] **Wed 29 Jul — TFS Top 10 Wave, all time** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Wave --event <TFS_ID> --dry-run --preview`
  → backlog: `tfs-alltime-waves-top10`
- [ ] **Thu 30 Jul — JA Fantasy Picks** · `bespoke`
  > 🟠 **BESPOKE** — JA Fantasy Picks (Tenerife)
  > - **Brief:** TODO · **Assets:** TODO · **Backlog id:** `tfs-ja-picks`

---

# AUGUST

## Week of Sun 02 Aug
*(no posts scheduled — Tenerife competition window)*

## Week of Sun 09 Aug — Tenerife recap
- [ ] **Mon 10 Aug — TFS Top 3 rider profiles (1st/2nd/3rd, Men & Women), 2026** · `rider` · `rider_profile`
  `python generate.py --template rider_profile --athlete1 <PODIUM_ATH> --event <TFS_ID> --sex Men --dry-run --preview`  *(1st/2nd/3rd × M&W = 6 posts)*
  → backlog: `tfs2026-rp-m1`, `tfs2026-rp-m2`, `tfs2026-rp-m3`, `tfs2026-rp-w1`, `tfs2026-rp-w2`, `tfs2026-rp-w3`
- [ ] **Wed 12 Aug — TFS Top 10 2026 Waves Men & Women** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Wave --sex Men --year 2026 --event <TFS_ID> --dry-run --preview`  *(repeat `--sex Women`)*
  → backlog: `tfs2026-mens-waves-top10`, `tfs2026-womens-waves-top10`
- [ ] **Fri 14 Aug — TFS Top 10 2026 Jumps Men & Women** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Jump --sex Men --year 2026 --event <TFS_ID> --dry-run --preview`  *(repeat `--sex Women`)*
  → backlog: `tfs2026-mens-jumps-top10`, `tfs2026-womens-jumps-top10`
- [ ] **Sat 15 Aug — Fantasy League** · `fantasy` · `fantasy_league_announce`

## Week of Sun 16 Aug — Throwbacks
- [ ] **Mon 17 Aug — Tiree throwback** · `bespoke`
  > 🟠 **BESPOKE** — Tiree throwback · **Brief/Assets/Data:** TODO · **Backlog id:** `tiree-throwback`
- [ ] **Wed 19 Aug — Portugal throwback, Men Top 3 rider profiles** · `rider` · `rider_profile`
  `python generate.py --template rider_profile --athlete1 <PODIUM_ATH> --event <PORTUGAL_HIST_ID> --sex Men --dry-run --preview`  *(1st/2nd/3rd = 3 posts; confirm year)*
  → backlog: `portugal-throwback-rp1`, `portugal-throwback-rp2`, `portugal-throwback-rp3`
- [ ] **Fri 21 Aug — Brazil throwback** · `bespoke`
  > 🟠 **BESPOKE** — Brazil throwback · **Brief/Assets/Data:** TODO · **Backlog id:** `brazil-throwback`
- [ ] **Sat 22 Aug — Fantasy League** · `fantasy` · `fantasy_league_announce`

## Week of Sun 23 Aug — Season standings
- [ ] **Mon 24 Aug — Top 10 Wave, current season** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Wave --sex Men --year 2026 --dry-run --preview`  *(season-wide, no `--event`; repeat `--sex Women`)*
  → backlog: `season2026-waves-top10`
- [ ] **Wed 26 Aug — Top 10 Jump, current season** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Jump --sex Men --year 2026 --dry-run --preview`  *(repeat `--sex Women`)*
  → backlog: `season2026-jumps-top10`
- [ ] **Fri 28 Aug — "Road to" teaser** · `bespoke`
  > 🟠 **BESPOKE** — Road To… teaser (precedes the ranking-calculator launch)
  > - **Brief:** TODO · **Assets:** TODO · **Backlog id:** `road-to-teaser`
- [ ] **Sat 29 Aug — Fantasy League** · `fantasy` · `fantasy_league_announce`

## Week of Sun 30 Aug — Ranking update + feature launch
- [ ] **Mon 31 Aug — Men's Ranking Update** · `bespoke`
  > 🟠 **BESPOKE** — rankings · **Data:** current season rankings · **Backlog id:** `mens-ranking-update`
- [ ] **Wed 02 Sep — Women's Ranking Update** · `bespoke`
  > 🟠 **BESPOKE** — rankings · **Data:** current season rankings · **Backlog id:** `womens-ranking-update`
- [ ] **Fri 04 Sep — LAUNCH: "Road To" Ranking Calculator** · `bespoke` (feature launch)
  > 🟠 **BESPOKE** — product/feature launch
  > - **Brief:** announce the ranking calculator · **Assets:** demo/screens · **Backlog id:** `ranking-calculator-launch`
- [ ] **Sat 05 Sep — Fantasy League** · `fantasy` · `fantasy_league_announce`

---

# SEPTEMBER

## Week of Sun 06 Sep — Sylt build-up
- [ ] **Mon 07 Sep — Sylt Men Top 3 rider profiles (throwback 20XX??)** · `rider` · `rider_profile`
  `python generate.py --template rider_profile --athlete1 <PODIUM_ATH> --event <SYLT_HIST_ID> --sex Men --dry-run --preview`  *(1st/2nd/3rd = 3 posts; confirm year)*
  → backlog: `sylt-throwback-m-rp1`, `sylt-throwback-m-rp2`, `sylt-throwback-m-rp3`
- [ ] **Wed 09 Sep — Sylt Women Top 3 rider profiles (throwback 20XX??)** · `rider` · `rider_profile`
  `python generate.py --template rider_profile --athlete1 <PODIUM_ATH> --event <SYLT_HIST_ID> --sex Women --dry-run --preview`  *(1st/2nd/3rd = 3 posts)*
  → backlog: `sylt-throwback-w-rp1`, `sylt-throwback-w-rp2`, `sylt-throwback-w-rp3`
- [ ] **Fri 11 Sep — Men H2H, Sylt** · `h2h` · `h2h_carousel`
  `python generate.py --template h2h_carousel --event <SYLT_ID> --athlete1 <ATH> --athlete2 <ATH> --division Men --dry-run --preview`
  → backlog: `sylt-men-h2h`
- [ ] **Sat 12 Sep — Fantasy League** · `fantasy` · `fantasy_league_announce`

## Week of Sun 13 Sep — Sylt build-up
- [ ] **Mon 14 Sep — Women H2H, Sylt** · `h2h` · `h2h_carousel`
  `python generate.py --template h2h_carousel --event <SYLT_ID> --athlete1 <ATH> --athlete2 <ATH> --division Women --dry-run --preview`
  → backlog: `sylt-women-h2h`
- [ ] **Wed 16 Sep — Bespoke Sylt** · `bespoke`
  > 🟠 **BESPOKE** — Sylt feature · **Brief/Assets/Data:** TODO · **Backlog id:** `sylt-bespoke`
- [ ] **Fri 18 Sep — Top 10 Women, Sylt (201X)** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Wave --sex Women --event <SYLT_ID> --dry-run --preview`  *(confirm score type + year)*
  → backlog: `sylt-women-top10`
- [ ] **Sat 19 Sep — Fantasy League** · `fantasy` · `fantasy_league_announce`

## Week of Sun 20 Sep — 🏆 Sylt 5*
- [ ] **Mon 21 Sep — Sylt Top 10 Jump, all time** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Jump --event <SYLT_ID> --dry-run --preview`
  → backlog: `sylt-alltime-jumps-top10`
- [ ] **Wed 23 Sep — Sylt Top 10 Wave, all time** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Wave --event <SYLT_ID> --dry-run --preview`
  → backlog: `sylt-alltime-waves-top10`
- [ ] **Thu 24 Sep — JA Fantasy Picks** · `bespoke`
  > 🟠 **BESPOKE** — JA Fantasy Picks (Sylt) · **Backlog id:** `sylt-ja-picks`

---

# OCTOBER

## Week of Sun 27 Sep
*(no posts scheduled — Sylt competition window)*

## Week of Sun 04 Oct — Sylt recap
- [ ] **Mon 05 Oct — Sylt Top 3 rider profiles (1st/2nd/3rd, Men & Women), 2026** · `rider` · `rider_profile`
  `python generate.py --template rider_profile --athlete1 <PODIUM_ATH> --event <SYLT_ID> --sex Men --dry-run --preview`  *(1st/2nd/3rd × M&W = 6 posts)*
  → backlog: `sylt2026-rp-m1`, `sylt2026-rp-m2`, `sylt2026-rp-m3`, `sylt2026-rp-w1`, `sylt2026-rp-w2`, `sylt2026-rp-w3`
- [ ] **Wed 07 Oct — Sylt Top 10 2026 Waves Men & Women** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Wave --sex Men --year 2026 --event <SYLT_ID> --dry-run --preview`  *(repeat `--sex Women`)*
  → backlog: `sylt2026-mens-waves-top10`, `sylt2026-womens-waves-top10`
- [ ] **Fri 09 Oct — Sylt Top 10 2026 Jumps Men & Women** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Jump --sex Men --year 2026 --event <SYLT_ID> --dry-run --preview`  *(repeat `--sex Women`)*
  → backlog: `sylt2026-mens-jumps-top10`, `sylt2026-womens-jumps-top10`
- [ ] **Sat 10 Oct — JA Fantasy Picks** · `bespoke`
  > 🟠 **BESPOKE** — JA Fantasy Picks · **Backlog id:** `oct-ja-picks`

## Week of Sun 11 Oct — 🏆 Tiree 4*  ⚠ *(content tagged "Aloha" — see open questions)*
- [ ] **Wed 14 Oct — Aloha Top 10 Wave, all time** · `top10` · `top_10_carousel`  ⚠ *event week is Tiree*
  `python generate.py --template top_10_carousel --score-type Wave --event <ALOHA_ID> --dry-run --preview`
  → backlog: `aloha-alltime-waves-top10`

## Week of Sun 18 Oct — 🏆 Aloha 5*
- [ ] **Sun 18 Oct — JA Fantasy Picks** · `bespoke`
  > 🟠 **BESPOKE** — JA Fantasy Picks (Aloha) · **Backlog id:** `aloha-ja-picks`
- [x] **Mon 19 Oct — Aloha Top 3 rider profiles (1st/2nd/3rd, Men & Women), 2025** — ✅ Aloha Classic 2025 (event 134). Men: 1st Noireaux (52), 2nd Roediger (45), 3rd Browne (68). Women: 1st Offringa (5), 2nd Cochran (92), 3rd Wermeister (14). Custom photos (@pwaworldtour/@fishbowldiaries); 6 posts 09:00–11:30, reveal 3rd→1st alternating M/W. No headshot for Wermeister (thumb → API photo).
  `python generate.py --template rider_profile --athlete1 52 --event 134 --division Men --preview`  *(repeat 45/68/5/92/14)*
  → backlog: `aloha2025-rp-m1`, `aloha2025-rp-m2`, `aloha2025-rp-m3`, `aloha2025-rp-w1`, `aloha2025-rp-w2`, `aloha2025-rp-w3`

## Week of Sun 25 Oct
*(no posts scheduled — Aloha competition window)*

---

# NOVEMBER

## Week of Sun 01 Nov — Title race + Chile build-up
- [ ] **Mon 02 Nov — Title Race, Men** · `bespoke`
  > 🟠 **BESPOKE** — title-race standings (M) · **Data:** current rankings/scenarios · **Backlog id:** `title-race-men`
- [ ] **Wed 04 Nov — Title Race, Women** · `bespoke`
  > 🟠 **BESPOKE** — title-race standings (W) · **Backlog id:** `title-race-women`
- [ ] **Fri 06 Nov — Chile throwback (202X) Top 3 rider profiles (Men & Women)** · `rider` · `rider_profile`
  `python generate.py --template rider_profile --athlete1 <PODIUM_ATH> --event <CHILE_HIST_ID> --sex Men --dry-run --preview`  *(1st/2nd/3rd × M&W = 6 posts; confirm year)*
  → backlog: `chile-throwback-rp-m1..m3`, `chile-throwback-rp-w1..w3`

## Week of Sun 08 Nov — 🏆 Chile 5*
- [ ] **Mon 09 Nov — Chile Top 10 Jump, all time** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Jump --event <CHILE_ID> --dry-run --preview`
  → backlog: `chile-alltime-jumps-top10`
- [ ] **Wed 11 Nov — Chile Top 10 Wave, all time** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Wave --event <CHILE_ID> --dry-run --preview`
  → backlog: `chile-alltime-waves-top10`
- [ ] **Fri 13 Nov — JA Fantasy Picks** · `bespoke`
  > 🟠 **BESPOKE** — JA Fantasy Picks (Chile) · **Backlog id:** `chile-ja-picks`

## Week of Sun 15 Nov
*(no posts scheduled — Chile competition window)*

## Week of Sun 22 Nov
*(no posts scheduled — Chile competition window)*

## Week of Sun 29 Nov — 🏁 Season finale
- [ ] **Sun 29 Nov — Chile Top 3 rider profiles (1st/2nd/3rd, Men & Women), 2026** · `rider` · `rider_profile`
  `python generate.py --template rider_profile --athlete1 <PODIUM_ATH> --event <CHILE_ID> --sex Men --dry-run --preview`  *(1st/2nd/3rd × M&W = 6 posts)*
  → backlog: `chile2026-rp-m1`, `chile2026-rp-m2`, `chile2026-rp-m3`, `chile2026-rp-w1`, `chile2026-rp-w2`, `chile2026-rp-w3`
- [ ] **Mon 30 Nov — WORLD CHAMPIONS** · `bespoke` (season champions reveal)
  > 🟠 **BESPOKE** — 2026 World Champions (M+W)
  > - **Brief:** crown the season champions · **Assets:** champion photos, final standings · **Backlog id:** `world-champions-2026`
- [ ] **Tue 01 Dec — Fantasy Champions** · `bespoke` (fantasy season winners)
  > 🟠 **BESPOKE** — fantasy league season winners · **Data:** fantasy final standings · **Backlog id:** `fantasy-champions-2026`
- [ ] **Wed 02 Dec — Chile Top 10 2026 Waves Men & Women** · `top10` · `top_10_carousel`
  `python generate.py --template top_10_carousel --score-type Wave --sex Men --year 2026 --event <CHILE_ID> --dry-run --preview`  *(repeat `--sex Women`)*
  → backlog: `chile2026-mens-waves-top10`, `chile2026-womens-waves-top10`

---

# DECEMBER

## Week of Sun 06 Dec
*(no posts scheduled)*

## Week of Sun 13 Dec
*(no posts scheduled)*

---

## Summary
- **Total weeks:** 29 (w/c 31 May → 13 Dec). **Grid cells:** ~60 — but "Top 3" and "Men & Women" rows fan out, so **actual posts ≈ 90+**.
- **Events (col I):** Fiji 4* · GC 5* (TBC) · Tenerife 5* · Sylt 5* · Tiree 4* · Aloha 5* · Chile 5*.
- **Each event follows the arc:** build-up (throwbacks / H2H / rider profiles / all-time top 10s) → recap (Top-3 rider profiles + current-season top 10s).
- **"Top 3" → 3 rider profiles** (1st/2nd/3rd) per division → up to 6 `rider_profile` posts each.
- **Recurring:** weekly Fantasy League (Sat) + JA Fantasy Picks before each event.
- **Bespoke remaining (~13):** Fiji winners, JA picks (×6), teasers (TFS / Tiree / Brazil / Road-to / Sylt), ranking updates (×2), calculator launch, title race (×2), World Champions, Fantasy Champions.
