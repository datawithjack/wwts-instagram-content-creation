"""The contact sheet: every candidate frame, shown as the slide it would become.

Judging a 3:2 photograph and judging a 1080x1350 slide are different jobs. A
frame that looks superb wide can put the rider exactly where the score goes, and
a frame that looks empty can crop to something strong. So every card here is the
real crop, at the real aspect, under the real gradient, with the score and name
sitting on it -- and the full frame is the small reference underneath.

The crop slider writes ``object-position`` straight through to focus.json, so the
anchor is set by eye against the finished slide rather than estimated from the
whole photograph.
"""

import html
import json

# Matches slide_wave_photo.html, so the card is not a rough approximation.
SLIDE_GRADIENT = (
    "linear-gradient(to bottom,"
    "rgba(8,20,40,.20) 0%,rgba(10,14,26,.42) 40%,rgba(10,14,26,.80) 62%,"
    "rgba(10,14,26,.97) 78%,rgba(10,14,26,1) 100%)"
)


def _card(rider, cand) -> str:
    credit = cand["credit"]
    tagged = credit["confirmed"]
    who = credit["photographer"] or "no credit tag"
    badge_cls = "ok" if tagged else "warn"
    kind = "ACTION" if cand["kind"] == "wv" else cand["kind"].upper()

    return f"""
    <label class="card" data-athlete="{rider['athlete_id']}"
           data-file="{html.escape(cand['path'])}">
      <input type="radio" name="pick-{rider['athlete_id']}"
             value="{html.escape(cand['path'])}">
      <div class="crop">
        <img src="/thumbs/{cand['thumb']}" style="object-position:50% 50%">
        <div class="veil"></div>
        <div class="type">
          <span class="chip">{html.escape(rider['rank_label'])} BEST {html.escape(rider['metric'])}</span>
          <div class="score">{cand['score_label']}</div>
          <div class="who">{html.escape(rider['name'].upper())}</div>
        </div>
      </div>
      <div class="meta">
        <span class="kind">{kind}</span>
        <span class="badge {badge_cls}" title="{html.escape(who)}">
          {'&#10003; ' + html.escape(who) if tagged else '&#9888; untagged'}
        </span>
      </div>
      <div class="fname">{html.escape(cand['name'])}</div>
      <div class="tools">
        <span class="lbl">crop</span>
        <input class="focus" type="range" min="0" max="100" value="50">
        <span class="val">50%</span>
      </div>
      <div class="full"><img src="/thumbs/{cand['thumb']}"></div>
    </label>"""


def _rider_block(rider) -> str:
    if not rider["candidates"]:
        note = (f"<p class='empty'>No frames found for sail "
                f"<b>{html.escape(str(rider['sail']))}</b> "
                f"(tried {html.escape(', '.join(rider['tokens']))}). "
                f"He or she may be in the untagged MISC / YOUTH / MASTERS "
                f"buckets, which no sail lookup can reach.</p>")
        cards = ""
    else:
        note = ""
        cards = "".join(_card(rider, c) for c in rider["candidates"])

    return f"""
  <section class="rider" id="rider-{rider['athlete_id']}">
    <header>
      <h2>{html.escape(rider['name'])}</h2>
      <span class="sub">{html.escape(rider['rank_label'])} &middot;
        {rider['score']:.2f} &middot; sail {html.escape(str(rider['sail']))} &middot;
        {len(rider['candidates'])} frames</span>
      <label class="skip"><input type="radio" name="pick-{rider['athlete_id']}"
             value="" checked> leave as is</label>
    </header>
    {note}
    <div class="grid">{cards}</div>
  </section>"""


def render_sheet(riders, event_label: str) -> str:
    """The whole sheet as one HTML string."""
    blocks = "".join(_rider_block(r) for r in riders)
    counts = json.dumps({r["athlete_id"]: len(r["candidates"]) for r in riders})

    return f"""<!doctype html>
<meta charset="utf-8">
<title>Pick photos &middot; {html.escape(event_label)}</title>
<style>
  :root {{ --bg:#0E1927; --card:#16233A; --line:#24354F; --text:#E8EEF7;
           --dim:#93A6C0; --accent:#5AB4CC; --ok:#4DA89E; --warn:#D9A441; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:28px 32px 120px; background:var(--bg); color:var(--text);
          font:15px/1.5 "Inter",system-ui,sans-serif; }}
  h1 {{ font-size:24px; margin:0 0 2px; }}
  .lede {{ color:var(--dim); margin:0 0 26px; }}
  .rider {{ margin-bottom:38px; border-top:1px solid var(--line); padding-top:18px; }}
  .rider header {{ display:flex; align-items:baseline; gap:14px; flex-wrap:wrap;
                   margin-bottom:14px; }}
  .rider h2 {{ font-size:19px; margin:0; }}
  .sub {{ color:var(--dim); font-size:13px; }}
  .skip {{ margin-left:auto; color:var(--dim); font-size:13px; cursor:pointer; }}
  .empty {{ color:var(--warn); background:rgba(217,164,65,.08);
            border:1px solid rgba(217,164,65,.3); padding:12px 14px; border-radius:8px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(216px,1fr));
           gap:16px; }}
  .card {{ background:var(--card); border:2px solid var(--line); border-radius:10px;
           padding:8px; cursor:pointer; display:block; }}
  .card:has(input:checked) {{ border-color:var(--accent);
           box-shadow:0 0 0 3px rgba(90,180,204,.22); }}
  .card input {{ display:none; }}
  .crop {{ position:relative; width:100%; aspect-ratio:1080/1350; overflow:hidden;
           border-radius:6px; background:#000; }}
  .crop img {{ width:100%; height:100%; object-fit:cover; display:block; }}
  .veil {{ position:absolute; inset:0; background:{SLIDE_GRADIENT}; }}
  .type {{ position:absolute; left:10px; right:10px; bottom:9px; }}
  .chip {{ display:inline-block; background:#F0C040; color:#0E1927; font-weight:800;
           font-size:8px; letter-spacing:.09em; padding:3px 6px; border-radius:2px; }}
  .score {{ font-size:34px; line-height:.9; font-weight:800; color:var(--accent);
            margin-top:5px; }}
  .who {{ font-size:12px; font-weight:700; margin-top:2px; }}
  .meta {{ display:flex; align-items:center; gap:6px; margin-top:7px; font-size:10px; }}
  .kind {{ color:var(--dim); letter-spacing:.09em; font-weight:700; }}
  .badge {{ margin-left:auto; padding:2px 6px; border-radius:3px; font-weight:700;
            white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:130px; }}
  .badge.ok {{ background:rgba(77,168,158,.16); color:var(--ok); }}
  .badge.warn {{ background:rgba(217,164,65,.16); color:var(--warn); }}
  .fname {{ font:10px ui-monospace,monospace; color:var(--dim); margin-top:5px;
            overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
  .tools {{ display:flex; align-items:center; gap:7px; margin-top:6px; font-size:10px;
            color:var(--dim); }}
  .tools .focus {{ flex:1; }}
  .full {{ margin-top:7px; }}
  .full img {{ width:100%; border-radius:4px; display:block; opacity:.62; }}
  .bar {{ position:fixed; left:0; right:0; bottom:0; background:#0B1421;
          border-top:1px solid var(--line); padding:13px 32px; display:flex;
          align-items:center; gap:16px; }}
  button {{ background:var(--accent); color:#0B1421; border:0; border-radius:7px;
            padding:11px 22px; font-weight:800; font-size:14px; cursor:pointer; }}
  button[disabled] {{ opacity:.4; cursor:default; }}
  #status {{ color:var(--dim); font-size:13px; }}
</style>

<h1>Pick photos &middot; {html.escape(event_label)}</h1>
<p class="lede">Each card is the real 1080&times;1350 crop under the slide's own
gradient, so you are judging the slide and not the photograph. Drag <b>crop</b> to
move the framing. The small image underneath is the full frame.</p>

{blocks}

<div class="bar">
  <button id="save" disabled>Save picks</button>
  <span id="status">Nothing selected yet.</span>
</div>

<script>
const counts = {counts};

function focusValue(card) {{
  const slider = card.querySelector('.focus');
  return slider ? slider.value + '% 50%' : '50% 50%';
}}

document.addEventListener('input', e => {{
  if (!e.target.classList.contains('focus')) return;
  const card = e.target.closest('.card');
  card.querySelector('.crop img').style.objectPosition = focusValue(card);
  card.querySelector('.val').textContent = e.target.value + '%';
  // Dragging the crop is a clear statement of intent about this frame.
  card.querySelector('input[type=radio]').checked = true;
  refresh();
}});

function selections() {{
  const out = {{}};
  document.querySelectorAll('.rider').forEach(sec => {{
    const id = sec.id.replace('rider-', '');
    const chosen = sec.querySelector('input[type=radio]:checked');
    if (chosen && chosen.value) {{
      const card = chosen.closest('.card');
      out[id] = {{ file: chosen.value, focus: focusValue(card) }};
    }}
  }});
  return out;
}}

function refresh() {{
  const n = Object.keys(selections()).length;
  document.getElementById('save').disabled = n === 0;
  document.getElementById('status').textContent =
    n === 0 ? 'Nothing selected yet.'
            : n + ' of ' + Object.keys(counts).length + ' riders selected.';
}}

document.addEventListener('change', refresh);

document.getElementById('save').addEventListener('click', async () => {{
  const btn = document.getElementById('save');
  btn.disabled = true;
  document.getElementById('status').textContent = 'Saving...';
  try {{
    const res = await fetch('/save', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify(selections()),
    }});
    const body = await res.json();
    document.getElementById('status').textContent =
      body.ok ? 'Saved: ' + body.installed.join(', ') + '. You can close this tab.'
              : 'Failed: ' + body.error;
  }} catch (err) {{
    document.getElementById('status').textContent = 'Failed: ' + err;
    btn.disabled = false;
  }}
}});

refresh();
</script>
"""
