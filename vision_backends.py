"""
Vision-backend caption dispatcher for Ingredients Sheet Builder.

Goal: caption each panel image with a SWAPPABLE backend, all behind one
interface, so the user picks how they access a vision model:
    - "none"               -> no auto-caption; use the manually typed descriptions
    - "ollama"             -> local Ollama server (NSFW-safe, no key)  [FULLY WORKING]
    - "openai_compatible"  -> any OpenAI-style /v1/chat/completions vision endpoint
                              (Grok/xAI, LM Studio, oobabooga, OpenRouter, etc.) [FULLY WORKING]
    - "gemini"             -> Google Gemini API   [WORKING, but cloud = SFW only]
    - "anthropic"          -> Anthropic API       [WORKING, but cloud = SFW only]

Each backend function takes (image_b64, model, prompt, api_key, base_url, timeout)
and returns a caption string (or raises). Add a new backend = add one function
and one dispatch entry. That's the whole extension story.

NSFW NOTE: cloud vision APIs (gemini/anthropic/most openai_compatible hosted
providers) will refuse explicit imagery. For NSFW character work use "ollama"
with a local vision model (e.g. `ollama pull llava` or a qwen2-vl gguf).
"""

import base64
import io
import json
import urllib.request
import urllib.error


DEFAULT_CAPTION_PROMPT = (
    "Describe this single reference panel for a character/prop/location sheet in one "
    "concise phrase. Focus on identity-defining visual details (appearance, clothing, "
    "color, key features). No preamble, no 'this image shows', just the description."
)


def _pil_to_b64(pil_image, fmt="PNG"):
    buf = io.BytesIO()
    pil_image.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# --------------------------------------------------------------------------- #
# Backend: Ollama (local, NSFW-safe)                                          #
# --------------------------------------------------------------------------- #
def _caption_ollama(image_b64, model, prompt, api_key, base_url, timeout):
    url = (base_url or "http://localhost:11434").rstrip("/") + "/api/generate"
    payload = {
        "model": model or "llava",
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data.get("response") or "").strip()


# --------------------------------------------------------------------------- #
# Backend: OpenAI-compatible (Grok/xAI, LM Studio, OpenRouter, oobabooga, ...) #
# --------------------------------------------------------------------------- #
def _caption_openai_compatible(image_b64, model, prompt, api_key, base_url, timeout):
    # base_url should point at the server root, e.g.:
    #   https://api.x.ai/v1   (Grok)   |   http://localhost:1234/v1   (LM Studio)
    url = (base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
    payload = {
        "model": model or "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }
        ],
        "max_tokens": 300,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


# --------------------------------------------------------------------------- #
# Backend: Google Gemini  (cloud; SFW only)                                   #
# --------------------------------------------------------------------------- #
def _caption_gemini(image_b64, model, prompt, api_key, base_url, timeout):
    mdl = model or "gemini-2.0-flash"
    root = (base_url or "https://generativelanguage.googleapis.com").rstrip("/")
    url = f"{root}/v1beta/models/{mdl}:generateContent?key={api_key}"
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": image_b64}},
            ]
        }]
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


# --------------------------------------------------------------------------- #
# Backend: Anthropic  (cloud; SFW only)                                       #
# --------------------------------------------------------------------------- #
def _caption_anthropic(image_b64, model, prompt, api_key, base_url, timeout):
    root = (base_url or "https://api.anthropic.com").rstrip("/")
    url = f"{root}/v1/messages"
    payload = {
        "model": model or "claude-3-5-sonnet-20241022",
        "max_tokens": 300,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/png", "data": image_b64}},
                {"type": "text", "text": prompt},
            ],
        }],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key or "",
        "anthropic-version": "2023-06-01",
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["content"][0]["text"].strip()


_DISPATCH = {
    "ollama": _caption_ollama,
    "openai_compatible": _caption_openai_compatible,
    "gemini": _caption_gemini,
    "anthropic": _caption_anthropic,
}

BACKENDS = ["none", "ollama", "openai_compatible", "gemini", "anthropic"]


def caption_image(pil_image, backend, model="", prompt="", api_key="", base_url="", timeout=120):
    """
    Caption one PIL image with the chosen backend.
    Returns (caption_str, error_str_or_None). Never raises - failures come back
    as the error string so one bad panel doesn't kill the whole sheet.
    """
    if backend == "none" or pil_image is None:
        return "", None
    fn = _DISPATCH.get(backend)
    if fn is None:
        return "", f"unknown backend '{backend}'"
    use_prompt = prompt.strip() or DEFAULT_CAPTION_PROMPT
    try:
        b64 = _pil_to_b64(pil_image)
        cap = fn(b64, model, use_prompt, api_key, base_url, timeout)
        return cap, None
    except urllib.error.URLError as e:
        return "", f"{backend} connection error: {e}"
    except Exception as e:  # noqa: BLE001 - surface anything as a soft error
        return "", f"{backend} error: {e}"
