# BFC Access Review — Flask App

## Quick Start

### 1. Install dependencies
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your settings
```

### 3. Run
```bash
python app.py
```

Access at http://localhost:5000

Default admin: **admin@scor.com** / **Admin@1234**
> Change this password immediately after first login!

---

## Roles
- **admin** — uploads files, manages user accounts, sees monitoring dashboard
- **filter_owner** — sees only their own users (matched by `owner_key`), validates/deactivates

## Key mapping
The `owner_key` of each filter owner account must **exactly match** the value in the
`Data entry filter owner` column of the uploaded Excel file.

## Production deployment (Railway)
```bash
npm install -g @railway/cli
railway login
railway init
railway add postgresql
railway up
```
Set `SECRET_KEY` and `DATABASE_URL` in Railway dashboard environment variables.

## Production deployment (Render)
1. Push to GitHub
2. Create new Web Service on render.com
3. Add PostgreSQL database
4. Set environment variables
5. Build command: `pip install -r requirements.txt`
6. Start command: `gunicorn --workers 2 --bind 0.0.0.0:$PORT app:app`
