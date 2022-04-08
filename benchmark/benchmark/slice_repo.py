from pathlib import Path
import re
from typing import Sequence, Tuple, Optional
import operator
import typer

def slice_repo(
        repo: Path,
        slice_specs: Sequence[Tuple[Path, Optional[int], Optional[int]]],
) -> Sequence[str]:
    unique_slice_specs = set(slice_specs)
    slices = []
    for path, start, end in unique_slice_specs:
        if not path.is_absolute():
            path = repo / path
        text = path.read_text()
        if start is None:
            start = 1
        if end is None:
            end = len(text) + 1
        slices.append("\n".join(text.split("\n")[start-1:end-1]) + "\n")
    return slices

slice_spec_re = re.compile(r"^(?P<path>[^:]*)(?::(?P<start>\d+)?-(?P<end>\d+)?)?$")
def parse_slice_spec(slice_spec: str) -> Tuple[Path, Optional[int], Optional[int]]:
    m = slice_spec_re.match(slice_spec)
    if not m:
        raise ValueError(f"Invalid slice spec {slice_spec!r}")
    parsed = m.groupdict()
    path = Path(parsed["path"])
    start = int(parsed["start"]) if "start" in parsed else None
    end = int(parsed["end"]) if "end" in parsed else None
    return (path, start, end)

def main(
        repo: Path,
        slice_specs: typer.FileText,
        output: typer.FileTextWrite,
) -> None:
    parsed_slice_specs = [
        parse_slice_spec(line.strip())
        for line in slice_specs
    ]
    for repo_slice in slice_repo(repo, parsed_slice_specs):
        output.write(repo_slice)

if __name__ == "__main__":
    typer.run(main)
