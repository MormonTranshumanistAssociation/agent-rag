from __future__ import annotations

import argparse
import base64
import json
import math
import mimetypes
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Sequence
from urllib import error, request

MODEL = "gemini-3.1-pro-preview"
PROMPT_TEMPLATE = (
    "Transcribe all legible text from the attached scanned book pages in reading order and return the result as markdown. "
    "Preserve original spelling, punctuation, capitalization, and archaisms. "
    "If a page is part of a poem or other verse text, preserve verse lineation by ending each poetic line with `<br />` and preserve stanza breaks with blank lines between stanzas. "
    "If a page is prose, use normal markdown paragraphs and remove line-wrap artifacts. "
    "Do not modernize, summarize, explain, or silently regularize the text. "
    "For each page, begin with `[[page N]]` on its own line, where N is the page number provided below. "
    "Then provide only the markdown transcription for that page. "
    "Transcribe the pages in the exact order given below: {page_list}."
)


def pdf_page_count(pdf_path: Path) -> int:
    result = subprocess.run(["pdfinfo", str(pdf_path)], capture_output=True, text=True, check=True)
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    raise RuntimeError(f"Could not determine page count for {pdf_path}")


def render_page_to_jpeg(pdf_path: Path, page_number: int, out_path: Path, dpi: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "pdftoppm",
            "-jpeg",
            "-r",
            str(dpi),
            "-f",
            str(page_number),
            "-l",
            str(page_number),
            "-singlefile",
            str(pdf_path),
            str(out_path.with_suffix("")),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def gemini_batch_ocr(image_paths: Sequence[Path], page_numbers: Sequence[int], api_key: str) -> tuple[str, dict, str]:
    prompt = PROMPT_TEMPLATE.format(page_list=", ".join(str(n) for n in page_numbers))
    parts = [{"text": prompt}]
    for image_path in image_paths:
        mime_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        parts.append({"inline_data": {"mime_type": mime_type, "data": image_b64}})
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
    content_parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "".join(str(part.get("text", "")) for part in content_parts if isinstance(part, dict)).strip()
    if not text:
        raise RuntimeError("Gemini returned no transcription text")
    return prompt, body, text + "\n"


def chunked_pages(total_pages: int, pages_per_request: int) -> list[list[int]]:
    return [list(range(start, min(total_pages, start + pages_per_request - 1) + 1)) for start in range(1, total_pages + 1, pages_per_request)]


def transcribe_work(pdf_path: Path, output_dir: Path, source_url: str, api_key: str, *, pages_per_request: int, dpi: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    batches_dir = output_dir / "batches"
    batches_dir.mkdir(exist_ok=True)
    temp_dir = output_dir / ".tmp_images"
    temp_dir.mkdir(exist_ok=True)

    total_pages = pdf_page_count(pdf_path)
    batch_specs = chunked_pages(total_pages, pages_per_request)
    combined_parts = []
    batch_records = []

    for batch_index, page_numbers in enumerate(batch_specs, start=1):
        batch_path = batches_dir / f"batch-{batch_index:04d}.md"
        batch_meta_path = batches_dir / f"batch-{batch_index:04d}.json"
        if batch_path.exists() and batch_meta_path.exists():
            text = batch_path.read_text(encoding="utf-8").rstrip()
            combined_parts.append(text)
            batch_records.append(json.loads(batch_meta_path.read_text(encoding="utf-8")))
            continue

        image_paths = []
        for page_number in page_numbers:
            image_path = temp_dir / f"page-{page_number:04d}.jpg"
            if not image_path.exists():
                render_page_to_jpeg(pdf_path, page_number, image_path, dpi)
            image_paths.append(image_path)

        attempts = 0
        while True:
            attempts += 1
            try:
                prompt, response_body, text = gemini_batch_ocr(image_paths, page_numbers, api_key)
                batch_path.write_text(text, encoding="utf-8")
                record = {
                    "batch_index": batch_index,
                    "pages": page_numbers,
                    "file": str(batch_path.relative_to(output_dir)),
                    "response_file": str((batches_dir / f"batch-{batch_index:04d}.response.json").relative_to(output_dir)),
                }
                (batches_dir / f"batch-{batch_index:04d}.response.json").write_text(
                    json.dumps(response_body, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                batch_meta_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                if batch_index == 1:
                    (output_dir / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
                batch_records.append(record)
                combined_parts.append(text.rstrip())
                print(f"Transcribed {pdf_path.name} batch {batch_index}/{len(batch_specs)} pages {page_numbers[0]}-{page_numbers[-1]}", flush=True)
                break
            except error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code in {429, 500, 502, 503, 504} and attempts < 6:
                    wait = 5 * attempts
                    print(f"Retrying {pdf_path.name} batch {batch_index} after HTTP {exc.code}: {wait}s", flush=True)
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Gemini OCR failed for {pdf_path.name} batch {batch_index}: {exc.code} {detail}") from exc
            except Exception:
                if attempts < 6:
                    wait = 5 * attempts
                    print(f"Retrying {pdf_path.name} batch {batch_index} after generic failure: {wait}s", flush=True)
                    time.sleep(wait)
                    continue
                raise

    (output_dir / "combined.md").write_text("\n\n".join(combined_parts).rstrip() + "\n", encoding="utf-8")
    manifest = {
        "model": MODEL,
        "source_url": source_url,
        "source_pdf": str(pdf_path),
        "page_count": total_pages,
        "pages_per_request": pages_per_request,
        "dpi": dpi,
        "prompt_file": "prompt.txt",
        "combined_file": "combined.md",
        "batches": batch_records,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shutil.rmtree(temp_dir, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch direct Gemini OCR over a scanned PDF in multi-page requests.")
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--pages-per-request", type=int, default=6)
    parser.add_argument("--dpi", type=int, default=170)
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("Missing GEMINI_API_KEY in environment")

    transcribe_work(
        args.pdf_path,
        args.output_dir,
        args.source_url,
        api_key,
        pages_per_request=args.pages_per_request,
        dpi=args.dpi,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
