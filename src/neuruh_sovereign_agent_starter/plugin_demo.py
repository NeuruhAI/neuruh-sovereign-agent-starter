"""Run the three synthetic fixtures through the existing public functions."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .micro_plugins import (
    choose_cheapest_capable_route,
    compile_context_packet,
    public_proof_card,
)


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    candidate = here.parents[2]
    if (candidate / "examples").is_dir():
        return candidate
    return Path.cwd()


def main(argv: list[str] | None = None) -> int:
    del argv
    root = _repo_root()
    mission = json.loads((root / "examples/mission-packet.synthetic.json").read_text(encoding="utf-8"))
    candidates = json.loads((root / "examples/route-candidates.synthetic.json").read_text(encoding="utf-8"))
    receipt = json.loads((root / "examples/internal-receipt.synthetic.json").read_text(encoding="utf-8"))
    results = {
        "context_pack": compile_context_packet(mission),
        "cheap_route": choose_cheapest_capable_route(candidates).as_dict(),
        "proof_card": public_proof_card(receipt),
    }
    json.dump(results, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
