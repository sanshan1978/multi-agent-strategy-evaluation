from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import unquote, urlparse

from decision_engine import DecisionEngine
from main import PRESET_SCENES
from models import BattlefieldScene
from serializers import result_to_dict, scene_to_dict


ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"


class DecisionRequestHandler(BaseHTTPRequestHandler):
    server_version = "DecisionConsole/1.0"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"ok": True})
            return
        if parsed.path == "/api/scenarios":
            self._send_json({key: scene_to_dict(scene) for key, scene in PRESET_SCENES.items()})
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/decide":
            self._send_json({"error": "not found"}, status=404)
            return

        try:
            payload = self._read_json()
            scene_data = payload.get("scene", {})
            llm_mode = str(payload.get("llm_mode", "auto"))
            llm_model = payload.get("llm_model") or None
            scene = BattlefieldScene(**scene_data)
            engine = DecisionEngine(llm_mode=llm_mode, llm_model=llm_model)
            result = engine.run(scene)
            self._send_json(result_to_dict(result))
        except RuntimeError as exc:
            error_text = str(exc)
            error_type = "runtime_error"
            status = 500
            if "外部模型调用失败" in error_text:
                error_type = "llm_call_failed"
                status = 502
            elif "未检测到 API_KEY" in error_text:
                error_type = "missing_api_key"
                status = 400
            self._send_json({"error": error_text, "error_type": error_type}, status=status)
        except Exception as exc:  # noqa: BLE001
            self._send_json({"error": str(exc), "error_type": "server_error"}, status=500)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        data = json.loads(body or "{}")
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object")
        return data

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, request_path: str) -> None:
        path = unquote(request_path)
        if path in {"", "/"}:
            file_path = FRONTEND_DIR / "index.html"
        elif path.startswith("/frontend/"):
            file_path = FRONTEND_DIR / path.removeprefix("/frontend/")
        else:
            file_path = FRONTEND_DIR / path.lstrip("/")

        try:
            resolved = file_path.resolve()
            resolved.relative_to(FRONTEND_DIR.resolve())
        except ValueError:
            self._send_json({"error": "forbidden"}, status=403)
            return

        if not resolved.is_file():
            self._send_json({"error": "not found"}, status=404)
            return

        content = resolved.read_bytes()
        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        if resolved.suffix in {".html", ".css", ".js"}:
            content_type += "; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="战场对抗智能体前端展示服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), DecisionRequestHandler)
    print(f"前端地址: http://{args.host}:{args.port}/")
    print("按 Ctrl+C 停止服务")
    server.serve_forever()


if __name__ == "__main__":
    main()
