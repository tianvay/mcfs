"""Admin login: password hash, persistent sessions, lockout after failed attempts.

Only the standard library, so deploy/set-password.sh can run it with the system python.
"""
from __future__ import annotations

import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
from pathlib import Path

SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 14, 8, 1
MIN_LENGTH = 8
SESSION_DAYS = 30
MAX_FAILURES = 5
LOCK_SECONDS = 15 * 60


# ---------- password hash ----------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        kind, n, r, p, salt, digest = stored.split("$")
        if kind != "scrypt":
            return False
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
                             dklen=len(bytes.fromhex(digest)))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got.hex(), digest)


# ---------- sessions ----------

class Sessions:
    """Login tokens that survive a portal restart. Only a hash of each token is stored on disk.

    Every session is tied to the password hash it was created under: after a new password
    (and the portal restart that loads it) all older sessions are gone.
    """

    def __init__(self, path: Path, password_hash: str):
        self.path = path
        self.tag = hashlib.sha256(password_hash.encode()).hexdigest()[:16]
        self._lock = threading.Lock()
        self._items: dict[str, float] = {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            now = time.time()
            self._items = {k: v["exp"] for k, v in raw.items() if v.get("pw") == self.tag and v.get("exp", 0) > now}
        except (OSError, ValueError, AttributeError, TypeError):
            pass

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def _save(self) -> None:
        data = {k: {"exp": exp, "pw": self.tag} for k, exp in self._items.items()}
        tmp = self.path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, self.path)

    def create(self) -> str:
        token = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._items = {k: exp for k, exp in self._items.items() if exp > now}
            self._items[self._key(token)] = now + SESSION_DAYS * 86400
            self._save()
        return token

    def valid(self, token: str | None) -> bool:
        if not token:
            return False
        exp = self._items.get(self._key(token))
        return exp is not None and exp > time.time()

    def remove(self, token: str | None) -> None:
        if not token:
            return
        with self._lock:
            if self._items.pop(self._key(token), None) is not None:
                self._save()


# ---------- lockout ----------

class Lockout:
    """At most MAX_FAILURES wrong passwords per device (IP) within LOCK_SECONDS."""

    def __init__(self):
        self._fails: dict[str, list[float]] = {}

    def _recent(self, ip: str) -> list[float]:
        cutoff = time.time() - LOCK_SECONDS
        recent = [t for t in self._fails.get(ip, []) if t > cutoff]
        if recent:
            self._fails[ip] = recent
        else:
            self._fails.pop(ip, None)
        return recent

    def wait_seconds(self, ip: str) -> int:
        """0 if this device may try again, else the seconds until it may."""
        recent = self._recent(ip)
        if len(recent) < MAX_FAILURES:
            return 0
        return max(1, int(recent[-MAX_FAILURES] + LOCK_SECONDS - time.time()))

    def failed(self, ip: str) -> None:
        self._fails.setdefault(ip, []).append(time.time())

    def reset(self, ip: str) -> None:
        self._fails.pop(ip, None)


# ---------- set-password (run as root through deploy/set-password.sh) ----------

def write_hash(config_text: str, password_hash: str) -> str:
    """config.toml with password_hash set under [portal]; the old pin setting is removed."""
    lines = [ln for ln in config_text.splitlines()
             if not re.match(r"\s*pin\s*=", ln) and not ln.startswith("# PIN für")]
    entry = f'password_hash = "{password_hash}"'
    for i, ln in enumerate(lines):
        if re.match(r"\s*password_hash\s*=", ln):
            lines[i] = entry
            break
    else:
        try:
            at = next(i for i, ln in enumerate(lines) if ln.strip() == "[portal]")
        except StopIteration:
            raise SystemExit("Abschnitt [portal] fehlt in der Konfiguration")
        lines[at + 1:at + 1] = ["# Admin-Passwort (nur der Hash) - setzen mit deploy/set-password.sh", entry]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[0] != "set-password":
        print("Aufruf: python3 -m app.auth set-password /etc/mcportal/config.toml", file=sys.stderr)
        return 2
    path = Path(argv[1])
    text = path.read_text(encoding="utf-8")
    first = getpass.getpass("Neues Admin-Passwort: ")
    if len(first) < MIN_LENGTH:
        print(f"Zu kurz - bitte mindestens {MIN_LENGTH} Zeichen.", file=sys.stderr)
        return 1
    if getpass.getpass("Noch einmal: ") != first:
        print("Die beiden Eingaben sind verschieden - nichts geändert.", file=sys.stderr)
        return 1
    st = path.stat()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(write_hash(text, hash_password(first)), encoding="utf-8", newline="\n")
    os.chown(tmp, st.st_uid, st.st_gid)
    os.chmod(tmp, st.st_mode & 0o777)
    os.replace(tmp, path)
    print(f"Passwort gespeichert in {path} (nur als Hash).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
