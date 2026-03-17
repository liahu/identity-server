import argparse
import json
from pathlib import Path
from typing import Optional

import requests


def call_health(base_url: str) -> dict:
    resp = requests.get(f"{base_url}/health", timeout=15)
    resp.raise_for_status()
    return resp.json()


def call_enroll(base_url: str, person_id: str, file_path: Path) -> dict:
    with file_path.open("rb") as f:
        files = {"file": (file_path.name, f)}
        data = {"person_id": person_id}
        resp = requests.post(f"{base_url}/enroll", files=files, data=data, timeout=60)
    resp.raise_for_status()
    return resp.json()


def call_identify(base_url: str, file_path: Path, threshold: Optional[float]) -> dict:
    with file_path.open("rb") as f:
        files = {"file": (file_path.name, f)}
        data = {}
        if threshold is not None:
            data["threshold"] = str(threshold)
        resp = requests.post(f"{base_url}/identify", files=files, data=data, timeout=60)
    resp.raise_for_status()
    return resp.json()


def run_face(args: argparse.Namespace) -> None:
    print("== Face Service ==")
    health = call_health(args.face_url)
    print("health:", json.dumps(health, ensure_ascii=False))
    if not args.face_enroll_a or not args.face_enroll_b or not args.face_probe:
        print("skip face enroll/identify: missing --face-enroll-a/--face-enroll-b/--face-probe")
        return

    enroll_a = call_enroll(args.face_url, "face_user_a", Path(args.face_enroll_a))
    enroll_b = call_enroll(args.face_url, "face_user_b", Path(args.face_enroll_b))
    identify = call_identify(args.face_url, Path(args.face_probe), args.face_threshold)
    print("enroll_a:", json.dumps(enroll_a, ensure_ascii=False))
    print("enroll_b:", json.dumps(enroll_b, ensure_ascii=False))
    print("identify:", json.dumps(identify, ensure_ascii=False))


def run_voice(args: argparse.Namespace) -> None:
    print("== Voice Service ==")
    health = call_health(args.voice_url)
    print("health:", json.dumps(health, ensure_ascii=False))
    if not args.voice_enroll_a or not args.voice_enroll_b or not args.voice_probe:
        print("skip voice enroll/identify: missing --voice-enroll-a/--voice-enroll-b/--voice-probe")
        return

    enroll_a = call_enroll(args.voice_url, "voice_user_a", Path(args.voice_enroll_a))
    enroll_b = call_enroll(args.voice_url, "voice_user_b", Path(args.voice_enroll_b))
    identify = call_identify(args.voice_url, Path(args.voice_probe), args.voice_threshold)
    print("enroll_a:", json.dumps(enroll_a, ensure_ascii=False))
    print("enroll_b:", json.dumps(enroll_b, ensure_ascii=False))
    print("identify:", json.dumps(identify, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Integration tests for face/voice services")
    parser.add_argument("--face-url", default="http://face-service:8080")
    parser.add_argument("--voice-url", default="http://voice-service:8080")

    parser.add_argument("--face-enroll-a")
    parser.add_argument("--face-enroll-b")
    parser.add_argument("--face-probe")
    parser.add_argument("--face-threshold", type=float, default=None)

    parser.add_argument("--voice-enroll-a")
    parser.add_argument("--voice-enroll-b")
    parser.add_argument("--voice-probe")
    parser.add_argument("--voice-threshold", type=float, default=None)
    args = parser.parse_args()

    run_face(args)
    run_voice(args)


if __name__ == "__main__":
    main()
