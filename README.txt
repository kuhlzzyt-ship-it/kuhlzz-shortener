KUHLZZ.STORE SHORTENER BACKEND

Render:
Build command: pip install -r requirements.txt
Start command: gunicorn app:app

Environment variables:
DATABASE_URL = your Aiven PostgreSQL service URI
SHORTENER_API_KEY = a long random secret
BASE_URL = https://kuhlzz.store

After deployment, add kuhlzz.store as the Render custom domain and configure the DNS records Render shows you.

API:
POST /api/v1/links   Header X-API-Key
GET  /api/v1/links   Header X-API-Key
DELETE /api/v1/links/<id> Header X-API-Key
GET /<alias> redirects publicly.
