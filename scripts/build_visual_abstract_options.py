from __future__ import annotations

import base64
from pathlib import Path

from PIL import Image


REPO_ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = REPO_ROOT / "paper"
FIGURE_ROOT = PAPER_ROOT / "figures"
OPTION_ROOT = FIGURE_ROOT / "visual_abstract_options"

SOURCE_ORACLE = FIGURE_ROOT / "figure_8_oracle_target_recovery_examples.png"


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _crop_rows() -> dict[str, Path]:
    OPTION_ROOT.mkdir(parents=True, exist_ok=True)
    image = Image.open(SOURCE_ORACLE).convert("RGB")
    crops = {
        "lake": (8, 70, 1162, 320),
        "cat": (8, 335, 1162, 585),
        "bicycle": (8, 595, 1162, 845),
    }
    outputs: dict[str, Path] = {}
    for name, box in crops.items():
        out_path = OPTION_ROOT / f"progress_strip_{name}.png"
        image.crop(box).save(out_path)
        outputs[name] = out_path
    return outputs


def _pipeline_svg() -> str:
    return """
<svg viewBox="0 0 900 380" xmlns="http://www.w3.org/2000/svg" aria-label="StableSteering pipeline diagram">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#7a6c5b"/>
    </marker>
  </defs>
  <rect x="8" y="8" width="884" height="364" rx="26" fill="#fbf8f1" stroke="#d7cab8" stroke-width="2"/>
  <text x="34" y="48" font-family="Georgia, 'Times New Roman', serif" font-size="26" font-weight="700" fill="#211b16">Method overview</text>
  <text x="34" y="80" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#5c5144">Prompt p is fixed; the steering state z_t is updated from relative visual preference.</text>

  <rect x="36" y="120" width="180" height="118" rx="22" fill="#f6efe4" stroke="#d7cab8"/>
  <text x="56" y="154" font-family="Georgia, 'Times New Roman', serif" font-size="21" font-weight="700" fill="#211b16">1. Initialize</text>
  <text x="56" y="184" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">Prompt only</text>
  <text x="56" y="208" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">Baseline image</text>
  <text x="56" y="232" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">State z₀ = 0</text>

  <rect x="254" y="120" width="180" height="118" rx="22" fill="#eef4f3" stroke="#d7cab8"/>
  <text x="274" y="154" font-family="Georgia, 'Times New Roman', serif" font-size="21" font-weight="700" fill="#211b16">2. Propose</text>
  <text x="274" y="184" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">Exploit + explore batch</text>
  <text x="274" y="208" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">Small candidate set</text>
  <text x="274" y="232" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">Current preference model</text>

  <rect x="472" y="120" width="180" height="118" rx="22" fill="#f6efe4" stroke="#d7cab8"/>
  <text x="492" y="154" font-family="Georgia, 'Times New Roman', serif" font-size="21" font-weight="700" fill="#211b16">3. Compare</text>
  <text x="492" y="184" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">Relative judgment</text>
  <text x="492" y="208" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">Winner, ranking, or score</text>
  <text x="492" y="232" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">Hidden-target oracle in experiments</text>

  <rect x="690" y="120" width="168" height="118" rx="22" fill="#eef4f3" stroke="#d7cab8"/>
  <text x="710" y="154" font-family="Georgia, 'Times New Roman', serif" font-size="21" font-weight="700" fill="#211b16">4. Update</text>
  <text x="710" y="184" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">Aggregate preference</text>
  <text x="710" y="208" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">Advance z_t → z_{t+1}</text>
  <text x="710" y="232" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#4c4338">Repeat until plateau or budget</text>

  <line x1="216" y1="178" x2="254" y2="178" stroke="#7a6c5b" stroke-width="3" marker-end="url(#arrow)"/>
  <line x1="434" y1="178" x2="472" y2="178" stroke="#7a6c5b" stroke-width="3" marker-end="url(#arrow)"/>
  <line x1="652" y1="178" x2="690" y2="178" stroke="#7a6c5b" stroke-width="3" marker-end="url(#arrow)"/>
  <path d="M 774 252 C 774 314, 170 314, 170 252" fill="none" stroke="#9f9384" stroke-width="3" stroke-dasharray="7 7" marker-end="url(#arrow)"/>

  <rect x="40" y="276" width="256" height="64" rx="16" fill="#fffdfa" stroke="#d7cab8"/>
  <text x="58" y="304" font-family="Georgia, 'Times New Roman', serif" font-size="18" font-weight="700" fill="#211b16">Design axes studied in the paper</text>
  <text x="58" y="329" font-family="Georgia, 'Times New Roman', serif" font-size="15" fill="#4c4338">steering representation · proposal policy · preference model · incumbent policy</text>

  <rect x="322" y="276" width="536" height="64" rx="16" fill="#fffdfa" stroke="#d7cab8"/>
  <text x="340" y="304" font-family="Georgia, 'Times New Roman', serif" font-size="18" font-weight="700" fill="#211b16">Optimization view</text>
  <text x="340" y="329" font-family="Georgia, 'Times New Roman', serif" font-size="15" fill="#4c4338">proposal batch ≈ stochastic search step, preference model ≈ local surrogate, update rule ≈ optimizer step</text>
</svg>
""".strip()


def _base_css() -> str:
    return """
:root{
  --bg:#f4eee4;
  --paper:#fffdfa;
  --ink:#201a15;
  --muted:#5b5144;
  --rule:#d8cab8;
  --warm:#f4ecdf;
  --cool:#eef4f3;
  --accent:#9b6b32;
}
*{box-sizing:border-box}
body{
  margin:0;
  background:var(--bg);
  color:var(--ink);
  font-family:Georgia,"Times New Roman",serif;
}
.page{
  width:1600px;
  min-height:900px;
  margin:0 auto;
  padding:28px;
}
.frame{
  background:var(--paper);
  border:1.5px solid var(--rule);
  border-radius:28px;
  box-shadow:0 16px 40px rgba(77,58,34,0.07);
  overflow:hidden;
}
.header{
  padding:26px 34px 20px;
  border-bottom:1px solid var(--rule);
}
.eyebrow{
  font-size:18px;
  color:#7b6d5e;
  margin-bottom:8px;
}
.title{
  font-size:44px;
  font-weight:700;
  line-height:1.05;
  margin:0 0 10px;
}
.subtitle{
  font-size:20px;
  line-height:1.45;
  color:var(--muted);
  margin:0;
  max-width:1100px;
}
.grid{
  padding:26px;
  display:grid;
  gap:24px;
}
.card{
  border:1.5px solid var(--rule);
  border-radius:24px;
  padding:22px 24px;
  background:#fffdfa;
}
.card h2{
  margin:0 0 12px;
  font-size:28px;
  line-height:1.15;
}
.card p, .card li{
  margin:0;
  font-size:18px;
  line-height:1.45;
  color:var(--muted);
}
.muted-note{
  font-size:15px;
  color:#7d7164;
}
.strip{
  width:100%;
  border:1px solid var(--rule);
  border-radius:18px;
  display:block;
  background:white;
}
.metrics{
  display:grid;
  gap:14px;
}
.metric{
  border:1px solid var(--rule);
  border-radius:18px;
  background:#faf7f1;
  padding:14px 16px;
}
.metric .label{
  font-size:16px;
  color:#7b6d5e;
  margin-bottom:6px;
}
.metric .value{
  font-size:26px;
  font-weight:700;
}
.chips{
  display:flex;
  flex-wrap:wrap;
  gap:10px;
}
.chip{
  border:1px solid var(--rule);
  border-radius:999px;
  padding:8px 14px;
  font-size:15px;
  background:#faf7f1;
  color:#594f43;
}
.tiny-table{
  width:100%;
  border-collapse:collapse;
}
.tiny-table th,.tiny-table td{
  border-top:1px solid var(--rule);
  padding:10px 8px;
  text-align:left;
  font-size:16px;
}
.tiny-table th{
  color:#7b6d5e;
  font-weight:600;
}
.footer{
  padding:0 34px 26px;
  color:#7b6d5e;
  font-size:15px;
}
""".strip()


def _html_document(*, title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{title}</title>
    <style>{_base_css()}</style>
  </head>
  <body>{body}</body>
</html>
"""


def _option_a_html(crops: dict[str, Path]) -> str:
    return _html_document(
        title="Visual Abstract Option A",
        body=f"""
<main class="page">
  <section class="frame">
    <header class="header">
      <div class="eyebrow">Visual abstract option A</div>
      <h1 class="title">StableSteering: preference-guided iterative refinement from a fixed prompt</h1>
      <p class="subtitle">The method treats refinement as repeated proposal, comparison, and steering-state update. The right column grounds the concept with a real hidden-target recovery example and the main quantitative highlight.</p>
    </header>
    <div class="grid" style="grid-template-columns: 1.3fr 0.9fr;">
      <div class="card" style="padding:18px 18px 14px;">{_pipeline_svg()}</div>
      <div style="display:grid; gap:24px;">
        <div class="card">
          <h2>Representative target-recovery run</h2>
          <img class="strip" src="{crops['bicycle'].name}" alt="Oracle steering progression strip">
          <p style="margin-top:12px;">A real run can move from a prompt-only baseline toward a visually closer image over repeated rounds without rewriting the prompt at every step.</p>
        </div>
        <div class="card">
          <h2>Main quantitative highlight</h2>
          <div class="metrics">
            <div class="metric"><div class="label">Repeated oracle study</div><div class="value">CLIP 0.828 → 0.881</div></div>
            <div class="metric"><div class="label">Independent image metric</div><div class="value">DINOv2 0.452 → 0.595</div></div>
            <div class="metric"><div class="label">Main interpretation</div><div class="value" style="font-size:22px;">Progress depends on proposal geometry, preference aggregation, and incumbent handling.</div></div>
          </div>
        </div>
      </div>
    </div>
    <div class="footer">Concept-first abstract with exact vector layout and experiment-derived imagery.</div>
  </section>
</main>
""".strip(),
    )


def _option_b_html(crops: dict[str, Path]) -> str:
    return _html_document(
        title="Visual Abstract Option B",
        body=f"""
<main class="page">
  <section class="frame">
    <header class="header">
      <div class="eyebrow">Visual abstract</div>
      <h1 class="title">StableSteering: iterative text-to-image refinement as a controllable search loop</h1>
      <p class="subtitle">The figure separates the problem setting, the method loop, and the evidence layer so the reader can parse the paper in one pass.</p>
    </header>
    <div class="grid" style="grid-template-columns: 0.78fr 1.08fr 0.94fr; align-items:stretch;">
      <div class="card" style="background:var(--warm);">
        <h2>Problem setting</h2>
        <p>Users often recognize a better image before they can express the corrective prompt. The target is latent, feedback is comparative, and the refinement burden is shifted away from repeated prompt rewriting.</p>
        <div class="chips" style="margin-top:16px;">
          <span class="chip">persistent prompt p</span>
          <span class="chip">hidden target y</span>
          <span class="chip">state z_t</span>
          <span class="chip">relative feedback</span>
        </div>
        <table class="tiny-table" style="margin-top:18px;">
          <tr><th>Input</th><td>caption only</td></tr>
          <tr><th>Feedback</th><td>winner / rank / score</td></tr>
          <tr><th>Goal</th><td>improve similarity over rounds</td></tr>
        </table>
      </div>
      <div class="card" style="padding:18px 18px 18px; display:grid; grid-template-rows:auto auto; gap:16px;">
        {_pipeline_svg()}
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">
          <div class="metric">
            <div class="label">Core variables</div>
            <div style="font-size:18px; line-height:1.45; color:#4c4338;"><strong>p</strong>: persistent prompt<br><strong>z_t</strong>: steering state<br><strong>f_t</strong>: relative feedback</div>
          </div>
          <div class="metric">
            <div class="label">Interpretation</div>
            <div style="font-size:18px; line-height:1.45; color:#4c4338;">Proposal batch ≈ stochastic search step; preference model ≈ local surrogate; update rule ≈ optimizer step.</div>
          </div>
        </div>
      </div>
      <div class="card" style="background:var(--cool);">
        <h2>Evidence layer</h2>
        <img class="strip" src="{crops['lake'].name}" alt="Lake trajectory strip" style="margin-bottom:12px;">
        <p style="margin-top:12px;">Example trajectory from the hidden-target protocol.</p>
        <div class="metrics" style="margin-top:16px;">
          <div class="metric"><div class="label">Repeated oracle</div><div class="value">9 runs · 90 rounds</div></div>
          <div class="metric"><div class="label">Recovery</div><div class="value">CLIP 0.828 → 0.881</div></div>
          <div class="metric"><div class="label">Cross-metric check</div><div class="value">DINOv2 0.452 → 0.595</div></div>
        </div>
      </div>
    </div>
    <div class="footer">Scientific overview: problem setting, iterative mechanism, and representative evidence.</div>
  </section>
</main>
""".strip(),
    )


def _option_c_svg(crops: dict[str, Path]) -> str:
    bicycle_data = base64.b64encode(crops["bicycle"].read_bytes()).decode("ascii")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900" role="img" aria-label="Visual abstract option C">
  <rect width="1600" height="900" fill="#f4eee4"/>
  <rect x="28" y="22" width="1544" height="856" rx="28" fill="#fffdfa" stroke="#d8cab8" stroke-width="2"/>
  <text x="64" y="78" font-family="Georgia, 'Times New Roman', serif" font-size="20" fill="#7b6d5e">Visual abstract option C</text>
  <text x="64" y="124" font-family="Georgia, 'Times New Roman', serif" font-size="48" font-weight="700" fill="#201a15">StableSteering as an iterative refinement framework</text>
  <text x="64" y="160" font-family="Georgia, 'Times New Roman', serif" font-size="22" fill="#5b5144">Prompt remains fixed; preference feedback updates a low-dimensional steering state over repeated rounds.</text>

  <rect x="64" y="210" width="640" height="278" rx="24" fill="#fbf8f1" stroke="#d8cab8"/>
  <text x="92" y="252" font-family="Georgia, 'Times New Roman', serif" font-size="30" font-weight="700" fill="#201a15">Concept</text>
  <text x="92" y="292" font-family="Georgia, 'Times New Roman', serif" font-size="18" fill="#5b5144">Refinement is treated as proposal, comparison, aggregation, and update rather than repeated prompt rewriting.</text>
  <rect x="96" y="330" width="140" height="90" rx="18" fill="#f6efe4" stroke="#d8cab8"/>
  <rect x="276" y="330" width="140" height="90" rx="18" fill="#eef4f3" stroke="#d8cab8"/>
  <rect x="456" y="330" width="140" height="90" rx="18" fill="#f6efe4" stroke="#d8cab8"/>
  <text x="119" y="368" font-family="Georgia, 'Times New Roman', serif" font-size="22" font-weight="700" fill="#201a15">Propose</text>
  <text x="121" y="396" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#5b5144">exploit + explore</text>
  <text x="300" y="368" font-family="Georgia, 'Times New Roman', serif" font-size="22" font-weight="700" fill="#201a15">Compare</text>
  <text x="309" y="396" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#5b5144">relative judgment</text>
  <text x="480" y="368" font-family="Georgia, 'Times New Roman', serif" font-size="22" font-weight="700" fill="#201a15">Update</text>
  <text x="470" y="396" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#5b5144">z_t → z_(t+1)</text>
  <path d="M236 375 H276 M416 375 H456" stroke="#7a6c5b" stroke-width="3" fill="none"/>
  <polygon points="272,375 262,369 262,381" fill="#7a6c5b"/>
  <polygon points="452,375 442,369 442,381" fill="#7a6c5b"/>

  <rect x="742" y="210" width="766" height="278" rx="24" fill="#fbf8f1" stroke="#d8cab8"/>
  <text x="770" y="252" font-family="Georgia, 'Times New Roman', serif" font-size="30" font-weight="700" fill="#201a15">Representative run</text>
  <image x="770" y="286" width="710" height="154" href="data:image/png;base64,{bicycle_data}" preserveAspectRatio="xMidYMid meet"/>
  <text x="770" y="466" font-family="Georgia, 'Times New Roman', serif" font-size="17" fill="#5b5144">Experiment-derived strip showing target, baseline, and best-so-far checkpoints.</text>

  <rect x="64" y="528" width="460" height="286" rx="24" fill="#f6efe4" stroke="#d8cab8"/>
  <text x="92" y="570" font-family="Georgia, 'Times New Roman', serif" font-size="30" font-weight="700" fill="#201a15">Problem</text>
  <text x="92" y="612" font-family="Georgia, 'Times New Roman', serif" font-size="20" fill="#5b5144">Users can often judge a better image more easily than they can write the exact corrective prompt.</text>
  <text x="92" y="668" font-family="Georgia, 'Times New Roman', serif" font-size="18" fill="#5b5144">This motivates an inference-time loop with comparative feedback rather than prompt rewriting alone.</text>

  <rect x="570" y="528" width="430" height="286" rx="24" fill="#eef4f3" stroke="#d8cab8"/>
  <text x="598" y="570" font-family="Georgia, 'Times New Roman', serif" font-size="30" font-weight="700" fill="#201a15">Main finding</text>
  <text x="598" y="624" font-family="Georgia, 'Times New Roman', serif" font-size="26" font-weight="700" fill="#201a15">CLIP 0.828 → 0.881</text>
  <text x="598" y="660" font-family="Georgia, 'Times New Roman', serif" font-size="26" font-weight="700" fill="#201a15">DINOv2 0.452 → 0.595</text>
  <text x="598" y="712" font-family="Georgia, 'Times New Roman', serif" font-size="18" fill="#5b5144">Progress is measurable, but it depends strongly on proposal geometry, preference aggregation, and incumbent policy.</text>

  <rect x="1046" y="528" width="462" height="286" rx="24" fill="#fbf8f1" stroke="#d8cab8"/>
  <text x="1074" y="570" font-family="Georgia, 'Times New Roman', serif" font-size="30" font-weight="700" fill="#201a15">Method axes</text>
  <text x="1074" y="624" font-family="Georgia, 'Times New Roman', serif" font-size="18" fill="#5b5144">• steering representation</text>
  <text x="1074" y="658" font-family="Georgia, 'Times New Roman', serif" font-size="18" fill="#5b5144">• proposal policy</text>
  <text x="1074" y="692" font-family="Georgia, 'Times New Roman', serif" font-size="18" fill="#5b5144">• preference model</text>
  <text x="1074" y="726" font-family="Georgia, 'Times New Roman', serif" font-size="18" fill="#5b5144">• incumbent management</text>
  <text x="1074" y="778" font-family="Georgia, 'Times New Roman', serif" font-size="16" fill="#7b6d5e">The paper compares concrete strategies within this shared loop.</text>
</svg>"""


def main() -> None:
    crops = _crop_rows()
    _write_text(OPTION_ROOT / "option_a.html", _option_a_html(crops))
    _write_text(OPTION_ROOT / "option_b.html", _option_b_html(crops))
    _write_text(OPTION_ROOT / "option_c.svg", _option_c_svg(crops))
    print(f"Wrote visual abstract options to {OPTION_ROOT}")


if __name__ == "__main__":
    main()
