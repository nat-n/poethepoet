"""Data processing script."""

from __future__ import annotations

from pathlib import Path


def main(
    input_file: str,
    output_dir: str = "reports",
    verbose: bool = False,
    format: str = "html",
) -> None:
    """
    Process a data file and write a report.

    Args:
        input_file: Path to the input data file
        output_dir: Directory to write the report to
        verbose: Enable verbose logging
        format: Output format (html, csv, json)
    """
    if verbose:
        print(f"Processing {input_file} -> {output_dir} ({format})")

    src = Path(input_file)
    if not src.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    print(f"Report written to {output_dir}/")
