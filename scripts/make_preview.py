#!/usr/bin/env python3
"""Generate docs/takoron_preview.html from opentama.art.

The preview shows every Takoron stage in colour, rendered the same way
`opentama show` renders in a truecolor terminal: each terminal cell is
an upper-half pixel over a lower-half pixel, drawn here as a hard-stop
CSS gradient so the cells are seamless (no inter-cell gaps).

Usage:
    python scripts/make_preview.py
"""

from __future__ import annotations

import pathlib
import sys

# Allow running from the repo root without installing.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from opentama import art  # noqa: E402

STAGES = ["egg", "baby", "child", "teen", "adult", "elder"]
LABELS = {
    "egg": "たまご",
    "baby": "あかちゃん (ω)",
    "child": "こども",
    "teen": "ティーン",
    "adult": "おとな",
    "elder": "ご長老",
}


def _rgb(c):
    return f"rgb({c[0]},{c[1]},{c[2]})" if c else "transparent"


def _cell(top_key: str, bot_key: str) -> str:
    top = _rgb(art.PALETTE.get(top_key))
    bot = _rgb(art.PALETTE.get(bot_key))
    return f'<i style="background:linear-gradient({top} 0 50%,{bot} 50% 100%)"></i>'


def _grid_html(stage: str) -> str:
    grid = art.GRIDS[stage]
    rows = []
    for i in range(0, len(grid), 2):
        top = grid[i]
        bot = grid[i + 1] if i + 1 < len(grid) else "." * len(top)
        rows.append(
            '<div class="r">'
            + "".join(_cell(t, b) for t, b in zip(top, bot))
            + "</div>"
        )
    return "".join(rows)


def build_html() -> str:
    cards = "".join(
        f'<figure class="card"><div class="screen">{_grid_html(s)}</div>'
        f"<figcaption>{LABELS[s]}<br><span>{s}</span></figcaption></figure>"
        for s in STAGES
    )
    return f"""<!doctype html><html lang=ja><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>タコロン — OpenTama</title>
<style>
  :root{{--cell:14px}}
  *{{box-sizing:border-box}}
  body{{margin:0;padding:32px;background:#0d1117;color:#e6edf3;
       font-family:-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}}
  h1{{font-size:22px;margin:0 0 4px}}
  .sub{{color:#8b949e;font-size:13px;margin:0 0 28px}}
  .grid{{display:flex;flex-wrap:wrap;gap:22px}}
  .card{{margin:0;background:#161b22;border:1px solid #30363d;border-radius:14px;
        padding:18px 18px 12px;box-shadow:0 6px 20px rgba(0,0,0,.35)}}
  .screen{{background:#000;border-radius:8px;padding:14px;display:inline-block;
          line-height:0;font-size:0}}
  .r{{display:block;height:var(--cell);white-space:nowrap}}
  .r i{{display:inline-block;width:var(--cell);height:var(--cell);vertical-align:top}}
  figcaption{{text-align:center;margin-top:12px;font-size:13px;color:#e6edf3}}
  figcaption span{{color:#8b949e;font-size:11px;letter-spacing:.08em;text-transform:uppercase}}
</style>
<h1>タコロン — OpenTama のドット絵</h1>
<p class=sub>truecolor 端末では <code>opentama show</code> がこの色そのまま出ます。あかちゃんだけ ω の口、こども以降は開いた口。</p>
<div class="grid">{cards}</div>
</html>"""


def main() -> int:
    out = pathlib.Path(__file__).resolve().parents[1] / "docs" / "takoron_preview.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_html(), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
