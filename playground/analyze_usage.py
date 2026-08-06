# analyze_usage.py
import sqlite3, os, pandas as pd, yaml, math
from datetime import datetime, timedelta
import pytz
import tldextract

DB_PATH = os.path.abspath("traffic.db")
CATS_PATH = os.path.abspath("categories.yml")

# CONFIG — adjust to your schedule & timezone
LOCAL_TZ = pytz.timezone("Asia/Bangkok")    # change if needed
WORK_START = (9, 0)     # 09:00
WORK_END   = (17, 30)   # 17:30
WORK_DAYS  = set([0,1,2,3,4])  # Mon–Fri
UA_BROWSER_HINTS = ["Chrome", "Firefox", "Safari", "Edg/"]  # crude filter

SESSION_GAP_MIN = 5     # minutes
SESSION_CAP_MIN = 15    # cap per continuous session

def load_categories():
  if os.path.exists(CATS_PATH):
    with open(CATS_PATH, "r", encoding="utf-8") as f:
      y = yaml.safe_load(f) or {}
  else:
    y = {}
  lookup = {}
  for cat, domains in y.items():
    for d in (domains or []):
      lookup[d.lower()] = cat
  return lookup

def is_browser_ua(ua:str) -> bool:
  if not ua: return False
  return any(h in ua for h in UA_BROWSER_HINTS)

def to_local(ts_utc: float) -> datetime:
  return datetime.fromtimestamp(ts_utc, pytz.UTC).astimezone(LOCAL_TZ)

def in_work_window(dt_local: datetime) -> bool:
  if dt_local.weekday() not in WORK_DAYS:
    return False
  start = dt_local.replace(hour=WORK_START[0], minute=WORK_START[1], second=0, microsecond=0)
  end   = dt_local.replace(hour=WORK_END[0], minute=WORK_END[1], second=0, microsecond=0)
  return start <= dt_local <= end

def read_requests():
  conn = sqlite3.connect(DB_PATH)
  df = pd.read_sql_query(
    "SELECT ts_utc, method, url, domain, status, req_bytes, resp_bytes, ua FROM requests ORDER BY ts_utc ASC",
    conn
  )
  conn.close()
  return df

def read_navigations():
  conn = sqlite3.connect(DB_PATH)
  try:
    df = pd.read_sql_query(
      "SELECT ts_utc, url, domain, title FROM navigations ORDER BY ts_utc ASC",
      conn
    )
  except Exception:
    df = pd.DataFrame(columns=["ts_utc","url","domain","title"])
  finally:
    conn.close()
  return df

def sessionize_browser(df_req):
  # Keep only browser-like traffic during working hours
  rows = []
  for _, row in df_req.iterrows():
    ts_local = to_local(row.ts_utc)
    if in_work_window(ts_local) and is_browser_ua(row.ua or ""):
      rows.append({
        "ts_utc": row.ts_utc,
        "local": ts_local,
        "domain": (row.domain or "").lower()
      })
  if not rows:
    return pd.DataFrame(columns=["day","domain","active_minutes"])

  df = pd.DataFrame(rows).sort_values("local")
  results = []

  # Group by domain per day, then create sessions by gaps
  df["day"] = df["local"].dt.date
  for (day, domain), g in df.groupby(["day","domain"]):
    g = g.sort_values("local")
    session_start = g.iloc[0]["local"]
    last_time = session_start
    total = 0.0

    for i in range(1, len(g)):
      t = g.iloc[i]["local"]
      gap = (t - last_time).total_seconds() / 60.0
      if gap > SESSION_GAP_MIN:
        # close session
        sess_dur = min((last_time - session_start).total_seconds()/60.0 + SESSION_GAP_MIN, SESSION_CAP_MIN)
        total += max(0.0, sess_dur)
        session_start = t
      last_time = t

    # close final session
    sess_dur = min((last_time - session_start).total_seconds()/60.0 + SESSION_GAP_MIN, SESSION_CAP_MIN)
    total += max(0.0, sess_dur)

    results.append({"day": day, "domain": domain, "active_minutes": round(total,1)})

  return pd.DataFrame(results)

def categorize(df, cat_lookup):
  def cat_of(domain):
    # try full domain, then registrable
    d = domain.lower()
    if d in cat_lookup:
      return cat_lookup[d]
    ext = tldextract.extract(d)
    reg = ".".join([ext.domain, ext.suffix]) if ext.suffix else d
    return cat_lookup.get(reg.lower(), "uncategorized")
  df["category"] = df["domain"].apply(cat_of)
  return df

def main():
  df_req = read_requests()
  df_nav = read_navigations()

  # Sessionize (browser-ish only) during working hours
  sessions = sessionize_browser(df_req)

  if sessions.empty:
    print("No browser sessions found in working hours.")
    return

  cat_lookup = load_categories()
  sessions = categorize(sessions, cat_lookup)

  # Summaries
  by_domain = sessions.groupby(["day","domain","category"], as_index=False)["active_minutes"].sum()
  by_cat = sessions.groupby(["day","category"], as_index=False)["active_minutes"].sum()

  # Export CSVs
  out_dir = os.path.abspath("usage_reports")
  os.makedirs(out_dir, exist_ok=True)
  by_domain.to_csv(os.path.join(out_dir, "by_domain.csv"), index=False)
  by_cat.to_csv(os.path.join(out_dir, "by_category.csv"), index=False)

  # Show today’s (local) snapshot
  today = datetime.now(LOCAL_TZ).date()
  td = by_domain[by_domain["day"] == today].sort_values("active_minutes", ascending=False)
  tc = by_cat[by_cat["day"] == today].sort_values("active_minutes", ascending=False)

  print(f"\n=== {today} Working-hours online time (estimated) ===")
  if not tc.empty:
    print("\nBy category:")
    for _, r in tc.iterrows():
      print(f"  {r['category']:<14} {r['active_minutes']:>6.1f} min")

  if not td.empty:
    print("\nTop domains:")
    for _, r in td.head(15).iterrows():
      print(f"  {r['domain']:<35} {r['active_minutes']:>6.1f} min  [{r['category']}]")

  print(f"\nCSV saved in: {out_dir}")

if __name__ == "__main__":
  main()