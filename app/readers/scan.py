"""Scanned (image-only) PDFs -> RawDoc with noisy=True. Owned by C.

    read_scan(path, data, client=None) -> RawDoc

Pipeline: render the page at the scan's own resolution -> crop to the text -> upscale to about
450 dpi -> black and white -> Tesseract -> fuzzy-match each line's label to one of the 7 fields.
The pairs use the canonical labels ("Port of Loading", ...) that D's mapping understands.

Optional vision fallback (a Gemini model reads the page image). It runs only when it is
configured AND OCR came back incomplete or unsure. Configuration, in .env:

    GEMINI_API_KEY=...             the key (never commit it)
    GEMINI_MODEL=...               a model name that works with your key
    SCAN_VISION=off|fallback|always   default "fallback"; "off" never calls the model

Calls to the model never raise into the pipeline: a failure adds a "Reader note" pair and the
OCR result is returned.
"""
import difflib
import io
import json
import os
import re
from statistics import mean

import pdfplumber
import pytesseract
from PIL import Image

from ..contracts import CANONICAL_LABELS, FIELDS, RawDoc
from .common import detect_doc_type, unreadable

try:                                # so TESSERACT_CMD, GEMINI_API_KEY, ... in .env work in tests and scripts too
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:                 # pragma: no cover
    pass

TARGET_DPI = 450         # Tesseract reads best when the text is roughly this sharp
THRESHOLD = 170          # darker than this is text; the faint "scanned copy" watermark is lighter
LABEL_MATCH = 0.80       # how close a line's first words must be to a known label (0..1)
MIN_CONFIDENCE = 60      # mean OCR confidence below this counts as "unsure"

# Label spellings, letters only, mapped to the 7 fields. OCR damages labels ("Portof", "Notity").
LABELS = {
    "shipper": "shipper", "exporter": "shipper", "shipperexporter": "shipper",
    "consignee": "consignee", "totheorderof": "consignee",
    "notify": "notify_party", "notifyparty": "notify_party",
    "portofloading": "port_of_loading", "loadport": "port_of_loading", "loadingport": "port_of_loading",
    "portofdischarge": "port_of_discharge", "dischargeport": "port_of_discharge",
    "containers": "container_count", "totalcontainers": "container_count", "containercount": "container_count",
    "noofcontainers": "container_count", "noofcontainersorpackages": "container_count",
    "grossweight": "gross_weight_kg", "grosswt": "gross_weight_kg", "grossweightkg": "gross_weight_kg",
}
SHORT_LABELS = {"pol": "port_of_loading", "pod": "port_of_discharge"}    # too short to match loosely


class OcrUnavailable(RuntimeError):
    """The Tesseract program is not installed. Raised (not hidden) so the team notices at once."""


# ---- rendering and OCR ------------------------------------------------------
def _render(page):
    """Render at the embedded image's own resolution, so we see the scan pixel for pixel."""
    images = page.images
    src = images[0].get("srcsize") if images else None
    dpi = src[0] / (page.width / 72) if src and src[0] else 150
    return page.to_image(resolution=dpi).original, dpi


def _prepare(img, dpi):
    """Crop to the dark text, upscale, and make it black and white. None if the page is blank."""
    gray = img.convert("L")
    box = gray.point(lambda v: 255 if v < THRESHOLD else 0).getbbox()
    if box is None:
        return None
    margin = 10
    gray = gray.crop((max(box[0] - margin, 0), max(box[1] - margin, 0),
                      min(box[2] + margin, gray.width), min(box[3] + margin, gray.height)))
    scale = min(max(TARGET_DPI / dpi, 1.0), 4.0)
    gray = gray.resize((int(gray.width * scale), int(gray.height * scale)), Image.LANCZOS)
    return gray.point(lambda v: 255 if v > THRESHOLD else 0)


def _ocr_lines(img):
    """[(text, mean confidence)] per printed line, top to bottom."""
    cmd = os.environ.get("TESSERACT_CMD")
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    try:
        data = pytesseract.image_to_data(img, config="--psm 6", output_type=pytesseract.Output.DICT)
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrUnavailable(
            "Tesseract OCR is not installed. Linux: sudo apt install tesseract-ocr. "
            "Windows: install it and set TESSERACT_CMD in .env to the full path of tesseract.exe."
        ) from exc
    lines = {}
    for i, text in enumerate(data["text"]):
        if text.strip():
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append((text, float(data["conf"][i])))
    return [(" ".join(t for t, _ in words), mean(c for _, c in words if c >= 0) if any(c >= 0 for _, c in words) else 0.0)
            for _, words in sorted(lines.items())]


def _match_label(tokens):
    """Best (score, field, words used) for the start of a line, or (0, None, 0)."""
    best = (0.0, None, 0)
    for k in range(1, 6):
        if k > len(tokens) or re.search(r"\d", tokens[k - 1]):
            break                       # labels never contain digits: "Containers 6 x" is label + value
        cand = re.sub(r"[^a-z]", "", " ".join(tokens[:k]).lower())
        if not cand:
            continue
        if cand in SHORT_LABELS:
            best = max(best, (1.0, SHORT_LABELS[cand], k), key=lambda b: (b[0], b[2]))
        for label, field in LABELS.items():
            score = difflib.SequenceMatcher(None, cand, label).ratio()
            if score > best[0] or (score == best[0] and k > best[2]):
                best = (score, field, k)
    return best if best[0] >= LABEL_MATCH else (0.0, None, 0)


def _pairs_from_lines(lines, first_line_no=1):
    pairs = []
    for n, (text, conf) in enumerate(lines, first_line_no):
        score, field, used = _match_label(text.split())
        if field is None:
            continue
        value = " ".join(text.split()[used:]).lstrip(":. ").strip()
        pairs.append([CANONICAL_LABELS[field], value, f"OCR line {n} (confidence {conf:.0f}): {text}"])
    return pairs


# ---- optional vision fallback -----------------------------------------------
PROMPT = (
    "You are reading a scanned shipping document (a Shipping Instruction or a draft Bill of Lading). "
    "Return ONLY a JSON object, no markdown, in exactly this shape:\n"
    '{"title": "...", "shipper": "...", "consignee": "...", "notify_party": "...", "port_of_loading": "...", '
    '"port_of_discharge": "...", "container_count": "...", "gross_weight_kg": "..."}\n'
    '"title" is the heading printed at the top of the page. '
    "Copy each value exactly as printed (for example \"6 x 40'HC\" and \"128,544 KG\"). "
    "Use null for a value you cannot read. Do not guess."
)


def _vision_client():
    if not (os.environ.get("GEMINI_API_KEY") and os.environ.get("GEMINI_MODEL")):
        return None
    try:
        from google import genai
        return genai.Client()
    except ImportError:
        return None


def _vision_pairs(images, client):
    """Ask the model to read the page image(s). Returns ([label, value, evidence] pairs, title)."""
    model = os.environ.get("GEMINI_MODEL", "")
    found, title = {}, ""
    for image in images:
        response = client.models.generate_content(model=model, contents=[PROMPT, image])
        text = re.sub(r"^```(?:json)?|```$", "", (response.text or "").strip(), flags=re.M).strip()
        data = json.loads(text)
        title = title or str(data.get("title") or "")
        for field in FIELDS:
            value = data.get(field)
            if value not in (None, "") and field not in found:
                found[field] = str(value)
    return [[CANONICAL_LABELS[f], v, "vision model"] for f, v in found.items()], title


# ---- entry point ------------------------------------------------------------
def read_scan(path, data, client=None):
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
        pages = list(pdf.pages)
    except Exception as exc:                                  # noqa: BLE001 - same rule as read_pdf
        return unreadable(path, f"The PDF cannot be opened ({type(exc).__name__})")

    mode = os.environ.get("SCAN_VISION", "fallback").lower()
    client = client or (_vision_client() if mode != "off" else None)
    title, ocr_pairs, confidences, originals, ocr_error = "", [], [], [], None
    with pdf:
        for page in pages:
            img, dpi = _render(page)
            prepared = _prepare(img, dpi)
            if prepared is None:
                continue
            originals.append(img)
            try:
                lines = _ocr_lines(prepared)
            except OcrUnavailable as exc:
                ocr_error = exc
                break
            if lines and not title:
                title, lines = lines[0][0], lines[1:]
            ocr_pairs += _pairs_from_lines(lines, first_line_no=2 if not ocr_pairs else 1)
            confidences += [c for _, c in lines]

    if ocr_error is not None and client is None:
        raise ocr_error
    if not originals:
        return unreadable(path, "The scanned page is blank")

    fields_seen = {p[0] for p in ocr_pairs}
    unsure = ocr_error is not None or len(fields_seen) < len(FIELDS) or (confidences and mean(confidences) < MIN_CONFIDENCE)
    pairs = ocr_pairs
    if client is not None and mode != "off" and (mode == "always" or unsure):
        try:
            vision, vision_title = _vision_pairs(originals, client)
            pairs = vision + ocr_pairs                      # vision first: the first pair for a field wins
            title = title or vision_title
        except Exception as exc:                            # noqa: BLE001 - never break the pipeline on a model failure
            if ocr_error is not None:
                raise ocr_error                             # no OCR and no vision: make the problem visible
            pairs = ocr_pairs + [["Reader note", f"The vision model failed ({type(exc).__name__})", "scan"]]
    return RawDoc(path=path, doc_type=detect_doc_type(title, fuzzy=True), title=title, pairs=pairs, noisy=True)
