import json
import sys
from pathlib import Path

# Allow importing the app package when running this script directly.
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from app.ingest.pdf_loader import load_policy_pdf
from app.ingest.chunker import chunk_policy


def main() -> None:
    pdf_path = ROOT_DIR / "data" / "policy.pdf"
    output_dir = ROOT_DIR / "data" / "processed"
    output_path = output_dir / "policy_chunks.json"

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading policy: {pdf_path}")

    pages = load_policy_pdf(str(pdf_path))

    print(f"Extracted text from {len(pages)} pages.")

    chunks = chunk_policy(pages)

    print(f"Created {len(chunks)} policy chunks.")

    data = [
        {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "page_number": chunk.page_number,
            "section": chunk.section,
            "source": chunk.source,
        }
        for chunk in chunks
    ]

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    print(f"Saved chunks to: {output_path}")

    print("\nFirst five chunks:")

    for chunk in data[:5]:
        print(
            f"\n{chunk['chunk_id']} | "
            f"Page {chunk['page_number']} | "
            f"{chunk['section']}"
        )

        print(chunk["text"][:300])


if __name__ == "__main__":
    main()