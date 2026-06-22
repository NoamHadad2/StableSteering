from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ILLUSTRATIONS = {
    "steering_loop.png": (
        "Create a clean editorial technical illustration for a documentation page about "
        "interactive diffusion steering. Show a left-to-right loop: user text prompt, several "
        "candidate images, user preference selection, updated steering state, and a stronger next round. "
        "Use a warm copper, amber, teal, and graphite palette. Minimal UI panels, soft latent-space curves, "
        "high clarity, no text labels inside the image, no watermark."
    ),
    "system_architecture.png": (
        "Create a polished systems illustration for software documentation. Visualize a prompt-first "
        "image steering platform with layered blocks and subtle connections: frontend, API, orchestrator, "
        "generation engine on GPU, SQLite storage, and trace/report outputs. Use an elegant research-tool "
        "aesthetic, warm copper and teal highlights, light background, no words inside the image, no watermark."
    ),
    "trace_report.png": (
        "Create a documentation illustration showing why trace reports matter in an interactive AI system. "
        "Show a session timeline with candidate images, user choices, preference events, diagnostics, and a "
        "report panel coming together into one readable artifact. Editorial, clean, modern, warm technical palette, "
        "no text in the image, no watermark."
    ),
}


def _extract_image_bytes(payload: dict) -> bytes:
    for candidate in payload.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise RuntimeError("Gemini response did not contain inline image data.")


def generate_one(*, api_key: str, prompt: str, output_path: Path, model: str = "gemini-2.5-flash-image") -> None:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"imageConfig": {"aspectRatio": "16:9"}},
    }
    request = Request(
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API request failed with HTTP {exc.code}: {details}") from exc
    except URLError as exc:
        raise RuntimeError(f"Gemini API request failed: {exc.reason}") from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_extract_image_bytes(payload))


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is required.")

    output_root = Path("docs") / "assets" / "illustrations"
    for filename, prompt in ILLUSTRATIONS.items():
        path = output_root / filename
        generate_one(api_key=api_key, prompt=prompt, output_path=path)
        print(path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
