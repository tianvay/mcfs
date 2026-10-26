import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.adapters.bedrock.commands import gamemode_survival, tell_operator_status
from app.adapters.bedrock.files import ServerFiles
from app.adapters.bedrock.logparse import OnlinePlayer, parse_journal_line, parse_spawned
from app.audit import AuditLog
from app.services import allowlist as allowlist_mod
from app.services.allowlist import AllowlistService

PERMS = '[{"permission":"operator","xuid":"2535400000000001"},{"permission":"operator","xuid":"2535400000000002"}]'
ALLOW = ('[{"ignoresPlayerLimit":false,"name":"Steve","xuid":"2535400000000001"},'
         '{"ignoresPlayerLimit":false,"name":"Alex","xuid":"2535400000000002"}]')


class Unit:
    active_state, sub_state = "active", "running"


class Tracker:
    def __init__(self):
        self.players = {}


class FakeMc:
    def __init__(self):
        self.line_listeners, self.extras = [], {}
        self.tracker, self.unit, self.busy = Tracker(), Unit(), None
        self.op_lock = asyncio.Lock()

    def publish(self):
        pass

    def refresh_allowlist_count(self):
        pass


class FakeAdapter:
    def __init__(self, server_dir):
        self.files = ServerFiles(server_dir)
        self.sent = []

    def console_available(self):
        return True

    def permissions_reload_live(self):
        self.sent.append("permission reload")

    def set_survival_live(self, name):
        self.sent.append(gamemode_survival(name))

    def tell_operator_status_live(self, name, granted):
        self.sent.append(tell_operator_status(name, granted))


class OperatorSurvivalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        (d / "srv").mkdir()
        (d / "srv/permissions.json").write_text(PERMS)
        (d / "srv/allowlist.json").write_text(ALLOW)
        self.dir = d
        allowlist_mod.SPAWN_SETTLE = 0

    def tearDown(self):
        self.tmp.cleanup()

    def make(self):
        mc = FakeMc()
        a = FakeAdapter(str(self.dir / "srv"))
        s = AllowlistService(a, mc, AuditLog(self.dir / "audit.jsonl"), self.dir / "backups", 5,
                             self.dir / "pending_operator.json")
        return s, a, mc

    def test_online_player_is_set_to_survival_immediately(self):
        s, a, mc = self.make()
        mc.tracker.players["steve"] = OnlinePlayer("Steve", "2535400000000001", 0)
        asyncio.run(s.set_operator("steve", False, "test"))
        self.assertEqual(a.sent, ["permission reload", "gamemode survival Steve",
                                  'tellraw Steve {"rawtext": [{"text": "§6Du bist nicht mehr Operator."}]}'])
        self.assertFalse(s.pending)

    def test_offline_player_is_set_on_next_spawn_also_after_portal_restart(self):
        s, a, mc = self.make()
        asyncio.run(s.set_operator("Alex", False, "test"))
        self.assertEqual(a.sent, ["permission reload"])
        self.assertEqual(json.loads((self.dir / "pending_operator.json").read_text()),
                         {"alex": {"name": "Alex", "survival": True, "message": False}})
        self.assertTrue([e for e in s.list()["entries"] if e["name"] == "Alex"][0]["survival_pending"])

        # portal restarts, then Alex joins and spawns
        s2, a2, mc2 = self.make()
        spawn = parse_journal_line("1.0 h bedrock_server[1]: [2026-10-26 08:10:00:000 INFO] "
                                   "Player Spawned: Alex xuid: 2535400000000002, pfid: 0000000000000002")
        self.assertEqual(parse_spawned(spawn), "Alex")

        async def run():
            for fn in mc2.line_listeners:
                fn(spawn)
            await asyncio.sleep(0.05)
        asyncio.run(run())
        self.assertEqual(a2.sent, ["gamemode survival Alex",
                                   'tellraw Alex {"rawtext": [{"text": "§6Du bist nicht mehr Operator."}]}'])
        self.assertFalse(s2.pending)

    def test_granting_again_replaces_survival_by_the_grant_message(self):
        s, a, mc = self.make()
        asyncio.run(s.set_operator("Alex", False, "test"))
        asyncio.run(s.set_operator("Alex", True, "test"))
        self.assertEqual(s.pending["alex"], {"name": "Alex", "survival": False, "message": True})
        self.assertFalse([e for e in s.list()["entries"] if e["name"] == "Alex"][0]["survival_pending"])

    def test_online_grant_gets_message(self):
        s, a, mc = self.make()
        asyncio.run(s.set_operator("Alex", False, "test"))  # offline revoke -> pending
        mc.tracker.players["alex"] = OnlinePlayer("Alex", "2535400000000002", 0)
        a.sent.clear()
        asyncio.run(s.set_operator("Alex", True, "test"))
        self.assertEqual(a.sent, ["permission reload",
                                  'tellraw Alex {"rawtext": [{"text": "§6Du bist jetzt Operator."}]}'])
        self.assertFalse(s.pending)

    def test_reads_pending_file_of_the_first_version(self):
        (self.dir / "pending_survival.json").write_text('["Alex"]')
        s, a, mc = self.make()
        self.assertEqual(s.pending["alex"], {"name": "Alex", "survival": True, "message": None})

    def test_command_quotes_names_with_spaces(self):
        self.assertEqual(gamemode_survival("Cool Kid 7"), 'gamemode survival "Cool Kid 7"')
        self.assertTrue(tell_operator_status("Cool Kid 7", True).startswith('tellraw "Cool Kid 7" {'))
        with self.assertRaises(ValueError):
            tell_operator_status('x" @a', True)


if __name__ == "__main__":
    unittest.main()
