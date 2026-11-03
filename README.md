# Shop Billing Machine — PostgreSQL Edition

## This version
- Uses hosted PostgreSQL for durable stock and bill records.
- Supports product management, billing, stock deduction, Excel export, and WhatsApp click-to-chat.
- WhatsApp message is prefilled; the user must press Send.
- Intended as a starter app; add authentication and backups before production use.

## Requirements
Python 3.10+; PostgreSQL database connection string.

## Run locally
```bash
pip install -r requirements.txt
```
Set environment variable `DATABASE_URL` to a PostgreSQL connection string, then:
```bash
streamlit run app.py
```

## Render
Build command:
```bash
pip install -r requirements.txt
```
Start command:
```bash
streamlit run app.py --server.port $PORT --server.address 0.0.0.0
```
Add environment variable:
- `DATABASE_URL` = your hosted PostgreSQL connection string

Do not set `BILLING_DB_PATH` in this PostgreSQL edition. Remove the old variable if present.

## Supabase database setup
1. Create a Supabase project.
2. Open Project Settings → Database and obtain a PostgreSQL connection string (use the pooler connection for hosted apps if recommended by Supabase).
3. Copy the connection string and replace its password placeholder with your database password.
4. Add it to Render as `DATABASE_URL`. Treat this string as a secret; do not commit it to GitHub.
5. Redeploy the Render service.
6. In app tabs, add a product, create a test bill, then check saved stock and bill.

Supabase free-tier projects can pause after inactivity. Review current provider limits and arrange exports/backups.

## Important
Use a private GitHub repository. Never upload customer data, database credentials, or exported bills to public repositories.
