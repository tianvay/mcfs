"""deploy/mc-public-ip: public IPv4 from the router into server-udp-ports (one line per port)."""
import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parent.parent / "deploy" / "mc-public-ip"
_loader = importlib.machinery.SourceFileLoader("mc_public_ip", str(SCRIPT))
_spec = importlib.util.spec_from_loader("mc_public_ip", _loader)
P = importlib.util.module_from_spec(_spec)
_loader.exec_module(P)

PROPS = "server-name=Family\nserver-port=19132\nserver-udp-ports=19140-19159\nlevel-name=FAF\n"


def soap(ip: str) -> bytes:
    return (f"<s:Envelope><s:Body><u:GetExternalIPAddressResponse><NewExternalIPAddress>{ip}"
            "</NewExternalIPAddress></u:GetExternalIPAddressResponse></s:Body></s:Envelope>").encode()


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def read(self, n=-1):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class RewriteTest(unittest.TestCase):
    def test_one_line_per_port_in_place(self):
        out = P.rewrite(PROPS, "203.0.113.7", range(19140, 19143))
        self.assertEqual(out.splitlines(), [
            "server-name=Family", "server-port=19132",
            "server-udp-ports=203.0.113.7:19140:19140", "server-udp-ports=203.0.113.7:19141:19141",
            "server-udp-ports=203.0.113.7:19142:19142", "level-name=FAF"])
        self.assertEqual(P.rewrite(out, "203.0.113.7", range(19140, 19143)), out, "second run changes nothing")

    def test_appended_when_missing(self):
        out = P.rewrite("server-port=19132\n", "203.0.113.7", range(19140, 19141))
        self.assertTrue(out.endswith("server-udp-ports=203.0.113.7:19140:19140\n"))

    def test_port_range_limits(self):
        self.assertEqual(P.port_range("19140-19149"), range(19140, 19150))
        for bad in ("19140", "19140-19160", "80-90", "19149-19140", "a-b"):
            with self.assertRaises(ValueError, msg=bad):
                P.port_range(bad)


class RouterTest(unittest.TestCase):
    def test_public_address_accepted_private_refused(self):
        with mock.patch.object(P.urllib.request, "urlopen", return_value=FakeResponse(soap("203.0.113.7"))):
            # 203.0.113.0/24 is a documentation range, not global - like DS-Lite/CGNAT it must be refused
            with self.assertRaises(ValueError):
                P.public_ipv4("192.168.178.1")
        with mock.patch.object(P.urllib.request, "urlopen", return_value=FakeResponse(soap("8.8.4.4"))):
            self.assertEqual(P.public_ipv4("192.168.178.1"), "8.8.4.4")
        for bad in ("100.64.1.2", "192.168.1.1", "", "2001:db8::1"):
            with mock.patch.object(P.urllib.request, "urlopen", return_value=FakeResponse(soap(bad))):
                with self.assertRaises(ValueError, msg=bad):
                    P.public_ipv4("192.168.178.1")

    def test_router_down_keeps_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            props = Path(tmp, "server.properties")
            props.write_text(PROPS)
            with mock.patch.object(P.urllib.request, "urlopen", side_effect=OSError("no route")):
                self.assertEqual(P.main(["mc-public-ip", str(props)]), 0, "never blocks the start")
            self.assertEqual(props.read_text(), PROPS)
            with mock.patch.object(P.urllib.request, "urlopen", return_value=FakeResponse(soap("8.8.4.4"))):
                P.main(["mc-public-ip", str(props)])
            self.assertEqual(props.read_text().count("server-udp-ports=8.8.4.4:"), 10)


if __name__ == "__main__":
    unittest.main()
