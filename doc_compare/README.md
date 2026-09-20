# SI / BL mapping, normalization, comparison and decision

## Run

```bash
python -m pip install pytest
pytest -q
```

## Core API

```python
from models import RawDoc
from pipeline import evaluate_pair

si = RawDoc(
    doc_type="SI",
    fields={
        "Shipper": "ACME LTD",
        "Consignee": "BUYER LIMITED",
        "Port of Loading": "Shanghai, CNSHA",
        "Port of Discharge": "Rotterdam, NLRTM",
        "Containers": "2 x 40HC",
        "Gross Weight": "12,345 KG",
        "Description": "Frozen Beef",
    },
)

bl = RawDoc(
    doc_type="BL",
    fields={
        "Shipper": "ACME LIMITED",
        "Consignee": "BUYER LTD",
        "Port of Loading": "Shanghai, CN-SHA",
        "Port of Discharge": "Rotterdam, NL-RTM",
        "Containers": "2 containers",
        "Gross Weight": "12345 kg",
        "Description": "Frozen Beef",
    },
)

print(evaluate_pair(si, bl))
```

## Decision precedence

1. missing attachment -> `NEEDS_REVIEW / missing_attachment`
2. wrong document type -> `NEEDS_REVIEW / wrong_doc_type`
3. document error -> `NEEDS_REVIEW / unreadable`
4. missing value -> `NEEDS_REVIEW / missing_value`
5. comparison -> `MISMATCH` or `OK`

## Eyeballing first 30 mismatches

Use:

```python
from report import print_first_mismatches

pairs = [
    ("013", si_013, bl_013),
    # ...
]

print_first_mismatches(pairs, limit=30)
```

`pairs` should contain `(case_id, RawDoc, RawDoc)` tuples.


## Pointing the project at the Windows dataset

If the extracted attachments directory is:

```text
C:\Users\User\AppData\Local\Temp\8ffd9642-a15f-4e3f-86b2-7f98c98d79e3\_drive-download-20260918T101927Z-1-001.zip.9e3\sdoc-hackathon-docker.zip\data_v2\attachments
```

run:

```powershell
python inspect_dataset.py "C:\Users\User\AppData\Local\Temp\8ffd9642-a15f-4e3f-86b2-7f98c98d79e3\_drive-download-20260918T101927Z-1-001.zip.9e3\sdoc-hackathon-docker.zip\data_v2\attachments"
```

If Windows says the path does not exist, you are probably looking at a folder
inside a ZIP archive through Explorer. Extract `sdoc-hackathon-docker.zip`
first, then use the actual extracted path:

```powershell
python inspect_dataset.py "C:\path\to\sdoc-hackathon-docker\data_v2\attachments"
```


## Read the actual attachment files

Install readers:

```powershell
python -m pip install -r requirements.txt
```

Then run the real dataset:

```powershell
python run_dataset.py "C:\Users\User\AppData\Local\Temp\8ffd9642-a15f-4e3f-86b2-7f98c98d79e3\_drive-download-20260918T101927Z-1-001.zip.9e3\sdoc-hackathon-docker.zip\data_v2\attachments" --json results.json
```

The runner now:

1. opens every attachment file,
2. extracts document text,
3. detects SI or BL,
4. extracts the seven relevant fields,
5. maps and normalizes them,
6. compares SI against BL,
7. applies the required decision precedence,
8. prints the first 30 mismatches,
9. writes all results to JSON when `--json` is supplied.

PDF attachments must contain an extractable text layer. Scanned-image PDFs
will be marked `unreadable` by this version rather than silently guessing.
