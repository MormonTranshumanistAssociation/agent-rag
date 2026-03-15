from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import time
from pathlib import Path
from urllib import error, request

MODEL = "gemini-3.1-pro-preview"
PROMPT_TEMPLATE = (
    "Transcribe all legible text from the attached scanned book page images in reading order and return the result as markdown. "
    "Preserve original spelling, punctuation, capitalization, and archaisms. "
    "If any page is part of a poem or other verse text, preserve verse lineation by ending each poetic line with `<br />` and preserve stanza breaks with blank lines between stanzas. "
    "If the pages are prose, use normal markdown paragraphs and remove line-wrap artifacts. "
    "Do not modernize, summarize, explain, or silently regularize the text. "
    "For each page, begin with `[[page N]]` on its own line, where N is the page number provided below. "
    "Return only the markdown transcription. "
    "This batch covers original page numbers: {page_list}."
)


def parse_page_number(path: Path) -> int:
    stem = path.stem
    if "page-" in stem:
        return int(stem.rsplit("page-", 1)[1])
    raise ValueError(f"Could not parse page number from {path.name}")


def gemini_batch_ocr(image_paths: list[Path], page_numbers: list[int], api_key: str) -> tuple[str, dict, str]:
    prompt = PROMPT_TEMPLATE.format(page_list=", ".join(str(n) for n in page_numbers))
    parts = [{"text": prompt}]
    for image_path in image_paths:
        mime_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
        parts.append(
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(image_path.read_bytes()).decode("ascii"),
                }
            }
        )
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": 0},
    }
    req = request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={api_key}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=600) as response:
        body = json.loads(response.read().decode("utf-8"))
    text = "".join(part.get("text", "") for part in body.get("candidates", [{}])[0].get("content", {}).get("parts", []) if isinstance(part, dict)).strip()
    if not text:
        raise RuntimeError("Gemini returned no transcription text")
    return prompt, body, text + "\n"


def chunked(items: list[Path], size: int) -> list[list[Path]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def transcribe_dir(image_dir: Path, output_dir: Path, source_url: str, api_key: str, *, batch_size: int) -> None:
    images = sorted(image_dir.glob("*.jpg"))
    if not images:
        raise RuntimeError(f"No .jpg files found in {image_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    batches_dir = output_dir / "batches"
    batches_dir.mkdir(exist_ok=True)

    combined_parts = []
    batch_records = []
    prompt_written = False
    for batch_index, batch_images in enumerate(chunked(images, batch_size), start=1):
        page_numbers = [parse_page_number(path) for path in batch_images]
        batch_md = batches_dir / f"batch-{batch_index:03d}.md"
        batch_json = batches_dir / f"batch-{batch_index:03d}.json"
        batch_resp = batches_dir / f"batch-{batch_index:03d}.response.json"
        if batch_md.exists() and batch_json.exists() and batch_resp.exists():
            combined_parts.append(batch_md.read_text(encoding="utf-8").rstrip())
            batch_records.append(json.loads(batch_json.read_text(encoding="utf-8")))
            continue
        attempts = 0
        while True:
            attempts += 1
            try:
                prompt, body, text = gemini_batch_ocr(batch_images, page_numbers, api_key)
                batch_md.write_text(text, encoding="utf-8")
                batch_resp.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                record = {
                    "batch_index": batch_index,
                    "pages": page_numbers,
                    "file": str(batch_md.relative_to(output_dir)),
                }
                batch_json.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                batch_records.append(record)
                combined_parts.append(text.rstrip())
                if not prompt_written:
                    (output_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
                    prompt_written = True
                print(f"{output_dir.name}: batch {batch_index} pages {page_numbers[0]}-{page_numbers[-1]} done", flush=True)
                break
            except error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code in {429, 500, 502, 503, 504} and attempts < 6:
                    wait = 5 * attempts
                    print(f"{output_dir.name}: retry batch {batch_index} after HTTP {exc.code} in {wait}s", flush=True)
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Gemini failed on {output_dir.name} batch {batch_index}: {exc.code} {detail}") from exc

    (output_dir / "combined.md").write_text("\n\n".join(combined_parts).rstrip() + "\n", encoding="utf-8")
    manifest = {
        "model": MODEL,
        "source_url": source_url,
        "source_dir": str(image_dir),
        "page_count": len(images),
        "batch_size": batch_size,
        "prompt_file": "prompt.txt",
        "combined_file": "combined.md",
        "batches": batch_records,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch direct Gemini OCR over scanned page images.")
    parser.add_argument("image_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--batch-size", type=int, default=6)
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Missing GEMINI_API_KEY in environment")

    transcribe_dir(args.image_dir, args.output_dir, args.source_url, api_key, batch_size=args.batch_size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
