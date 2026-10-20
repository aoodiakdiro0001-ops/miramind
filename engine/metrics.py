"""Objective drawing metrics — facts only (no hidden-meaning claims).

Computes verifiable properties of a child's drawing: dominant palette,
ink coverage, stroke-density proxy, brightness, and where the ink sits on the
page (thirds). Interpretation happens elsewhere — as reflective questions,
never as diagnostic statements.
"""
import os
import time
from typing import Any, Dict, Optional


def drawing_metrics(image_bytes: bytes, media_dir: str = None, name: str = "drawing") -> Dict[str, Any]:
    out: Dict[str, Any] = {"name": name, "bytes": len(image_bytes), "ts": int(time.time())}
    saved_to: Optional[str] = None
    try:
        from PIL import Image  # type: ignore
        import io
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        out["width"], out["height"] = img.size
        small = img.resize((64, 64))
        px = list(small.getdata())
        n = len(px)
        # palette buckets (4 bits/channel)
        buckets: Dict[tuple, int] = {}
        for r, g, b in px:
            buckets[(r >> 5, g >> 5, b >> 5)] = buckets.get((r >> 5, g >> 5, b >> 5), 0) + 1
        top = sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)[:6]
        out["palette"] = [
            {"rgb": "#%02x%02x%02x" % (k[0] * 32 + 16, k[1] * 32 + 16, k[2] * 32 + 16),
             "share": round(v / n, 3)}
            for k, v in top
        ]
        # brightness / colorfulness (mean HSV)
        hsv = list(small.convert("HSV").getdata())
        out["brightness"] = round(sum(p[2] for p in hsv) / n / 255, 3)
        out["colorfulness"] = round(sum(p[1] for p in hsv) / n / 255, 3)
        # ink coverage: pixels far from the whitest bucket (assumes light paper)
        max_share_key = top[0][0]
        ink = sum(1 for r, g, b in px
                  if (r >> 5, g >> 5, b >> 5) != max_share_key)
        out["ink_coverage"] = round(ink / n, 3)
        # ink distribution across thirds (rows)
        thirds = [0, 0, 0]
        for i, (r, g, b) in enumerate(px):
            if (r >> 5, g >> 5, b >> 5) != max_share_key:
                band = min(2, i // (n // 3)) if i < n else 2
                thirds[band] += 1
        total_ink = sum(thirds) or 1
        out["ink_thirds"] = [round(t / total_ink, 3) for t in thirds]
        # stroke-density proxy: color changes along mid rows
        mid_rows = [img.crop((0, y, img.width, y + 1)).convert("RGB")
                    .getdata() for y in (int(img.height * .33), int(img.height * .55))]
        changes = 0
        samples = 0
        for row in mid_rows:
            prev = None
            for p in row:
                if prev is not None:
                    d = abs(p[0] - prev[0]) + abs(p[1] - prev[1]) + abs(p[2] - prev[2])
                    if d > 90:
                        changes += 1
                    samples += 1
                prev = p
        out["stroke_density"] = round(changes / max(1, samples), 3)
        pil_ok = True
    except Exception as e:
        out["error"] = str(e)[:100]
        return out
    # persist locally (never uploaded anywhere)
    try:
        d = media_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "drawings")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, f"{int(time.time() * 1000)}_{out['name'][:30]}.png")
        with open(path, "wb") as fh:
            fh.write(image_bytes)
        saved_to = path
    except Exception:
        pass
    out["saved_locally"] = saved_to
    return out
