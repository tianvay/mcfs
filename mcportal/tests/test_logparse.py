import unittest

from app.adapters.bedrock.commands import allowlist_add, valid_player_name
from app.adapters.bedrock.logparse import PlayerTracker, parse_journal_line, version_history

# Real lines from the server journal (2026-09-20)
JOURNAL = """\
1789905216.843800 mcserver systemd[1]: Started minecraft-bedrock.service - Minecraft Bedrock Server.
1789905216.930177 mcserver bedrock_server[114723]: NO LOG FILE! - setting up server logging...
1789905216.930177 mcserver bedrock_server[114723]: [2026-09-20 13:53:36:878 INFO] Starting Server
1789905216.930177 mcserver bedrock_server[114723]: [2026-09-20 13:53:36:878 INFO] Version: 1.26.51.1
1789905220.824545 mcserver bedrock_server[114723]: [2026-09-20 13:53:40:824 INFO] Server started.
1789905274.525368 mcserver bedrock_server[114723]: [2026-09-20 13:54:34:524 INFO] Player connected: Steve, xuid: 2535400000000001
1789905281.764142 mcserver bedrock_server[114723]: [2026-09-20 13:54:41:764 INFO] Player Spawned: Steve xuid: 2535400000000001, pfid: 00000000000A0001
1789905290.000000 mcserver bedrock_server[114723]: [2026-09-20 13:54:50:000 INFO] Player connected: Alex, xuid: 2535400000000002
1789905300.000000 mcserver bedrock_server[114723]: [2026-09-20 13:55:00:000 INFO] Player disconnected: Alex, xuid: 2535400000000002, pfid: 0000000000000002
"""


def lines(text):
    return [l for l in (parse_journal_line(r) for r in text.splitlines()) if l]


class TrackerTest(unittest.TestCase):
    def test_connect_disconnect(self):
        t = PlayerTracker()
        for l in lines(JOURNAL):
            t.feed(l)
        self.assertTrue(t.server_started)
        self.assertEqual([p.name for p in t.players.values()], ["Steve"])

    def test_systemd_stop_clears(self):
        t = PlayerTracker()
        for l in lines(JOURNAL + "1789905399.038849 mcserver systemd[1]: Stopping minecraft-bedrock.service - Minecraft Bedrock Server...\n"):
            t.feed(l)
        self.assertEqual(t.players, {})
        self.assertFalse(t.server_started)

    def test_list_reconciles(self):
        t = PlayerTracker()
        for l in lines(JOURNAL):
            t.feed(l)
        extra = (
            "1789905400.0 mcserver bedrock_server[1]: [2026-09-20 13:56:40:000 INFO] There are 2/10 players online:\n"
            "1789905400.0 mcserver bedrock_server[1]: Sunny, Alex\n"
        )
        for l in lines(extra):
            t.feed(l)
        self.assertEqual(sorted(p.name for p in t.players.values()), ["Alex", "Sunny"])

    def test_list_zero(self):
        t = PlayerTracker()
        for l in lines(JOURNAL):
            t.feed(l)
        for l in lines("1789905400.0 mcserver bedrock_server[1]: [2026-09-20 13:56:40:000 INFO] There are 0/10 players online:\n"):
            t.feed(l)
        self.assertEqual(t.players, {})


class VersionTest(unittest.TestCase):
    def test_history(self):
        text = (
            "100.0 h bedrock_server[1]: [2026-09-20 13:16:23:839 INFO] Version: 1.21.124.2\n"
            "200.0 h bedrock_server[2]: [2026-09-20 13:20:04:214 INFO] Version: 1.26.51.1\n"
            "300.0 h bedrock_server[3]: [2026-09-20 13:53:36:878 INFO] Version: 1.26.51.1\n"
        )
        self.assertEqual(version_history(lines(text)), [(100.0, "1.21.124.2"), (200.0, "1.26.51.1")])


class CommandTest(unittest.TestCase):
    def test_names(self):
        for ok in ["Steve", "Alex", "Sunny", "Cool Kid 7", "Name#1234", "a_b-c"]:
            self.assertTrue(valid_player_name(ok), ok)
        for bad in ["", " lead", "trail ", "a;b", 'x"y', "two  spaces", "a\nb", "x" * 40, "@s", "ä"]:
            self.assertFalse(valid_player_name(bad), bad)

    def test_quoting(self):
        self.assertEqual(allowlist_add("Cool Kid 7"), 'allowlist add "Cool Kid 7"')
        with self.assertRaises(ValueError):
            allowlist_add("x; stop")


if __name__ == "__main__":
    unittest.main()
