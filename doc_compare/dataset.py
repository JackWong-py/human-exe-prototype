from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SUPPORTED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff",
    ".txt", ".doc", ".docx", ".xls", ".xlsx",
}


@dataclass(slots=True)
class Attachment:
    path: Path
    case_id: str
    name: str


def infer_case_id(path: Path) -> str:
    """
    Best-effort case ID extraction.

    Examples:
        013_SI.pdf       -> 013
        013/si.pdf       -> 013
        case_097_BL.pdf  -> 097
    """
    import re

    candidates = [path.stem, path.parent.name]
    for candidate in candidates:
        match = re.search(r"(?<!\d)(\d{3})(?!\d)", candidate)
        if match:
            return match.group(1)

    return path.parent.name or path.stem


def discover_attachments(root: str | Path) -> list[Attachment]:
    root = Path(root).expanduser()

    if not root.exists():
        raise FileNotFoundError(
            f"Dataset path does not exist: {root}\n"
            "If you copied the path from inside Windows Explorer's ZIP view, "
            "extract the ZIP first and point this command at the real "
            "data_v2\\attachments directory."
        )

    if not root.is_dir():
        raise NotADirectoryError(f"Expected an attachments directory, got: {root}")

    found: list[Attachment] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
            continue

        found.append(
            Attachment(
                path=path,
                case_id=infer_case_id(path),
                name=path.name,
            )
        )

    return sorted(found, key=lambda x: (x.case_id, str(x.path).casefold()))


def group_by_case(items: Iterable[Attachment]) -> dict[str, list[Attachment]]:
    grouped: dict[str, list[Attachment]] = {}
    for item in items:
        grouped.setdefault(item.case_id, []).append(item)
    return grouped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover SI/BL dataset attachments."
    )
    parser.add_argument(
        "attachments",
        help=r"Path to data_v2\attachments",
    )
    parser.add_argument(
        "--show",
        type=int,
        default=20,
        help="How many discovered files to print.",
    )
    args = parser.parse_args()

    items = discover_attachments(args.attachments)
    grouped = group_by_case(items)

    print(f"attachments: {len(items)}")
    print(f"case groups: {len(grouped)}")
    print()

    for item in items[: args.show]:
        print(f"{item.case_id:>8}  {item.path}")

    if len(items) > args.show:
        print(f"... {len(items) - args.show} more")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
