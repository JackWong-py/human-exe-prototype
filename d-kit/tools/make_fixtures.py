"""Build fixtures/rawdocs.json: the RawDoc pair for every BL_COMPARISON email.

Rough readers written only to unblock D. B and C's real readers replace them.
"""
import difflib, glob, json, re, subprocess, sys
from pathlib import Path
import openpyxl, docx, pytesseract
from PIL import Image

DATA = Path(sys.argv[1])
OUT = Path(sys.argv[2])


def doc_type(title):
    t = re.sub(r"\s+", " ", title.upper())
    if re.search(r"COMMERCIAL INVOICE|PACKING LIST|CERTIFICATE OF ORIGIN", t): return "OTHER"
    if "INSTRUCTION" in t: return "SI"
    if re.search(r"BILL\s*OF\s*LADING", t): return "BL"
    return "UNKNOWN"


def raw(path, title, pairs, error=None, noisy=False):
    return {"path": path, "doc_type": doc_type(title) if not error else "UNKNOWN", "title": title,
            "pairs": pairs, "error": error, "noisy": noisy}


def read_txt(rel):
    lines = (DATA / rel).read_text(errors="replace").splitlines()
    title = lines[0].strip() if lines else ""
    pairs, cur = [], None
    for n, ln in enumerate(lines[1:], 2):
        if not ln.strip() or set(ln.strip()) == {"="}: cur = None; continue
        m = re.match(r"^([A-Za-z][^:]{0,70}?):\s*(.*)$", ln) if not ln.startswith(" ") else None
        if m: cur = [m.group(1), m.group(2), f"line {n}"]; pairs.append(cur)
        elif cur is not None: cur[1] += " | " + ln.strip()
    return raw(rel, title, pairs)


def read_xlsx(rel):
    ws = openpyxl.load_workbook(DATA / rel, data_only=True).active
    rows = [(i, r) for i, r in enumerate(ws.iter_rows(values_only=True), 1) if any(c is not None for c in r)]
    title = " ".join(str(c) for c in rows[0][1] if c) + " " + (str(rows[1][1][0]) if len(rows) > 1 else "")
    pairs = [[str(r[0]), "" if r[1] is None else str(r[1]), f"row {i}"] for i, r in rows[1:] if r[0]]
    return raw(rel, title, pairs)


def read_docx(rel):
    d = docx.Document(DATA / rel)
    title = " ".join(p.text for p in d.paragraphs if p.text.strip())
    pairs = []
    for ti, t in enumerate(d.tables, 1):
        for ri, r in enumerate(t.rows, 1):
            c = [x.text for x in r.cells]
            if len(c) >= 2:
                pairs.append([c[0], " | ".join(x.strip() for x in c[1].split("\n") if x.strip()), f"table {ti} row {ri}"])
    return raw(rel, title, pairs)


LABELS = ["Shipper (Principal or Seller)", "Shipper/Exporter", "Shipper", "Exporter",
          "Consignee (Non-Negotiable)", "Consignee", "To the Order of",
          "Notify Party/Intermediate Consignee", "Notify Party", "Notify",
          "Port of Loading (POL)", "Port of Loading", "Load Port", "POL",
          "Port of Discharge (POD)", "Port of Discharge", "Discharge Port", "POD",
          "No. of Containers or Packages", "No. of Containers", "Total Containers", "Container Count",
          "TOTAL Gross Weight (KG)", "TOTAL Gross Wt (kgs)", "Gross Weight (KG)", "Gross Wt (kgs)", "GROSS WEIGHT"]
LABEL_RX = re.compile(r"^(" + "|".join(re.escape(l) for l in sorted(LABELS, key=len, reverse=True)) + r")(?=[\s:]|$)\s*:?\s*(.*)$", re.I)
ROW_RX = re.compile(r"^([A-Z]{4}\d{7})\s+(\d+'\w+)\s+.*?\s+([\d,]+)\s*$")


def read_pdf(rel):
    r = subprocess.run(["pdftotext", "-layout", str(DATA / rel), "-"], capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        img = subprocess.run(["pdfimages", "-list", str(DATA / rel)], capture_output=True, text=True).stdout.strip().splitlines()
        if r.returncode == 0 and len(img) > 2: return read_scan(rel)
        return raw(rel, "", [], error="unreadable")
    lines = r.stdout.splitlines()
    title = next((l.strip() for l in lines if l.strip()), "")
    pairs, cur, rows = [], None, []
    for n, ln in enumerate(lines, 1):
        s = ln.strip()
        if not s: cur = None; continue
        m = ROW_RX.match(s)
        if m: rows.append((m.group(2), int(m.group(3).replace(",", "")))); cur = None; continue
        m = LABEL_RX.match(s) if not ln.startswith("   ") else None
        if m:
            cur = [m.group(1), m.group(2).strip(), f"page 1 line {n}"]; pairs.append(cur)
        elif cur is not None and ln.startswith(" "):
            cur[1] = (cur[1] + " | " + s) if cur[1] else s
        else: cur = None
    labels = {p[0].lower() for p in pairs}
    if rows and not any("container" in l for l in labels):
        pairs.append(["Container Count", f"{len(rows)} x {rows[0][0]}", "container table roll-up"])
    if rows and not any("gross" in l for l in labels):
        pairs.append(["Gross Weight (KG)", f"{sum(w for _, w in rows):,}", "container table roll-up"])
    return raw(rel, title, pairs)


KEYS = {"shipper": "Shipper", "consignee": "Consignee", "notify": "Notify Party", "portofloading": "Port of Loading",
        "portofdischarge": "Port of Discharge", "containers": "Container Count", "grossweight": "Gross Weight (KG)"}


def read_scan(rel):
    subprocess.run(["pdfimages", "-png", str(DATA / rel), "/tmp/_scan"], check=True)
    img = Image.open(sorted(glob.glob("/tmp/_scan-*.png"))[0]).convert("L")
    w, h = img.size
    img = img.crop((0, 0, w, int(h * 0.45))).resize((w * 3, int(h * 0.45) * 3), Image.LANCZOS).point(lambda x: 255 if x > 170 else 0)
    for f in glob.glob("/tmp/_scan-*.png"): Path(f).unlink()
    text = pytesseract.image_to_string(img, config="--psm 6")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    pairs = []
    for n, ln in enumerate(lines[1:], 2):
        toks = ln.split(); best = (0, None, 0)
        for k in (1, 2, 3):
            cand = re.sub(r"[^a-z]", "", " ".join(toks[:k]).lower())
            for key in KEYS:
                ratio = difflib.SequenceMatcher(None, cand, key).ratio()
                if ratio > best[0]: best = (ratio, key, k)
        if best[0] >= 0.8:
            value = " ".join(toks[best[2]:]).lstrip(":. ").strip()
            pairs.append([KEYS[best[1]], value, f"OCR line {n}: {ln}"])
    return raw(rel, lines[0] if lines else "", pairs, noisy=True)


def read_any(rel):
    ext = rel.rsplit(".", 1)[-1].lower()
    return {"txt": read_txt, "xlsx": read_xlsx, "docx": read_docx, "pdf": read_pdf}[ext](rel)


BL_PHRASE = re.compile(r"compare the si and (the )?draft bl|check the draft bl against the si|(attached|find attached)( are)?( the)? (si|shipping instruction) and (the )?(draft (bl|bill of lading)|bill of lading)|attached si and draft bl|(si) and the (packing list|certificate of origin|commercial invoice)", re.I)
fixtures = {}
for p in sorted(glob.glob(str(DATA / "inbox/email_*.json"))):
    e = json.load(open(p))
    if not BL_PHRASE.search(e["body"]): continue
    si = bl = None
    for a in e["attachments"]:
        d = read_any(a)
        if a.upper().find("_SI.") >= 0: si = d
        elif a.upper().find("_BL.") >= 0: bl = d
    fixtures[e["email_id"]] = {"si": si, "bl": bl}
OUT.parent.mkdir(exist_ok=True)
json.dump(fixtures, open(OUT, "w"), indent=1, ensure_ascii=False)
print(len(fixtures), "emails; both docs:", sum(1 for v in fixtures.values() if v["si"] and v["bl"]))
