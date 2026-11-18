import http.client
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
with patch.dict(os.environ, {"EDOPRO_DIR": "/nonexistent/ygo-test-fixture"}):
    spec = importlib.util.spec_from_file_location("collection_app", ROOT / "collection.py")
    app = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app)


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        edopro = self.root / "edopro"
        (edopro / "expansions").mkdir(parents=True)
        with closing(sqlite3.connect(edopro / "expansions/cards.cdb")) as db:
            db.executescript('''
                CREATE TABLE datas (id INTEGER, ot INTEGER, alias INTEGER, type INTEGER,
                                    atk INTEGER, def INTEGER, level INTEGER);
                CREATE TABLE texts (id INTEGER, name TEXT, desc TEXT);
                INSERT INTO datas VALUES (1, 3, 0, 1, 3000, 2500, 8),
                                         (2, 3, 0, 2, 0, 0, 0),
                                         (3, 3, 1, 1, 3000, 2500, 8),
                                         (4, 3, 0, 16385, 0, 0, 1);
                INSERT INTO texts VALUES (1, 'Blue-Eyes White Dragon', 'A dragon.'),
                                         (2, 'Test Spell', '</script><script>alert(1)</script>'),
                                         (3, 'Alternate art', ''), (4, 'Token', '');
            ''')
        settings = patch.multiple(app, EDOPRO=str(edopro), DATA_DIR=str(self.root),
                                  COLLECTION=str(self.root / "collection.json"),
                                  LFLIST=str(edopro / "lflists/Collection.lflist.conf"),
                                  PIC_DIRS=[str(self.root / "pics")], CACHE=str(self.root / "pics"))
        settings.start()
        self.addCleanup(settings.stop)
        cards = patch.object(app, "CARDS", app.load_cards())
        cards.start()
        self.addCleanup(cards.stop)
        self.server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            conn.request("GET" if body is None else "POST", path,
                         body=None if body is None else json.dumps(body),
                         headers=headers if headers is not None else {"Content-Type": "application/json"})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_search_and_database_filtering(self):
        self.assertEqual(set(app.CARDS), {1, 2})
        status, body = self.request("/api/search?q=blue%20eyes")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)[0]["id"], 1)

    def test_save_update_delete_and_banlist(self):
        self.assertEqual(app.read_collection(), {})
        self.assertEqual(self.request("/api/set", {"id": 1, "qty": 3})[0], 200)
        added = app.read_collection()["1"]["added"]
        self.assertIn("1 3 --Blue-Eyes White Dragon", Path(app.LFLIST).read_text())
        self.assertEqual(self.request("/api/set", {"id": 1, "qty": 2})[0], 200)
        self.assertEqual(app.read_collection()["1"]["added"], added)
        status, body = self.request("/api/collection")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)[0]["qty"], 2)
        self.assertEqual(self.request("/api/set", {"id": 1, "qty": 0})[0], 200)
        self.assertEqual(app.read_collection(), {})
        self.assertNotIn("1 2 --", Path(app.LFLIST).read_text())

    def test_invalid_requests_do_not_save(self):
        for body in ([], 1, {}, {"id": 1, "qty": 4}, {"id": 1, "qty": -1},
                     {"id": 1, "qty": 1.5}, {"id": 1, "qty": True}, {"id": 999, "qty": 1}):
            with self.subTest(body=body):
                self.assertEqual(self.request("/api/set", body)[0], 400)
        self.assertFalse(Path(app.COLLECTION).exists())

    def test_foreign_origins_hosts_and_forms_cannot_edit(self):
        body = {"id": 1, "qty": 1}
        status, _ = self.request("/api/set", body, {"Content-Type": "application/json", "Origin": "https://example.com"})
        self.assertEqual(status, 403)
        self.assertEqual(self.request("/api/collection", headers={"Host": "example.com"})[0], 403)
        self.assertEqual(self.request("/api/set", body, {"Content-Type": "text/plain"})[0], 415)
        self.assertFalse(Path(app.COLLECTION).exists())

    def test_corrupt_collection_is_not_treated_as_empty(self):
        for data in ('{"broken":', '[]', '{"1": {"qty": 8, "name": "test"}}'):
            Path(app.COLLECTION).write_text(data)
            with self.assertRaises(ValueError):
                app.read_collection()
            self.assertEqual(self.request("/api/collection")[0], 500)
            self.assertEqual(self.request("/api/set", {"id": 1, "qty": 2})[0], 500)
            self.assertEqual(Path(app.COLLECTION).read_text(), data)

    def test_export_is_standalone_escaped_and_does_not_change_data(self):
        self.request("/api/set", {"id": 1, "qty": 3})
        self.request("/api/set", {"id": 2, "qty": 1})
        pics = self.root / "pics"
        pics.mkdir()
        (pics / "1.png").write_bytes(b"\x89PNGfixture")
        original = Path(app.COLLECTION).read_bytes()
        banlist = Path(app.LFLIST).read_bytes()
        output = self.root / "showcase.html"
        app.export_collection(str(output))
        html = output.read_text()
        self.assertNotIn("const snapshot = null;", html)
        self.assertNotIn("</script><script>alert(1)</script>", html)
        data = html.split("const snapshot = ", 1)[1].split(";\nconst readOnly", 1)[0]
        cards = json.loads(data)
        self.assertEqual(len(cards), 2)
        self.assertTrue(cards[0]["image"].startswith("data:image/png;base64,"))
        self.assertEqual(cards[1]["image"], app.PIC_URL.format(2))
        self.assertTrue(cards[1]["fallback"].startswith("data:image/svg+xml;base64,"))
        self.assertEqual(Path(app.COLLECTION).read_bytes(), original)
        self.assertEqual(Path(app.LFLIST).read_bytes(), banlist)
        with self.assertRaises(FileExistsError):
            app.export_collection(str(output))
        with self.assertRaises(FileExistsError):
            app.export_collection(app.COLLECTION)
        self.assertEqual(Path(app.COLLECTION).read_bytes(), original)

    def test_empty_collection_export(self):
        output = self.root / "empty.html"
        app.export_collection(str(output))
        self.assertIn("const snapshot = [];", output.read_text())


if __name__ == "__main__":
    unittest.main()
