import os, re, secrets, string
from urllib.parse import urlparse
from flask import Flask, request, jsonify, redirect
import psycopg
from psycopg.rows import dict_row

app=Flask(__name__)
DATABASE_URL=os.environ["DATABASE_URL"]
API_KEY=os.environ["SHORTENER_API_KEY"]
BASE_URL=os.getenv("BASE_URL","https://kuhlzz.store").rstrip("/")
ALIAS_RE=re.compile(r"^[A-Za-z0-9_-]{3,32}$")
RESERVED={"api","health","admin","login","register","static"}

def db():
    return psycopg.connect(DATABASE_URL,row_factory=dict_row)

def init_db():
    with db() as con, con.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS short_links(
          id BIGSERIAL PRIMARY KEY,
          alias VARCHAR(32) UNIQUE NOT NULL,
          target_url TEXT NOT NULL,
          clicks BIGINT NOT NULL DEFAULT 0,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          last_clicked_at TIMESTAMPTZ
        )
        """)

def authorized():
    return secrets.compare_digest(request.headers.get("X-API-Key",""),API_KEY)

def valid_target(value):
    try:
        u=urlparse(value)
        return u.scheme in ("http","https") and bool(u.netloc)
    except Exception:
        return False

def random_alias(n=6):
    chars=string.ascii_letters+string.digits
    return "".join(secrets.choice(chars) for _ in range(n))

@app.get("/health")
def health():
    return {"ok":True}

@app.post("/api/v1/links")
def create_link():
    if not authorized(): return jsonify(error="unauthorized"),401
    data=request.get_json(silent=True) or {}
    target=(data.get("url") or "").strip()
    alias=(data.get("alias") or "").strip()
    if not valid_target(target): return jsonify(error="invalid_url"),400
    if alias and (not ALIAS_RE.fullmatch(alias) or alias.lower() in RESERVED):
        return jsonify(error="invalid_alias"),400
    with db() as con, con.cursor() as cur:
        for _ in range(8):
            candidate=alias or random_alias()
            try:
                cur.execute("INSERT INTO short_links(alias,target_url) VALUES(%s,%s) RETURNING *",
                            (candidate,target))
                row=cur.fetchone()
                return jsonify({**row,"short_url":f"{BASE_URL}/{candidate}"}),201
            except psycopg.errors.UniqueViolation:
                con.rollback()
                if alias: return jsonify(error="alias_taken"),409
        return jsonify(error="could_not_allocate_alias"),503

@app.get("/api/v1/links")
def list_links():
    if not authorized(): return jsonify(error="unauthorized"),401
    with db() as con, con.cursor() as cur:
        cur.execute("SELECT * FROM short_links ORDER BY created_at DESC LIMIT 250")
        rows=cur.fetchall()
    return jsonify([{**r,"short_url":f"{BASE_URL}/{r['alias']}"} for r in rows])

@app.delete("/api/v1/links/<int:link_id>")
def delete_link(link_id):
    if not authorized(): return jsonify(error="unauthorized"),401
    with db() as con, con.cursor() as cur:
        cur.execute("DELETE FROM short_links WHERE id=%s RETURNING id",(link_id,))
        if not cur.fetchone(): return jsonify(error="not_found"),404
    return "",204

@app.get("/<alias>")
def follow(alias):
    with db() as con, con.cursor() as cur:
        cur.execute("""
          UPDATE short_links SET clicks=clicks+1,last_clicked_at=NOW()
          WHERE alias=%s RETURNING target_url
        """,(alias,))
        row=cur.fetchone()
    if not row: return "Short link not found",404
    return redirect(row["target_url"],code=302)

with app.app_context():
    init_db()
