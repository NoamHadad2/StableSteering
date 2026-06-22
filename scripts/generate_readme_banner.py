from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_PROMPT = (
    "Create a wide cinematic GitHub README banner for an open-source research "
    "project called StableSteering. The composition should visualize a user text "
    "prompt on the left evolving into several candidate image directions in the "
    "middle and a refined chosen direction on the right. Show subtle interface "
    "panels, diffusion-inspired light trails, latent-space contour lines, and a "
    "clean technical-editorial style. Use a warm copper, amber, teal, and deep "
    "graphite palette. Make it elegant, futuristic, and readable as a banner. "
    "No words or lettering inside the image. No watermark."
)


def _extract_image_bytes(payload: dict[str, Any]) -> bytes:
    for candidate in payload.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])
    raise ValueError("Gemini response did not include inline image data.")


def generate_banner(api_key: str, prompt: str, model: str, aspect_ratio: str, output: Path) -> Path:
    body = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "imageConfig": {
                "aspectRatio": aspect_ratio,
            }
        },
    }
    request = Request(
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
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

    image_bytes = _extract_image_bytes(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image_bytes)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a README banner with the Gemini image API.")
    parser.add_argument("--output", default="docs/assets/readme_banner.png", help="Output image path.")
    parser.add_argument("--model", default="gemini-2.5-flash-image", help="Gemini image model.")
    parser.add_argument("--aspect-ratio", default="16:9", help="Image aspect ratio.")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, help="Image prompt.")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is required.")

    output = Path(args.output)
    path = generate_banner(
        api_key=api_key,
        prompt=args.prompt,
        model=args.model,
        aspect_ratio=args.aspect_ratio,
        output=output,
    )
    print(path.resolve())


if __name__ == "__main__":
    main()
