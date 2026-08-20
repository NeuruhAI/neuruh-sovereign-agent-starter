from __future__ import annotations
import argparse
import json
from pathlib import Path
from .core import StarterConfig, StarterError, run


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="neuruh-sovereign-agent")
    p.add_argument("config", help="starter JSON configuration")
    p.add_argument("--out-dir", default="run-output")
    args = p.parse_args(argv)
    try:
        config = StarterConfig.from_mapping(json.loads(Path(args.config).read_text()))
        result = run(config)
    except (OSError, json.JSONDecodeError, StarterError, ValueError) as exc:
        print(f"RUN REFUSED: {exc}")
        return 2
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(
        json.dumps(result.manifest.to_dict(), indent=2) + "\n"
    )
    (out / "receipts.jsonl").write_text(
        "".join(json.dumps(x, sort_keys=True) + "\n" for x in result.receipts)
    )
    (out / "result.json").write_text(
        json.dumps(
            {
                "decision": result.decision,
                "execution": result.execution,
                "inference_output": result.inference_output,
            },
            indent=2,
        )
        + "\n"
    )
    print(f"RUN {result.manifest.status.upper()}: {result.manifest.run_id}")
    print(f"MANIFEST: {out / 'manifest.json'}")
    print(f"RECEIPTS: {out / 'receipts.jsonl'}")
    return (
        0
        if result.manifest.status in {"completed", "dry_run", "denied", "escalated"}
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
