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


# ---------------------------------------------------------------------------
# Steps 2 to 5: review the post, confirm the caption, set the time, save.
#
# Held as plain strings rather than woven into the f-string below, so the CSS
# and JS braces do not have to be doubled. Everything here stays hidden until
# the photos are installed and the server hands back a built post.
# ---------------------------------------------------------------------------

REVIEW_CSS = """
  .step { border-top:1px solid var(--line); padding-top:20px; margin-top:34px; }
  .step h2 { font-size:17px; margin:0 0 4px; }
  .step .hint { color:var(--dim); font-size:13px; margin:0 0 14px; max-width:78ch; }
  .slides { display:flex; gap:14px; overflow-x:auto; padding:4px 0 16px; }
  .slide { flex:0 0 auto; width:281px; height:351px; overflow:hidden;
           border:1px solid var(--line); border-radius:8px; background:#000;
           cursor:zoom-in; position:relative; }
  .slide.big { width:594px; height:743px; cursor:zoom-out; }
  .slide iframe { width:1080px; height:1350px; border:0; display:block;
                  transform:scale(.26); transform-origin:top left;
                  pointer-events:none; }
  .slide.big iframe { transform:scale(.55); }
  .slide .n { position:absolute; top:6px; left:6px; z-index:2; font-size:10px;
              font-weight:800; background:rgba(11,20,33,.82); color:var(--dim);
              padding:2px 6px; border-radius:3px; }
  textarea { width:100%; max-width:820px; background:var(--card); color:var(--text);
             border:1px solid var(--line); border-radius:8px; padding:13px;
             font:14px/1.6 "Inter",system-ui,sans-serif; resize:vertical; }
  .row { display:flex; align-items:center; gap:10px; flex-wrap:wrap;
         margin-bottom:10px; }
  .row label { color:var(--dim); font-size:13px; }
  input[type=text], input[type=datetime-local] {
      background:var(--card); color:var(--text); border:1px solid var(--line);
      border-radius:7px; padding:8px 10px; font:14px "Inter",system-ui,sans-serif; }
  input[type=text] { min-width:360px; }
  .note { border-radius:8px; padding:11px 13px; font-size:13px; margin:10px 0;
          max-width:78ch; }
  .note.warn { background:rgba(217,164,65,.09); border:1px solid rgba(217,164,65,.32);
               color:var(--warn); }
  .note.ok { background:rgba(77,168,158,.10); border:1px solid rgba(77,168,158,.32);
             color:var(--ok); }
  .note pre { white-space:pre-wrap; font:12px/1.5 ui-monospace,monospace;
              margin:7px 0 0; color:var(--dim); }
  code { font:12px ui-monospace,monospace; background:rgba(255,255,255,.05);
         padding:1px 5px; border-radius:3px; }
"""

REVIEW_HTML = """
<section class="step" id="review" hidden>
  <h2>2 &middot; The post</h2>
  <p class="hint">Every slide as it will publish. Click one to see it bigger.</p>
  <div class="slides" id="slides"></div>
</section>

<section class="step" id="write" hidden>
  <h2>3 &middot; The caption</h2>
  <p class="hint">Prefilled and yours to rewrite. Hashtags are <b>not</b> stored
    here: the publisher appends the config set to whatever is saved, so a stored
    hashtag posts twice. It will append <span id="hashtags"></span></p>
  <textarea id="caption" rows="14"></textarea>
  <div class="note warn" id="creditwarn" hidden></div>
</section>

<section class="step" id="when" hidden>
  <h2>4 &middot; When</h2>
  <div class="row">
    <label for="postid">Backlog id</label>
    <input type="text" id="postid">
  </div>
  <div class="note warn" id="collision" hidden></div>
  <div class="row">
    <label for="publishat">Publish at (your time)</label>
    <input type="datetime-local" id="publishat">
    <span class="hint" id="utcline" style="margin:0"></span>
  </div>
  <p class="hint">Stored as UTC, which is what the backlog documents. The Action
    polls every <b>30 minutes</b> and publishes whatever is due, so a post goes
    out at the next poll after its time, not on the minute.</p>
</section>

<section class="step" id="commit" hidden>
  <h2>5 &middot; Save</h2>
  <p class="hint">This writes <code>content_backlog.yaml</code> and nothing else.
    <b>It does not schedule the post.</b> The poller runs from GitHub Actions
    against <code>main</code>, so the entry only exists once you have read the
    diff, committed it and pushed.</p>
  <div class="row">
    <button id="tobacklog">Save to backlog</button>
    <span id="backlogstatus" class="hint" style="margin:0"></span>
  </div>
  <div class="note ok" id="saved" hidden></div>
</section>
"""

REVIEW_JS = """
let POST = null;

function esc(s) {
  return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
}

function showPost(payload) {
  POST = payload;
  const strip = document.getElementById('slides');
  strip.innerHTML = '';
  payload.slides.forEach((html, i) => {
    const box = document.createElement('div');
    box.className = 'slide';
    box.innerHTML = '<span class="n">' + (i + 1) + '</span>';
    const frame = document.createElement('iframe');
    frame.setAttribute('scrolling', 'no');
    frame.srcdoc = html;
    box.appendChild(frame);
    box.addEventListener('click', () => box.classList.toggle('big'));
    strip.appendChild(box);
  });

  document.getElementById('caption').value = payload.caption;
  document.getElementById('hashtags').textContent = payload.hashtags || '(none)';
  document.getElementById('postid').value = payload.post_id;

  // Default to 08:00 UTC tomorrow, the slot the backlog already uses, shown in
  // local time because that is what the input speaks.
  const when = new Date();
  when.setUTCDate(when.getUTCDate() + 1);
  when.setUTCHours(8, 0, 0, 0);
  const local = new Date(when.getTime() - when.getTimezoneOffset() * 60000);
  document.getElementById('publishat').value = local.toISOString().slice(0, 16);

  ['review', 'write', 'when', 'commit'].forEach(
    id => document.getElementById(id).hidden = false);
  checkCredits();
  showUtc();
  checkId();
  document.getElementById('review').scrollIntoView({behavior: 'smooth'});
}

function checkCredits() {
  const box = document.getElementById('creditwarn');
  const body = document.getElementById('caption').value;
  const missing = (POST.credits || []).filter(c => !body.includes(c));
  box.hidden = missing.length === 0;
  if (missing.length) {
    box.innerHTML = 'The caption no longer names ' + esc(missing.join(', ')) +
      '. Someone else took these photographs, so the credit goes back on when ' +
      'you save unless you put it back yourself.';
  }
}

function utcString() {
  const raw = document.getElementById('publishat').value;
  if (!raw) return null;
  // A datetime-local value is wall-clock local time, and Date parses it as
  // such, so toISOString is the conversion. In BST that is an hour's difference
  // and the backlog documents scheduled_date as UTC.
  const local = new Date(raw);
  if (isNaN(local)) return null;
  return local.toISOString().slice(0, 19);
}

function showUtc() {
  const line = document.getElementById('utcline');
  const raw = document.getElementById('publishat').value;
  const utc = utcString();
  if (!utc) { line.textContent = ''; return; }
  const local = new Date(raw);
  const tz = (local.toLocaleTimeString('en-GB', {timeZoneName: 'short'})
              .split(' ').pop());
  const hhmm = raw.slice(11, 16);
  line.textContent = hhmm + ' ' + tz + ' = ' + utc.slice(11, 16) + ' UTC'
      + (utc.slice(0, 10) !== raw.slice(0, 10) ? ' on ' + utc.slice(0, 10) : '');
}

let idTimer = null;
function checkId() {
  clearTimeout(idTimer);
  idTimer = setTimeout(async () => {
    const id = document.getElementById('postid').value.trim();
    const box = document.getElementById('collision');
    if (!id) { box.hidden = true; return; }
    const res = await fetch('/lookup?id=' + encodeURIComponent(id));
    const found = await res.json();
    box.hidden = !found.exists;
    if (found.exists) {
      box.innerHTML = '<b>' + esc(id) + ' is already in the backlog</b>' +
        (found.published ? ' and has already published, so re-dating it ' +
          'publishes nothing: the poller skips published posts. Give it a new id.'
          : '.') +
        ' Saving updates it rather than adding a second entry, and replaces ' +
        'this caption:<pre>' + esc(found.caption || '(none)') + '</pre>' +
        'scheduled ' + esc(found.scheduled_date || '(no date)');
    }
  }, 220);
}

document.addEventListener('input', e => {
  if (e.target.id === 'caption') checkCredits();
  if (e.target.id === 'publishat') showUtc();
  if (e.target.id === 'postid') checkId();
});

document.getElementById('tobacklog').addEventListener('click', async () => {
  const btn = document.getElementById('tobacklog');
  const status = document.getElementById('backlogstatus');
  btn.disabled = true;
  status.textContent = 'Writing...';
  try {
    const res = await fetch('/backlog', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        id: document.getElementById('postid').value.trim(),
        caption: document.getElementById('caption').value,
        scheduled_date: utcString(),
        template: POST.template,
        params: POST.params,
      }),
    });
    const body = await res.json();
    if (!body.ok) {
      status.textContent = '';
      const box = document.getElementById('saved');
      box.className = 'note warn';
      box.hidden = false;
      box.textContent = body.error;
      btn.disabled = false;
      return;
    }
    status.textContent = '';
    const box = document.getElementById('saved');
    box.className = 'note ok';
    box.hidden = false;
    box.innerHTML = '<b>' + esc(body.action) + '</b> ' + esc(body.id) +
      ' for ' + esc(body.scheduled_date) + ' UTC.' +
      (body.credits_restored.length
        ? ' The credit line for ' + esc(body.credits_restored.join(', ')) +
          ' was put back.' : '') +
      (body.time_warning ? '<pre>' + esc(body.time_warning) + '</pre>' : '') +
      '<pre>' + esc(body.message) + '\\n\\n' +
      'git diff content_backlog.yaml\\ngit add content_backlog.yaml assets/photos\\n' +
      'git commit\\ngit push</pre>';
  } catch (err) {
    status.textContent = 'Failed: ' + err;
    btn.disabled = false;
  }
});
"""


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
{REVIEW_CSS}
</style>

<h1>Pick photos &middot; {html.escape(event_label)}</h1>
<p class="lede">Each card is the real 1080&times;1350 crop under the slide's own
gradient, so you are judging the slide and not the photograph. Drag <b>crop</b> to
move the framing. The small image underneath is the full frame.<br>
Saving the picks builds the post below: read the slides, write the caption, pick
a time, and it goes into the backlog.</p>

<section class="step" style="border:0; padding:0; margin:0">
  <h2>1 &middot; The photos</h2>
</section>

{blocks}

{REVIEW_HTML}

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
    const saved = body.installed ? body.installed.length : 0;
    let msg;
    if (!body.ok) {{
      // The photos are already on disk at this point, so say so plainly rather
      // than letting a generation failure read as though the picking was lost.
      msg = saved + ' photo(s) saved. Building the post failed: ' + body.error;
    }} else if (body.skipped) {{
      msg = saved + ' photo(s) saved. ' + (body.message || '');
    }} else {{
      msg = saved + ' photo(s) saved. The post is below.';
      showPost(body.post);
    }}
    document.getElementById('status').textContent = msg;
  }} catch (err) {{
    document.getElementById('status').textContent = 'Failed: ' + err;
    btn.disabled = false;
  }}
}});

refresh();
{REVIEW_JS}
</script>
"""
