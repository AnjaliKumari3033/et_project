"""nim_client.py -- thin wrapper around the NVIDIA NIM vision-instruct endpoint.

Per the architecture plan (build-prompt section 3.4):
  - Cloud endpoint: https://integrate.api.nvidia.com/v1/chat/completions
  - Model: meta/llama-3.2-90b-vision-instruct
  - Free-tier rate limit: ~40 requests/min (request 200 RPM increase via NVIDIA forum).
  - Strategy:
      - ~1.5s spacing between calls (configurable via NIM_SPACING_SEC env var or CLI)
      - exponential backoff on HTTP 429 (max ~3 retries)
      - HTTP 5xx / connection errors: short retry, then give up on that one crop
        and continue so the batch survives a transient NIM outage
      - run as an unattended background batch (this module just exposes
        `transcribe_crop(image_bytes, is_table)` plus a `transcribe_batch()` helper
        that persists progress so a crash resumes mid-batch)
  - Auto-switch support: the API key is read from NVIDIA_API_KEY env var. If empty
        or requests fail with 401/403, the wrapper raises `NIMAuthError` so the
        caller can choose to skip vision ingestion on a GPU-less dev box.
  - Idempotent: callers can pass a job_id (e.g. pdf basename) and we persist a
        progress file at data/vision_progress.json so resuming after a crash
        skips already-successful crops.

This module is network-only; it does NOT touch ChromaDB or the graph. It only
returns text transcriptions (Markdown for tables; description for diagrams).
"""
from __future__ import annotations

import base64
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests

ROOT = Path(__file__).resolve().parent.parent
PROGRESS_PATH = ROOT / "data" / "vision_progress.json"

NIM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NIM_MODEL = "meta/llama-3.2-90b-vision-instruct"

DEFAULT_SPACING_SEC = 1.5        # ~40 RPM free tier -- spacing between consecutive requests
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 2.0       # exponential backoff: 1s, 2s, 4s ...
DEFAULT_TIMEOUT_SEC = 120

TABLE_PROMPT = (
    "Transcribe this table into Markdown, preserving rows and columns exactly. "
    "Preserve all numeric values and unit labels. Do NOT include any commentary, "
    "only the Markdown table."
)
DIAGRAM_PROMPT = (
    "Describe this technical diagram. Include: "
    "(1) the visible components and their labels, "
    "(2) the connections between them (wiring, pipes, flow paths), "
    "(3) direction of flow if shown, "
    "(4) any visible part numbers, port numbers, or annotation text. "
    "Keep the description under ~250 words and organized as labeled sections."
)


class NIMAuthError(RuntimeError):
    """Raised when API key is missing or NIM refuses authentication."""


class NIMTransientError(RuntimeError):
    """Raised when NIM returns 5xx / rate-limit errors after all retries."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_progress() -> dict[str, Any]:
    if PROGRESS_PATH.exists():
        try:
            return json.loads(PROGRESS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"completed": {}, "failed": []}
    return {"completed": {}, "failed": []}


def _save_progress(state: dict[str, Any]) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_PATH.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def _headers() -> dict[str, str]:
    key = os.environ.get("NVIDIA_API_KEY", "")
    if not key:
        raise NIMAuthError(
            "NVIDIA_API_KEY env var is empty. Vision pipeline cannot run. "
            "Set it to your NVIDIA developer key (free tier) or skip vision."
        )
    return {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _payload_from_image(image_bytes: bytes, prompt: str, max_tokens: int = 512) -> dict:
    b64 = base64.b64encode(image_bytes).decode()
    return {
        "model": NIM_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }],
        "max_tokens": max_tokens,
        "temperature": 0.2,  # transcription / description should be deterministic
    }


def _do_request(image_bytes: bytes, prompt: str, *, max_tokens: int, spacing_sec: float,
                max_retries: int, backoff_base: float, timeout_sec: int) -> str:
    """One HTTP POST with retry/backoff. Returns the assistant's content string.
    Raises NIMAuthError on auth failures, NIMTransientError after retries are
    exhausted."""
    payload = _payload_from_image(image_bytes, prompt, max_tokens=max_tokens)
    headers = _headers()
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(NIM_URL, headers=headers, json=payload, timeout=timeout_sec)
        except requests.RequestException as e:
            last_err = e
            sleep_for = backoff_base ** attempt
            time.sleep(sleep_for)
            continue

        if r.status_code in (401, 403):
            raise NIMAuthError(f"NIM auth failed: HTTP {r.status_code} {r.text[:200]}")

        if r.status_code == 429:
            # rate limit -> back off harder
            sleep_for = backoff_base ** (attempt + 1)
            time.sleep(sleep_for)
            last_err = RuntimeError(f"HTTP 429 {r.text[:120]}")
            continue

        if 500 <= r.status_code < 600:
            sleep_for = backoff_base ** attempt
            time.sleep(sleep_for)
            last_err = RuntimeError(f"HTTP {r.status_code} {r.text[:120]}")
            continue

        # 2xx success expected
        if r.status_code != 200:
            last_err = RuntimeError(f"unexpected HTTP {r.status_code} {r.text[:120]}")
            time.sleep(backoff_base ** attempt)
            continue

        try:
            content = r.json()["choices"][0]["message"]["content"]
            # Enforce spacing after success to honor free-tier RPM.
            time.sleep(spacing_sec)
            return content if isinstance(content, str) else str(content)
        except (KeyError, ValueError) as e:
            last_err = e
            time.sleep(spacing_sec)
            continue

    raise NIMTransientError(f"NIM call failed after {max_retries} retries: {last_err}")


def transcribe_crop(image_bytes: bytes, is_table: bool, *,
                    max_tokens: int = 512,
                    spacing_sec: float | None = None,
                    max_retries: int = DEFAULT_MAX_RETRIES,
                    backoff_base: float = DEFAULT_BACKOFF_BASE,
                    timeout_sec: int = DEFAULT_TIMEOUT_SEC) -> str:
    """Transcribe a single image crop. Returns Markdown table or diagram
    description depending on `is_table`.

    Raises:
        NIMAuthError       -- if NVIDIA_API_KEY is missing / rejected
        NIMTransientError  -- if all retries fail; caller chooses to keep going
    """
    spacing = float(spacing_sec) if spacing_sec is not None else float(os.environ.get("NIM_SPACING_SEC", DEFAULT_SPACING_SEC))
    prompt = TABLE_PROMPT if is_table else DIAGRAM_PROMPT
    return _do_request(
        image_bytes, prompt,
        max_tokens=max_tokens,
        spacing_sec=spacing,
        max_retries=max_retries,
        backoff_base=backoff_base,
        timeout_sec=timeout_sec,
    )


def transcribe_batch(crops: Iterable[dict], *, resume: bool = True,
                     spacing_sec: float | None = None,
                     max_retries: int = DEFAULT_MAX_RETRIES) -> dict[str, Any]:
    """Transcribe a batch of crops, persisting progress for resume.

    Each `crop` dict from the caller must have:
        - crop_id:        stable unique id (e.g. f"{pdf_stem}_p{pno:04d}_r{r}")
        - image_bytes:    bytes of the cropped PNG (for non-resume calls)
        - is_table:       bool
        - pdf_path:       source PDF rel path (for logging)
        - page:           page index (for logging)
        - region_index:   which region on the page (for logging)

    Returns a dict with keys: completed (id->text), failed (list of dict), counts.
    State is persisted after each crop so a crash resumes mid-batch.
    """
    spacing = float(spacing_sec) if spacing_sec is not None else float(os.environ.get("NIM_SPACING_SEC", DEFAULT_SPACING_SEC))
    state = _load_progress() if resume else {"completed": {}, "failed": []}
    print(f"[nim_client] batch start  spacing={spacing}s  resume={resume}  "
          f"already_complete={len(state['completed'])}  already_failed={len(state['failed'])}")

    n_done = 0
    n_skipped = 0
    n_failed = 0
    for crop in crops:
        crop_id = crop["crop_id"]
        if crop_id in state["completed"]:
            n_skipped += 1
            continue

        try:
            text = transcribe_crop(
                crop["image_bytes"],
                is_table=crop["is_table"],
                spacing_sec=spacing,
                max_retries=max_retries,
            )
            state["completed"][crop_id] = {
                "text": text,
                "is_table": crop["is_table"],
                "pdf_path": crop.get("pdf_path"),
                "page": crop.get("page"),
                "region_index": crop.get("region_index"),
                "transcribed_at": _now_iso(),
            }
            n_done += 1
            if n_done % 5 == 0:
                _save_progress(state)
                print(f"  [nim_client] {n_done} OK / {n_failed} FAILED / {n_skipped} skipped (resume cache)")
        except NIMAuthError as e:
            # Hard stop: not safe to keep going.
            print(f"  [nim_client] AUTH ERROR on {crop_id}: {e}")
            state["failed"].append({"crop_id": crop_id, "error": f"auth: {e}"})
            _save_progress(state)
            raise
        except NIMTransientError as e:
            print(f"  [nim_client] FAILED {crop_id}: {e}")
            state["failed"].append({"crop_id": crop_id, "error": str(e)})
            n_failed += 1
            # Keep going -- one bad crop shouldn't kill the batch.
            continue

    _save_progress(state)
    print(f"[nim_client] batch done.  completed={n_done}  failed={n_failed}  skipped={n_skipped}")
    return {
        "completed": state["completed"],
        "failed": state["failed"],
        "n_completed_this_run": n_done,
        "n_skipped_resume": n_skipped,
        "n_failed_this_run": n_failed,
    }


# ---------- Cloud fallback for the text reasoning LLM (auto-switch policy) ---------
# Per the locked-in architecture decision: on demo day, if the local Ollama
# `llama3.1:8b` errors or times out, transparently retry the same prompt against
# an NVIDIA NIM text model. This module exposes a minimal helper that the agent
# layer (later phase) can use. It is not exercised by this v1 ingestion layer.
TEXT_FALLBACK_MODEL = "meta/llama-3.1-8b-instruct"  # NIM free-tier equivalent

FALLBACK_SYSTEM_PROMPT = (
    "You are an industrial knowledge-intelligence assistant for NovaChem Industries. "
    "Answer concisely and always include the source filename for any factual claim. "
    "If you do not know or the context is insufficient, say so -- never fabricate."
)


def chat_completion(prompt: str, *,
                    system: str = FALLBACK_SYSTEM_PROMPT,
                    max_tokens: int = 768,
                    timeout_sec: int = 60,
                    max_retries: int = 2) -> str:
    """One-shot text completion through NIM. Used by the agent layer as an
    auto-switch fallback or as the primary text path if Ollama is unavailable.

    Same retry/backoff/auth posture as transcribe_crop."""
    payload = {
        "model": TEXT_FALLBACK_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    headers = _headers()
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(NIM_URL, headers=headers, json=payload, timeout=timeout_sec)
        except requests.RequestException as e:
            last_err = e
            time.sleep(DEFAULT_BACKOFF_BASE ** attempt)
            continue
        if r.status_code in (401, 403):
            raise NIMAuthError(f"auth failed: {r.status_code} {r.text[:120]}")
        if r.status_code == 429:
            time.sleep(DEFAULT_BACKOFF_BASE ** (attempt + 1))
            last_err = RuntimeError("429")
            continue
        if 500 <= r.status_code < 600:
            time.sleep(DEFAULT_BACKOFF_BASE ** attempt)
            last_err = RuntimeError(f"{r.status_code}")
            continue
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"]
        last_err = RuntimeError(f"{r.status_code} {r.text[:120]}")
    raise NIMTransientError(f"text completion failed: {last_err}")


if __name__ == "__main__":
    # Smoke-test the wrapper when invoked directly. Requires NVIDIA_API_KEY set.
    # Reads a small PNG from data/crops/_smoke.png if present, else prints the
    # configured state.
    if not os.environ.get("NVIDIA_API_KEY"):
        print("NVIDIA_API_KEY not set. Cannot run smoke test.")
        print("Set the env var and rerun, or invoke the wrapper programmatically.")
    else:
        sample = ROOT / "data" / "crops" / "_smoke.png"
        if sample.exists():
            print(f"Transcribing {sample.name} as a diagram...")
            txt = transcribe_crop(sample.read_bytes(), is_table=False)
            print("--- transcription ---")
            print(txt)
        else:
            print(f"No sample image at {sample.relative_to(ROOT)}. Drop a PNG there to run the smoke test.")
