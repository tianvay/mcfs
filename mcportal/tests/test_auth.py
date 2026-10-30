import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from app import auth


class PasswordTest(unittest.TestCase):
    def test_hash_and_verify(self):
        h = auth.hash_password("Creeper-Bernd 42")
        self.assertTrue(h.startswith("scrypt$"))
        self.assertTrue(auth.verify_password("Creeper-Bernd 42", h))
        self.assertFalse(auth.verify_password("creeper-bernd 42", h))
        self.assertNotEqual(h, auth.hash_password("Creeper-Bernd 42"))  # own salt each time

    def test_broken_hash_is_never_valid(self):
        for stored in ("", "4711", "scrypt$x$8$1$00$00", "md5$1$2$3$4$5"):
            self.assertFalse(auth.verify_password("4711", stored))


class SessionsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "sessions.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_survives_restart_but_not_a_new_password(self):
        s = auth.Sessions(self.path, "hash-1")
        token = s.create()
        self.assertTrue(s.valid(token))
        self.assertNotIn(token, self.path.read_text())  # only a hash of the token on disk
        self.assertTrue(auth.Sessions(self.path, "hash-1").valid(token))
        self.assertFalse(auth.Sessions(self.path, "hash-2").valid(token))

    def test_logout_and_unknown(self):
        s = auth.Sessions(self.path, "h")
        token = s.create()
        s.remove(token)
        self.assertFalse(s.valid(token))
        self.assertFalse(auth.Sessions(self.path, "h").valid(token))
        self.assertFalse(s.valid(None))
        self.assertFalse(s.valid("made-up"))

    def test_expires(self):
        s = auth.Sessions(self.path, "h")
        token = s.create()
        later = time.time() + auth.SESSION_DAYS * 86400 + 1
        with mock.patch("app.auth.time.time", return_value=later):
            self.assertFalse(s.valid(token))
            self.assertFalse(auth.Sessions(self.path, "h").valid(token))


class LockoutTest(unittest.TestCase):
    def test_locks_one_device_only(self):
        lock = auth.Lockout()
        for _ in range(auth.MAX_FAILURES - 1):
            lock.failed("192.168.178.50")
        self.assertEqual(lock.wait_seconds("192.168.178.50"), 0)
        lock.failed("192.168.178.50")
        self.assertGreater(lock.wait_seconds("192.168.178.50"), 0)
        self.assertEqual(lock.wait_seconds("192.168.178.51"), 0)
        later = time.time() + auth.LOCK_SECONDS + 1
        with mock.patch("app.auth.time.time", return_value=later):
            self.assertEqual(lock.wait_seconds("192.168.178.50"), 0)

    def test_success_resets(self):
        lock = auth.Lockout()
        for _ in range(auth.MAX_FAILURES):
            lock.failed("ip")
        lock.reset("ip")
        self.assertEqual(lock.wait_seconds("ip"), 0)


class WriteHashTest(unittest.TestCase):
    CONFIG = ('[portal]\nhost = "0.0.0.0"\n# PIN für schreibende Aktionen (Start/Stop/Whitelist). Leer = kein PIN.\n'
              'pin = "4711"\nadapter = "bedrock"\n\n[bedrock]\nserver_dir = "/opt/minecraft/bedrock"\n')

    def test_adds_hash_and_drops_pin(self):
        out = auth.write_hash(self.CONFIG, "scrypt$a")
        self.assertIn('password_hash = "scrypt$a"', out)
        self.assertNotIn("pin =", out)
        self.assertNotIn("# PIN", out)
        self.assertLess(out.index("password_hash"), out.index("[bedrock]"))
        self.assertIn('server_dir = "/opt/minecraft/bedrock"', out)

    def test_replaces_existing_hash(self):
        out = auth.write_hash(auth.write_hash(self.CONFIG, "scrypt$a"), "scrypt$b")
        self.assertEqual(out.count("password_hash ="), 1)
        self.assertIn('password_hash = "scrypt$b"', out)


if __name__ == "__main__":
    unittest.main()
