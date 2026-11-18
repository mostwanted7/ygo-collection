#!/usr/bin/env python3
"""Yu-Gi-Oh! collection tracker: search cards by name, keep 1-3 copies of each, see them by picture.

Card names come from the EDOPro install's databases; pictures from EDOPro's pics folder, else downloaded from the
URL EDOPro uses and cached. The collection is collection.json next to this file.
Every save also rewrites the EDOPro banlist "Collection" (lflists/Collection.lflist.conf in the EDOPro folder): pick it
in EDOPro's deck editor to build only from owned cards, each limited to the copies owned. EDOPro reads banlists at
startup, so restart it to see changes.
Stdlib only: `./ygo-collection` starts the local server and opens the app window.
Use `./ygo-collection --export FILE.html` to create a read-only showcase.
"""

import argparse
import base64
import glob
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST, PORT = "127.0.0.1", 8737
HERE = os.path.dirname(os.path.abspath(__file__))
EDOPRO = os.path.expanduser(os.environ.get("EDOPRO_DIR", "~/Games/ProjectIgnis"))
DATA_DIR = HERE
COLLECTION = os.path.join(DATA_DIR, "collection.json")
CACHE = os.path.expanduser("~/.cache/ygo-collection/pics")
PIC_DIRS = [os.path.join(EDOPRO, "pics"), os.path.expanduser("~/.cache/ygo-agent/pics"), CACHE]
PIC_URL = "https://pics.projectignis.org:2096/pics/{}.jpg"
MAGIC = (b"\xff\xd8\xff", b"\x89PNG")
TOKEN, MONSTER, SPELL, TRAP = 0x4000, 0x1, 0x2, 0x4
LFLIST = os.path.join(EDOPRO, "lflists", "Collection.lflist.conf")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_cards():
    """{id: card} for every official (OCG/TCG) card, newest database last so updates win. Alternate artworks and
    tokens are left out: a collection counts a card once by name."""
    dbs = [os.path.join(EDOPRO, "expansions", "cards.cdb")]
    repos = os.path.join(EDOPRO, "repositories")
    dbs += sorted(glob.glob(os.path.join(repos, "*", "cards.delta.cdb")))
    dbs += sorted(glob.glob(os.path.join(repos, "*", "release-*.cdb")))
    cards = {}
    for path in dbs:
        if not os.path.isfile(path):
            continue
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT d.id, d.ot, d.alias, d.type, d.atk, d.def, d.level, t.name, t.desc "
                               "FROM datas d JOIN texts t ON t.id = d.id").fetchall()
        finally:
            con.close()
        for cid, ot, alias, typ, atk, de, level, name, desc in rows:
            if not name or not (ot & 3) or typ & TOKEN or alias:
                continue
            kind = "monster" if typ & MONSTER else "spell" if typ & SPELL else "trap" if typ & TRAP else "other"
            cards[cid] = {"id": cid, "name": name, "desc": desc or "", "kind": kind, "type": typ,
                          "atk": atk, "def": de, "level": level & 0xFF, "n": norm(name)}
    return cards


CARDS = load_cards()
_lock = threading.Lock()


def read_collection():
    try:
        with open(COLLECTION, encoding="utf-8") as f:
            col = json.load(f)
    except FileNotFoundError:
        return {}
    if not isinstance(col, dict) or any(
        not k.isdigit() or not isinstance(v, dict)
        or not isinstance(v.get("name"), str)
        or type(v.get("qty")) is not int or not 1 <= v["qty"] <= 3
        or type(v.get("added", 0)) not in (int, float)
        for k, v in col.items()
    ):
        raise ValueError("Invalid collection data; restore a backup before continuing.")
    return col


def write_collection(col):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = COLLECTION + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(col, f, indent=1, ensure_ascii=False)
    os.replace(tmp, COLLECTION)
    write_banlist(col)


def write_banlist(col):
    """Write the collection as an EDOPro banlist. With $whitelist, every card not listed is forbidden; each listed
    card is limited to its count. Alternate artworks count as their main card in EDOPro, so only main IDs are listed."""
    owned = sorted((v["name"], int(k), v["qty"]) for k, v in col.items())
    lines = ["#[Collection]", "!Collection", "$whitelist", "#Owned cards: limited to the copies owned"]
    lines += [f"{cid} {qty} --{name}" for name, cid, qty in owned]
    tmp = LFLIST + ".tmp"
    try:
        os.makedirs(os.path.dirname(LFLIST), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, LFLIST)
    except OSError as e:
        print(f"Could not write the EDOPro banlist {LFLIST}: {e}", file=sys.stderr)


def public(card, qty=None, added=None):
    out = {k: card[k] for k in ("id", "name", "desc", "kind", "type", "atk", "def", "level")}
    if qty is not None:
        out["qty"], out["added"] = qty, added
    return out


def collection_cards(col):
    return [public(CARDS[int(k)], v["qty"], v.get("added", 0)) for k, v in col.items() if int(k) in CARDS]


def export_collection(destination):
    """Create a read-only HTML snapshot, embedding artwork already available locally."""
    cards = collection_cards(read_collection())
    for card in cards:
        card["image"] = PIC_URL.format(card["id"])
        for folder in PIC_DIRS:
            found = False
            for ext in ("jpg", "png"):
                path = os.path.join(folder, f'{card["id"]}.{ext}')
                if os.path.isfile(path):
                    with open(path, "rb") as f:
                        data = f.read()
                    mime = "image/png" if data.startswith(MAGIC[1]) else "image/jpeg"
                    card["image"] = f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
                    found = True
                    break
            if found:
                break
        card["fallback"] = "data:image/svg+xml;base64," + base64.b64encode(placeholder(card["id"])).decode("ascii")
    with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
        html = f.read()
    # Escape '<' so even a card description containing </script> stays JSON data.
    data = json.dumps(cards, ensure_ascii=True).replace("<", "\\u003c")
    html = html.replace("const snapshot = null;", f"const snapshot = {data};")
    destination = os.path.abspath(os.path.expanduser(destination))
    # Never overwrite the app, a collection backup, or an existing export accidentally.
    with open(destination, "x", encoding="utf-8") as f:
        f.write(html)
    print(f"Exported {len(cards)} cards to {destination}")


def search(q, limit=60):
    nq = norm(q)
    if not nq:
        return []
    words = [norm(w) for w in q.split() if norm(w)]
    hits = []
    for c in CARDS.values():
        n = c["n"]
        if nq in n:
            rank = 0 if n == nq else 1 if n.startswith(nq) else 2
        elif all(w in n for w in words):
            rank = 3
        else:
            continue
        hits.append((rank, len(c["name"]), c["name"], c))
    hits.sort(key=lambda h: h[:3])
    return [public(h[3]) for h in hits[:limit]]


_pic_locks, _failed = {}, {}


def pic_path(cid):
    for folder in PIC_DIRS:
        for ext in ("jpg", "png"):
            p = os.path.join(folder, f"{cid}.{ext}")
            if os.path.isfile(p):
                return p
    with _lock:
        lock = _pic_locks.setdefault(cid, threading.Lock())
    with lock:
        p = os.path.join(CACHE, f"{cid}.jpg")
        if os.path.isfile(p):
            return p
        if time.time() - _failed.get(cid, 0) < 600:
            return None
        try:
            req = urllib.request.Request(PIC_URL.format(cid), headers={"User-Agent": "ygo-collection"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read(4 << 20)
        except (OSError, ValueError):
            data = b""
        if not data.startswith(MAGIC):
            _failed[cid] = time.time()
            return None
        os.makedirs(CACHE, exist_ok=True)
        tmp = f"{p}.{threading.get_ident()}.tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, p)
        return p


def placeholder(cid):
    card = CARDS.get(cid)
    name = card["name"] if card else f"#{cid}"
    color = {"monster": "#c5873a", "spell": "#1d8a6b", "trap": "#a23a7d"}.get(card and card["kind"], "#3a4256")
    rows, cur = [], ""
    for w in name.split():
        if cur and len(cur) + len(w) + 1 > 16:
            rows.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    rows.append(cur)
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    spans = "".join(f'<tspan x="88" dy="{0 if i == 0 else 19}">{esc(r)}</tspan>' for i, r in enumerate(rows[:5]))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="177" height="254" viewBox="0 0 177 254">'
            f'<rect width="177" height="254" rx="8" fill="{color}"/>'
            f'<rect x="9" y="9" width="159" height="236" rx="5" fill="#141822" opacity="0.92"/>'
            f'<text x="88" y="90" text-anchor="middle" font-family="sans-serif" font-size="15" font-weight="700" '
            f'fill="#eef1f7">{spans}</text></svg>').encode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype="application/json", status=200, cache=False):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.valid_host():
            return self.send({"error": "invalid host"}, status=403)
        url = urllib.parse.urlsplit(self.path)
        qs = urllib.parse.parse_qs(url.query)
        if url.path == "/":
            with open(os.path.join(HERE, "index.html"), "rb") as f:
                return self.send(f.read(), "text/html; charset=utf-8")
        if url.path == "/api/search":
            return self.send(search(qs.get("q", [""])[0]))
        if url.path == "/api/collection":
            try:
                with _lock:
                    col = read_collection()
            except (OSError, ValueError):
                return self.send({"error": "cannot read collection; check the file or restore a backup"}, status=500)
            return self.send(collection_cards(col))
        m = re.fullmatch(r"/pic/(\d+)", url.path)
        if m:
            cid = int(m.group(1))
            p = pic_path(cid)
            if p:
                with open(p, "rb") as f:
                    data = f.read()
                return self.send(data, "image/png" if data.startswith(MAGIC[1]) else "image/jpeg", cache=True)
            return self.send(placeholder(cid), "image/svg+xml")
        if url.path == "/api/ping":
            return self.send({"app": "ygo-collection"})
        self.send({"error": "not found"}, status=404)

    def do_POST(self):
        if not self.valid_host() or self.headers.get("Origin", f"http://{self.headers.get('Host')}") not in (
            f"http://{HOST}:{self.server.server_port}", f"http://localhost:{self.server.server_port}"
        ):
            return self.send({"error": "invalid origin"}, status=403)
        if self.path != "/api/set":
            return self.send({"error": "not found"}, status=404)
        if self.headers.get_content_type() != "application/json":
            return self.send({"error": "expected application/json"}, status=415)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 1024:
                raise ValueError("invalid body size")
            body = json.loads(self.rfile.read(length))
            cid, qty = body["id"], body["qty"]
            if type(cid) is not int or type(qty) is not int:
                raise ValueError("expected integers")
        except (ValueError, KeyError, TypeError):
            return self.send({"error": "bad request"}, status=400)
        if cid not in CARDS or not 0 <= qty <= 3:
            return self.send({"error": "bad card or quantity"}, status=400)
        with _lock:
            try:
                col = read_collection()
            except (OSError, ValueError):
                return self.send({"error": "cannot read collection; check the file or restore a backup"}, status=500)
            if qty == 0:
                col.pop(str(cid), None)
            else:
                col[str(cid)] = {"name": CARDS[cid]["name"], "qty": qty,
                                 "added": col.get(str(cid), {}).get("added") or int(time.time())}
            try:
                write_collection(col)
            except OSError:
                return self.send({"error": "could not write collection; check disk space and permissions"}, status=500)
        self.send({"ok": True})

    def valid_host(self):
        return self.headers.get("Host") in (f"{HOST}:{self.server.server_port}", f"localhost:{self.server.server_port}")


def running():
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}/api/ping", timeout=1) as r:
            return json.load(r).get("app") == "ygo-collection"
    except (OSError, ValueError):
        return False


def open_window():
    url = f"http://{HOST}:{PORT}/"
    for browser in ("brave-browser", "chromium", "google-chrome"):
        if shutil.which(browser):
            subprocess.Popen([browser, f"--app={url}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            return
    if shutil.which("xdg-open"):
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    else:
        print(f"Open {url} in your browser.")


def main():
    global PORT
    parser = argparse.ArgumentParser(description="Track your Yu-Gi-Oh! collection locally using EDOPro's card database.")
    parser.add_argument("--no-open", action="store_true", help="start without opening a browser")
    parser.add_argument("--port", type=int, default=8737, help="local server port (default: 8737)")
    parser.add_argument("--export", metavar="FILE.html", help="save a read-only collection snapshot and exit (file must not exist)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    PORT = args.port
    if args.export:
        if not CARDS:
            parser.error(f"No card database found under {EDOPRO}. Set EDOPRO_DIR to your EDOPro folder.")
        try:
            export_collection(args.export)
        except (OSError, ValueError) as e:
            sys.exit(f"Could not export collection: {e}")
        return
    if running():
        if not args.no_open:
            open_window()
        return
    if not CARDS:
        sys.exit(f"No card database found under {EDOPRO} (set EDOPRO_DIR).")
    try:
        write_banlist(read_collection())
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except (OSError, ValueError) as e:
        sys.exit(f"Could not start YGO Collection: {e}")
    print(f"{len(CARDS)} cards loaded. Collection: {COLLECTION}\nEDOPro banlist: {LFLIST}\nServing http://{HOST}:{PORT}/ (Ctrl+C to stop)")
    if not args.no_open:
        threading.Timer(0.3, open_window).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
