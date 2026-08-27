from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict

from decision_engine import DecisionEngine, format_result
from models import BattlefieldScene


PRESET_SCENES: Dict[str, BattlefieldScene] = {
    "urban_fast_capture": BattlefieldScene(
        name="城市快速夺控",
        objective="在4小时内控制交通枢纽并维持通信稳定",
        terrain="urban",
        weather="cloudy",
        enemy_strength=68,
        own_strength=72,
        supply_level=63,
        intel_quality=58,
        urgency=88,
        civilian_presence=82,
    ),
    "mountain_block": BattlefieldScene(
        name="山地要道封控",
        objective="封控山地要道，阻断敌增援",
        terrain="mountain",
        weather="fog",
        enemy_strength=74,
        own_strength=61,
        supply_level=55,
        intel_quality=64,
        urgency=65,
        civilian_presence=25,
    ),
    "plain_counterstrike": BattlefieldScene(
        name="平原反击",
        objective="夺回平原核心据点并恢复补给线",
        terrain="plain",
        weather="clear",
        enemy_strength=62,
        own_strength=70,
        supply_level=79,
        intel_quality=76,
        urgency=72,
        civilian_presence=30,
    ),
}


def load_scene_from_file(path: Path) -> BattlefieldScene:
    data = json.loads(path.read_text(encoding="utf-8"))
    return BattlefieldScene(**data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="战场对抗多智能体决策交流与最优策略选择")
    parser.add_argument(
        "--scenario",
        default="urban_fast_capture",
        help=f"预置场景名称，可选: {', '.join(PRESET_SCENES.keys())}",
    )
    parser.add_argument("--scene-file", type=Path, help="自定义场景 JSON 文件路径")
    parser.add_argument("--no-messages", action="store_true", help="不展示智能体交流摘录")
    parser.add_argument("--list", action="store_true", help="列出可用预置场景")
    parser.add_argument(
        "--llm-mode",
        choices=["auto", "on", "off"],
        default="auto",
        help="LLM调用模式: auto(有key则启用), on(强制启用), off(仅本地规则)",
    )
    parser.add_argument("--llm-model", help="覆盖默认模型名，例如 gpt-4o-mini")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        print("可用预置场景:")
        for name, scene in PRESET_SCENES.items():
            print(f"- {name}: {scene.name}")
        return

    if args.scene_file:
        scene = load_scene_from_file(args.scene_file)
    else:
        if args.scenario not in PRESET_SCENES:
            raise SystemExit(f"未知场景: {args.scenario}，可先执行 --list 查看可用场景。")
        scene = PRESET_SCENES[args.scenario]

    engine = DecisionEngine(llm_mode=args.llm_mode, llm_model=args.llm_model)
    try:
        result = engine.run(scene)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(format_result(scene, result, show_messages=not args.no_messages))


if __name__ == "__main__":
    main()
