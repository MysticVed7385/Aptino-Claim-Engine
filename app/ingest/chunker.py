import re
from dataclasses import dataclass


@dataclass
class PolicyChunk:
    chunk_id: str
    text: str
    page_number: int
    section: str
    source: str = "policy.pdf"


def is_heading(line: str) -> bool:
    """
    Heuristic heading detector for policy documents.

    It detects common numbered sections and uppercase headings.
    """
    line = line.strip()

    if not line:
        return False

    if len(line) > 180:
        return False

    numbered_heading = re.match(
        r"^(?:SECTION\s+)?\d+(?:\.\d+)*[\s.)-]+.+",
        line,
        flags=re.IGNORECASE,
    )

    uppercase_heading = (
        len(line) >= 4
        and line == line.upper()
        and any(char.isalpha() for char in line)
    )

    return bool(numbered_heading or uppercase_heading)


def normalize_text(text: str) -> str:
    """Normalize whitespace while preserving readable paragraphs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = [line.strip() for line in text.split("\n")]
    lines = [line for line in lines if line]

    return "\n".join(lines)


def chunk_policy(
    pages: list[dict],
    source: str = "policy.pdf",
) -> list[PolicyChunk]:
    """
    Create section-aware policy chunks.

    A new chunk starts when a new heading is detected.
    Page number and section are preserved in metadata.
    """
    chunks: list[PolicyChunk] = []

    current_lines: list[str] = []
    current_section = "Unknown"
    current_page = 1
    chunk_counter = 0

    def flush_chunk() -> None:
        nonlocal chunk_counter
        nonlocal current_lines

        if not current_lines:
            return

        text = normalize_text("\n".join(current_lines))

        if not text:
            current_lines = []
            return

        chunk_counter += 1

        chunks.append(
            PolicyChunk(
                chunk_id=f"POLICY-{chunk_counter:05d}",
                text=text,
                page_number=current_page,
                section=current_section,
                source=source,
            )
        )

        current_lines = []

    for page in pages:
        page_number = page["page_number"]
        text = page["text"]

        for line in text.splitlines():
            line = line.strip()

            if not line:
                continue

            if is_heading(line):
                flush_chunk()

                current_section = line
                current_page = page_number
                current_lines.append(line)
            else:
                if not current_lines:
                    current_page = page_number

                current_lines.append(line)

    flush_chunk()

    return chunks