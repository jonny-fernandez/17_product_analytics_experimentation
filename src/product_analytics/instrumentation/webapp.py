"""Loopback-only consent-aware browser demo. No user authentication or cloud hosting."""
from __future__ import annotations

import argparse
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
from urllib.parse import urlparse

from .core import EventStore, ID_PATTERN, iso, utc_now

WEB_DIR = Path(__file__).resolve().parents[3] / "web"


def create_handler(store: EventStore):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Do not log addresses, query parameters, request bodies or identifiers.
            pass

        def response(self, status, payload):
            body = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/api/status":
                monitor = store.monitor()
                gated = store.governed_metrics()
                return self.response(200, {"monitor": monitor, "release": gated["status"],
                                           "reason": gated.get("reason"),
                                           "notice": "Synthetic local browser traffic; seven-day metrics blocked until mature"})
            if self.path == "/health":
                return self.response(200, {"status": "ok", "mode": "local_synthetic_only"})
            file = {"/": "index.html", "/app.js": "app.js"}.get(self.path)
            if file is None:
                return self.response(404, {"error": "not_found"})
            data = (WEB_DIR / file).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript; charset=utf-8" if file.endswith(".js")
                             else "text/html; charset=utf-8")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path not in ("/api/start", "/api/event", "/api/purchase"):
                return self.response(404, {"error": "not_found"})
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                return self.response(415, {"error": "json_only"})
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).hostname not in ("localhost", "127.0.0.1"):
                return self.response(403, {"error": "cross_origin_blocked"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 2048:
                    raise ValueError("size")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("object")
            except (ValueError, json.JSONDecodeError):
                return self.response(400, {"error": "invalid_json"})
            if self.path == "/api/start":
                if data != {"consent": True}:
                    return self.response(403, {"error": "consent_required"})
                user_id, session_id = "u_"+secrets.token_hex(8), "s_"+secrets.token_hex(8)
                store.add_session(user_id=user_id, session_id=session_id, consent=True)
                start = utc_now() - timedelta(milliseconds=25)
                for i, name in enumerate(("experiment_assigned", "session_started", "experiment_exposed")):
                    event = {"schema_version": 1, "event_id": "evt_"+secrets.token_hex(10),
                             "user_id": user_id, "session_id": None if i == 0 else session_id,
                             "source": "server", "name": name,
                             "occurred_at": iso(start + timedelta(milliseconds=i)), "properties": {}}
                    result = store.ingest(event, received_at=start + timedelta(milliseconds=i + 1))
                    if result["status"] != "accepted":
                        return self.response(500, {"error": "instrumentation_unavailable"})
                return self.response(200, {"user_id": user_id, "session_id": session_id,
                                           "tracking_version": 1})
            if self.path == "/api/event":
                # HTTP boundary fixes the source: browsers cannot claim server-side purchases.
                if data.get("name") not in ("product_viewed", "cart_item_added", "checkout_started"):
                    return self.response(403, {"error": "client_event_not_allowed"})
                safe = {"schema_version": data.get("schema_version"), "event_id": data.get("event_id"),
                        "user_id": data.get("user_id"), "session_id": data.get("session_id"),
                        "name": data.get("name"), "occurred_at": data.get("occurred_at"),
                        "source": "client", "properties": data.get("properties", {})}
                if set(data) != set(safe) - {"source"}:
                    return self.response(400, {"error": "unknown_property"})
                outcome = store.ingest(safe)
                return self.response(200 if outcome["status"] in ("accepted", "duplicate") else 422, outcome)
            if set(data) != {"user_id", "session_id"}:
                return self.response(400, {"error": "unknown_property"})
            uid, sid = data.get("user_id"), data.get("session_id")
            if not isinstance(uid, str) or not isinstance(sid, str) or not ID_PATTERN.fullmatch(uid) or not ID_PATTERN.fullmatch(sid):
                return self.response(400, {"error": "synthetic_ids_required"})
            # A server-side confirmation is only available following the checked-out demo journey.
            frame = store.frame()
            ordered = frame[(frame.user_id == uid) & (frame.session_id == sid)].sort_values("event_timestamp")
            steps = list(ordered.event_name)
            if not all(x in steps for x in ("view_item", "add_to_cart", "begin_checkout")) or "purchase" in steps:
                return self.response(409, {"error": "complete_checkout_first"})
            event = {"schema_version": 1, "event_id": "evt_"+secrets.token_hex(10),
                     "user_id": uid, "session_id": sid, "name": "order_purchased", "source": "server",
                     "occurred_at": iso(utc_now()), "properties": {"revenue": 25.0}}
            outcome = store.ingest(event)
            return self.response(200 if outcome["status"] == "accepted" else 422, outcome)
    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=Path("artifacts/instrumentation_web/events.sqlite"))
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("port must be between 1024 and 65535")
    store = EventStore(args.db)
    print(f"Local-only synthetic instrumentation: http://127.0.0.1:{args.port}", flush=True)
    with ThreadingHTTPServer(("127.0.0.1", args.port), create_handler(store)) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
