KUHLZZ.STORE SHORTENER — AIVEN MYSQL

Render settings
===============

Build Command:
    pip install -r requirements.txt

Start Command:
    gunicorn app:app

Environment variables
=====================

MYSQL_HOST
    Aiven MySQL host

MYSQL_PORT
    Aiven MySQL port, e.g. 12345

MYSQL_USER
    Aiven MySQL username

MYSQL_PASSWORD
    Aiven MySQL password

MYSQL_DATABASE
    Database name, often defaultdb unless you created another one

SHORTENER_API_KEY
    Long random secret used by the KUHLZZ desktop module

BASE_URL
    https://kuhlzz.store

Optional:
MYSQL_SSL_CA
    Filesystem path to an Aiven CA certificate if you explicitly mount/provide
    the CA file to Render.

Do NOT paste the whole mysql:// URI into any of the fields above.
Do NOT commit credentials to GitHub.

Endpoints
=========
GET    /health
POST   /api/v1/links
GET    /api/v1/links
DELETE /api/v1/links/<id>
GET    /<alias>

The management endpoints require:
    X-API-Key: <SHORTENER_API_KEY>

The short_links table is created automatically at application startup.
