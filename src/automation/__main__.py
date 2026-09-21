"""python -m automation: local research and paper operations."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .runner import PROJECT_ROOT, load_config, read_state, run_once


def main() -> int:
    parser = argparse.ArgumentParser(description="Automação local de pesquisa e simulação Momentum ATR")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "automation.json")
    commands = parser.add_subparsers(dest="command", required=True)
    once = commands.add_parser("run-once", help="Pesquisa local; pula entradas inalteradas")
    once.add_argument("--force", action="store_true", help="Nova avaliação exploratória, sem apagar resultados anteriores")
    commands.add_parser("status", help="Último estado local, sem rede")
    demo = commands.add_parser("demo", help="Fixture sintética + pesquisa + webhook HMAC + ledger paper isolado")
    demo.add_argument("--output", type=Path, default=PROJECT_ROOT / "results" / "automation" / "demos")
    kill = commands.add_parser("kill", help="Liga/desliga bloqueio local de novas ordens paper")
    kill.add_argument("state", choices=("on", "off"))
    kill.add_argument("--oms-config", type=Path, default=PROJECT_ROOT / "config" / "oms_simulation.json")
    args = parser.parse_args()
    if args.command == "demo":
        from .demo import run_demo
        result = run_demo(args.output)
    elif args.command == "kill":
        from server.config import OmsSimulationConfig
        oms = OmsSimulationConfig.model_validate_json(args.oms_config.read_text(encoding="utf-8"))
        if oms.kill_switch_path is None:
            parser.error("configure kill_switch_path no JSON do OMS primeiro")
        marker = oms.kill_switch_path
        if not marker.is_absolute():
            marker = PROJECT_ROOT / marker
        marker = marker.resolve()
        marker.parent.mkdir(parents=True, exist_ok=True)
        if args.state == "on":
            with marker.open("x", encoding="utf-8") if not marker.exists() else marker.open("a", encoding="utf-8") as handle:
                handle.write("paper orders paused by local operator\n")
        else:
            marker.unlink(missing_ok=True)
        result = {"mode": "paper", "file_kill_switch": marker.exists(), "static_kill_switch": oms.kill_switch}
    else:
        config = load_config(args.config)
        result = read_state(config.output_root) if args.command == "status" else run_once(config, force=args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 2 if result.get("status") in {"blocked", "failed"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
