import logging

import uvicorn

from .config import load
from .main import SHUTTING_DOWN, create_app


class Server(uvicorn.Server):
    def handle_exit(self, sig, frame):
        # Let live views (SSE) close themselves before uvicorn waits for open connections.
        SHUTTING_DOWN.set()
        super().handle_exit(sig, frame)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = load()
    config = uvicorn.Config(create_app(cfg), host=cfg.host, port=cfg.port, log_level="info",
                            access_log=False, timeout_graceful_shutdown=5)
    Server(config).run()


if __name__ == "__main__":
    main()
