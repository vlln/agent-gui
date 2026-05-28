#!/usr/bin/env python3
"""Agent GUI Bridge — zero-dependency HTTP/WebSocket relay."""

import argparse, asyncio, base64, hashlib, json, os, struct
from pathlib import Path
from http import HTTPStatus

PORT = int(os.environ.get("PORT", 3001))
ACTION_FILE = Path("/tmp/agent-gui-actions.jsonl")
RUNTIME_HTML = (Path(__file__).parent.parent / "resources" / "runtime.html").read_text()

# ── State ──
browser_writer = None  # asyncio.StreamWriter for the connected browser
current_html = None     # latest full-page snapshot
action_queue = []       # pending actions (in-memory)
action_event = asyncio.Event()  # signaled when a new action arrives

# ── WebSocket helpers ──
WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

def ws_accept(key: str) -> str:
    return base64.b64encode(
        hashlib.sha1((key + WS_GUID).encode()).digest()
    ).decode()

def ws_encode(payload: str) -> bytes:
    """Text frame, server→client (unmasked)."""
    data = payload.encode()
    n = len(data)
    frame = bytearray([0x81])  # FIN + text
    if n < 126:
        frame.append(n)
    elif n < 65536:
        frame.append(126)
        frame += struct.pack(">H", n)
    else:
        frame.append(127)
        frame += struct.pack(">Q", n)
    return bytes(frame) + data

def ws_decode(buf: bytes) -> tuple[str | None, bytes]:
    """Decode one masked text frame. Returns (payload, remaining_buf) or (None, buf) if incomplete."""
    if len(buf) < 2:
        return None, buf
    opcode = buf[0] & 0x0F
    if opcode == 0x8:  # close
        return "__close__", b""
    length = buf[1] & 0x7F
    offset = 2
    if length == 126:
        if len(buf) < 4: return None, buf
        length = struct.unpack(">H", buf[2:4])[0]
        offset = 4
    elif length == 127:
        if len(buf) < 10: return None, buf
        length = struct.unpack(">Q", buf[2:10])[0]
        offset = 10
    total = offset + 4 + length  # header + mask + payload
    if len(buf) < total:
        return None, buf
    mask = buf[offset:offset + 4]
    payload = bytes(b ^ mask[i % 4] for i, b in enumerate(buf[offset + 4:total]))
    return payload.decode(), buf[total:]

# ── HTTP helpers ──

def parse_http(data: bytes) -> tuple[str, str, dict, str]:
    head, _, body = data.partition(b"\r\n\r\n")
    lines = head.decode().split("\r\n")
    method, path, *_ = lines[0].split(" ")
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return method, path, headers, body.decode()

def http_response(status=200, body="", content_type="application/json"):
    data = body.encode() if isinstance(body, str) else body
    header = (
        f"HTTP/1.1 {status} {HTTPStatus(status).phrase}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(data)}\r\n"
        f"Connection: close\r\n\r\n"
    )
    return header.encode() + data

def json_response(data, status=200):
    return http_response(status, json.dumps(data))

# ── Routing ──

async def handle_init(body: str) -> bytes:
    global current_html
    try:
        req = json.loads(body)
        html = req.get("html")
        if not html and req.get("file"):
            html = Path(req["file"]).read_text()
        if not html:
            return json_response({"error": "html or file required"}, 400)
        current_html = html
        ok = await ws_send({"type": "init", "html": html})
        return json_response({"ok": ok})
    except FileNotFoundError:
        return json_response({"error": "File not found"}, 400)
    except json.JSONDecodeError:
        return json_response({"error": "Invalid JSON"}, 400)

async def handle_update(body: str) -> bytes:
    try:
        updates = json.loads(body)
        ok = await ws_send({"type": "update", "updates": updates})
        return json_response({"ok": ok})
    except json.JSONDecodeError:
        return json_response({"error": "Invalid JSON"}, 400)

async def handle_wait(timeout: float | None = None) -> bytes:
    if action_queue:
        return json_response(action_queue.pop(0))
    try:
        await asyncio.wait_for(action_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        return json_response(None)
    if action_queue:
        return json_response(action_queue.pop(0))
    return json_response(None)

def handle_status() -> bytes:
    return json_response({"browserConnected": browser_writer is not None})

ROUTES = {
    ("GET", "/"): lambda: http_response(200, RUNTIME_HTML, "text/html; charset=utf-8"),
    ("GET", "/status"): handle_status,
}

# ── WebSocket send ──

async def ws_send(msg: dict) -> bool:
    if browser_writer is None:
        return False
    try:
        browser_writer.write(ws_encode(json.dumps(msg)))
        await browser_writer.drain()
        return True
    except Exception:
        return False

# ── Connection handler ──

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global browser_writer, current_html

    # Read HTTP request
    data = await reader.read(4096)
    if not data:
        writer.close(); return

    method, path, headers, body = parse_http(data)

    # ── WebSocket upgrade ──
    if headers.get("upgrade", "").lower() == "websocket":
        key = headers.get("sec-websocket-key", "")
        writer.write(
            f"HTTP/1.1 101 Switching Protocols\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {ws_accept(key)}\r\n\r\n".encode()
        )
        await writer.drain()

        # Replace previous browser connection
        browser_writer = writer

        # Restore: send latest snapshot
        if current_html:
            writer.write(ws_encode(json.dumps({"type": "init", "html": current_html})))
            await writer.drain()

        # Read loop
        buf = b""
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                buf += chunk
                while True:
                    payload, buf = ws_decode(buf)
                    if payload is None:
                        break
                    if payload == "__close__":
                        writer.close()
                        return
                    try:
                        msg = json.loads(payload)
                        if msg.get("type") == "action":
                            action_queue.append(msg)
                            action_file_log(msg)
                            action_event.set()  # wake /wait
                            action_event.clear()
                        elif msg.get("type") == "snapshot":
                            current_html = msg["html"]
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass
        finally:
            if browser_writer is writer:
                browser_writer = None
            writer.close()
        return

    # ── HTTP routes ──
    parsed_path = path.split("?")[0]
    query_string = path.split("?")[1] if "?" in path else ""
    query_params = {}
    if query_string:
        for pair in query_string.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                query_params[k] = v

    route_key = (method, parsed_path)
    handler = ROUTES.get(route_key)

    if parsed_path == "/wait" and method == "GET":
        timeout = None
        if "timeout" in query_params:
            try:
                timeout = float(query_params["timeout"])
            except ValueError:
                pass
        writer.write(await handle_wait(timeout))
    elif handler:
        writer.write(handler())
    elif method == "POST" and path.startswith("/"):
        raw_body = body
        if headers.get("content-length") and len(raw_body) < int(headers["content-length"]):
            raw_body += (await reader.read()).decode()
        if path.startswith("/init"):
            writer.write(await handle_init(raw_body))
        elif path.startswith("/update"):
            writer.write(await handle_update(raw_body))
        else:
            writer.write(http_response(404, json.dumps({"error": "Not found"})))
    else:
        writer.write(http_response(404, json.dumps({"error": "Not found"})))

    await writer.drain()
    writer.close()

# ── Action file persistence ──

def action_file_log(msg: dict):
    import fcntl
    try:
        line = json.dumps(msg) + "\n"
        with open(ACTION_FILE, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.write(line)
            fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        pass  # best-effort

# ── Main ──

async def main():
    try:
        server = await asyncio.start_server(handle_client, "0.0.0.0", PORT)
    except OSError as e:
        if e.errno == 98:  # EADDRINUSE
            print(f"Port {PORT} is already in use. Kill the existing process or set PORT= in env.")
        else:
            print(f"Error: {e}")
        return

    print(f"Agent GUI bridge running at http://localhost:{PORT}")
    print(f"Open browser to http://localhost:{PORT}")
    print(f"POST /init   — send initial HTML")
    print(f"POST /update — send region updates")
    print(f"GET  /wait   — pop next action (blocking; ?timeout=0 for non-blocking)")
    print(f"GET  /status — browser connection status")
    print(f"Actions also written to {ACTION_FILE}")

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Agent GUI Bridge")
    p.add_argument("--port", "-p", type=int, default=PORT,
                   help=f"Listen port (default: {PORT}, env: PORT)")
    args = p.parse_args()
    PORT = args.port
    asyncio.run(main())
