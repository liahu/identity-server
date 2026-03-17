import json
import subprocess
import sys


def main() -> None:
    installed = []
    seen = set()
    while True:
        p = subprocess.run(
            [sys.executable, "-c", "import wespeaker.cli.speaker"],
            capture_output=True,
            text=True,
        )
        if p.returncode == 0:
            break
        msg = (p.stderr or p.stdout or "")
        marker = "No module named "
        if marker not in msg:
            print(msg)
            raise SystemExit(1)

        tail = msg.split(marker, 1)[1].strip()
        name = tail.strip('"').strip("'").split(".")[0]
        if name in seen:
            print("repeated", name)
            print(msg)
            raise SystemExit(1)

        seen.add(name)
        r = subprocess.run([sys.executable, "-m", "pip", "install", name], text=True)
        if r.returncode != 0:
            raise SystemExit(r.returncode)
        installed.append(name)

    print(json.dumps(installed))


if __name__ == "__main__":
    main()
