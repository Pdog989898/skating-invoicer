import json
from pathlib import Path
from urllib.request import urlopen


class UpdateService:
    def __init__(self, version_file: str = "version.txt") -> None:
        self.version_file = Path(version_file)

    def local_version(self) -> str:
        if not self.version_file.exists():
            return "0.0.0"
        return self.version_file.read_text(encoding="utf-8").strip() or "0.0.0"

    def check(self, version_json_url: str) -> dict:
        with urlopen(version_json_url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        local = self.local_version()
        remote = payload.get("version", local)
        return {
            "local": local,
            "remote": remote,
            "download_url": payload.get("download_url"),
            "has_update": self._is_newer(remote, local),
        }

    @staticmethod
    def _is_newer(remote: str, local: str) -> bool:
        def to_parts(v: str):
            return tuple(int(part) for part in v.split("."))

        try:
            return to_parts(remote) > to_parts(local)
        except ValueError:
            return remote != local
