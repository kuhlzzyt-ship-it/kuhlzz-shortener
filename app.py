import os, re, secrets, string
from urllib.parse import urlparse
from flask import Flask, request, jsonify, redirect
import pymysql

app=Flask(__name__)

MYSQL_HOST=os.environ["MYSQL_HOST"]
MYSQL_PORT=int(os.getenv("MYSQL_PORT","3306"))
MYSQL_USER=os.environ["MYSQL_USER"]
MYSQL_PASSWORD=os.environ["MYSQL_PASSWORD"]
MYSQL_DATABASE=os.environ["MYSQL_DATABASE"]
MYSQL_SSL_CA=os.getenv("MYSQL_SSL_CA","").strip()

API_KEY=os.environ["SHORTENER_API_KEY"]
BASE_URL=os.getenv("BASE_URL","https://kuhlzz.store").rstrip("/")

ALIAS_RE=re.compile(r"^[A-Za-z0-9_-]{3,32}$")
RESERVED={"api","health","admin","login","register","static"}

def db():
    kwargs=dict(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
        connect_timeout=10,
        read_timeout=10,
        write_timeout=10,
    )
    # Aiven requires TLS. If a CA path is supplied, verify against it.
    # Otherwise request TLS; this works with Aiven deployments where the
    # platform/container trust store already contains the relevant CA chain.
    kwargs["ssl"]={"ca": MYSQL_SSL_CA} if MYSQL_SSL_CA else {}
    return pymysql.connect(**kwargs)

def init_db():
    con=db()
    try:
        with con.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS short_links(
                    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
                    alias VARCHAR(32) NOT NULL UNIQUE,
                    target_url TEXT NOT NULL,
                    clicks BIGINT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_clicked_at TIMESTAMP NULL DEFAULT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
        con.commit()
    finally:
        con.close()

def authorized():
    supplied=request.headers.get("X-API-Key","")
    return bool(supplied) and secrets.compare_digest(supplied,API_KEY)

def valid_target(value):
    try:
        u=urlparse(value)
        return u.scheme in ("http","https") and bool(u.netloc)
    except Exception:
        return False

def random_alias(n=6):
    chars=string.ascii_letters+string.digits
    return "".join(secrets.choice(chars) for _ in range(n))

def serialize(row):
    if not row:
        return row
    row=dict(row)
    for k,v in list(row.items()):
        if hasattr(v,"isoformat"):
            row[k]=v.isoformat()
    return row

@app.get("/health")
def health():
    return {"ok":True}

@app.post("/api/v1/links")
def create_link():
    if not authorized():
        return jsonify(error="unauthorized"),401

    data=request.get_json(silent=True) or {}
    target=(data.get("url") or "").strip()
    alias=(data.get("alias") or "").strip()

    if not valid_target(target):
        return jsonify(error="invalid_url"),400
    if alias and (not ALIAS_RE.fullmatch(alias) or alias.lower() in RESERVED):
        return jsonify(error="invalid_alias"),400

    for _ in range(8):
        candidate=alias or random_alias()
        con=db()
        try:
            with con.cursor() as cur:
                cur.execute(
                    "INSERT INTO short_links(alias,target_url) VALUES(%s,%s)",
                    (candidate,target),
                )
                link_id=cur.lastrowid
                cur.execute("SELECT * FROM short_links WHERE id=%s",(link_id,))
                row=cur.fetchone()
            con.commit()
            row=serialize(row)
            row["short_url"]=f"{BASE_URL}/{candidate}"
            return jsonify(row),201
        except pymysql.err.IntegrityError:
            con.rollback()
            if alias:
                return jsonify(error="alias_taken"),409
        finally:
            con.close()

    return jsonify(error="could_not_allocate_alias"),503

@app.get("/api/v1/links")
def list_links():
    if not authorized():
        return jsonify(error="unauthorized"),401

    con=db()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT * FROM short_links ORDER BY created_at DESC LIMIT 250")
            rows=cur.fetchall()
    finally:
        con.close()

    result=[]
    for row in rows:
        row=serialize(row)
        row["short_url"]=f"{BASE_URL}/{row['alias']}"
        result.append(row)
    return jsonify(result)

@app.delete("/api/v1/links/<int:link_id>")
def delete_link(link_id):
    if not authorized():
        return jsonify(error="unauthorized"),401

    con=db()
    try:
        with con.cursor() as cur:
            cur.execute("DELETE FROM short_links WHERE id=%s",(link_id,))
            deleted=cur.rowcount
        con.commit()
    finally:
        con.close()

    if not deleted:
        return jsonify(error="not_found"),404
    return "",204

@app.get("/<alias>")
def follow(alias):
    con=db()
    try:
        with con.cursor() as cur:
            cur.execute("SELECT target_url FROM short_links WHERE alias=%s",(alias,))
            row=cur.fetchone()
            if not row:
                return "Short link not found",404
            cur.execute(
                "UPDATE short_links SET clicks=clicks+1,last_clicked_at=CURRENT_TIMESTAMP WHERE alias=%s",
                (alias,),
            )
        con.commit()
    finally:
        con.close()

    return redirect(row["target_url"],code=302)

init_db()
