# log_traffic.py
# Logs requests to traffic.db (SQLite)
import sqlite3, os, time, tldextract
from mitmproxy import http, ctx
from datetime import datetime, timezone

DB_PATH = os.path.abspath("traffic.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc REAL NOT NULL,                 -- epoch seconds
  ts_iso TEXT NOT NULL,                 -- ISO8601 UTC
  method TEXT,
  url TEXT,
  scheme TEXT,
  host TEXT,
  domain TEXT,                          -- registrable domain (e.g., example.com)
  path TEXT,
  status INTEGER,
  req_bytes INTEGER,
  resp_bytes INTEGER,
  ua TEXT                               -- user-agent (if present)
);
CREATE INDEX IF NOT EXISTS idx_ts ON requests(ts_utc);
CREATE INDEX IF NOT EXISTS idx_domain ON requests(domain);
"""

def _connect():
  conn = sqlite3.connect(DB_PATH)
  conn.execute("PRAGMA journal_mode=WAL;")
  conn.execute("PRAGMA synchronous=NORMAL;")
  return conn

class Logger:
  def __init__(self):
    self.conn = None

  def load(self, loader):
    self.conn = _connect()
    self.conn.executescript(SCHEMA)
    ctx.log.info(f"Logging to {DB_PATH}")

  def done(self):
    if self.conn:
      self.conn.close()

  def request(self, flow: http.HTTPFlow):
    # We log on response (below) so we can capture status/resp size.

    # If you want immediate logging on request, implement here.
    pass

  def response(self, flow: http.HTTPFlow):
    try:
      ts = time.time()
      ts_iso = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

      url = flow.request.pretty_url
      scheme = flow.request.scheme
      host = flow.request.host
      path = flow.request.path
      method = flow.request.method

      ext = tldextract.extract(host)
      domain = ".".join([ext.domain, ext.suffix]) if ext.suffix else host

      status = flow.response.status_code
      req_bytes = len(flow.request.raw_content or b"")
      resp_bytes = len(flow.response.raw_content or b"")

      ua = ""
      try:
        ua = flow.request.headers.get("User-Agent", "")
      except:
        ua = ""

      self.conn.execute(
        """INSERT INTO requests
           (ts_utc, ts_iso, method, url, scheme, host, domain, path, status, req_bytes, resp_bytes, ua)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (ts, ts_iso, method, url, scheme, host, domain, path, status, req_bytes, resp_bytes, ua),
      )
      self.conn.commit()
    except Exception as e:
      ctx.log.warn(f"DB log error: {e}")

addons = [Logger()]