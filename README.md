# Taqneeq Backend (FastAPI + PostgreSQL)

This repository hosts the FastAPI backend for the Taqneeq application. The service manages user onboarding, OTP-based auth, credits/transactions, leaderboards, and the admin portal.

The project was migrated from Flask + Firebase to FastAPI + PostgreSQL and now includes a refreshed admin dashboard implementation. The current focus area (owned by **Swaraj**) is the admin metrics and control panel.

---

## 1. Current Status (Swaraj – Admin Panel)

### ✅ Deliverables Completed
- **Metrics API surface**
  - `GET /admin/metrics/total_users`
  - `GET /admin/metrics/daily_signups?days=7`
  - `GET /admin/metrics/points_minted?days=7`
  - `GET /admin/metrics/points_redeemed?days=7`
  - `GET /admin/metrics/top_users?limit=10`
  - `GET /admin/transactions/export.csv`
- **Aggregation logic**
  - User counts, daily signups, minted vs redeemed summaries.
  - Transaction history flattening for CSV export.
  - Respects existing admin-token guard (`ADMIN_PASSWORD`, base64).
- **Dashboard UI**
  - `templates/dashboard.html` rendered at `/admin/dashboard`.
  - Chart.js charts for signups and minted vs redeemed.
  - Time-range selectors, top users table, CSV download button.
  - Auto-prompt for admin password (stored base64, matches backend guard).
- **Documentation**
  - Expanded README (this file) with setup, usage, and testing guidance.

### ⏳ Outstanding Work
- **Testing / QA**
  - Manual smoke test with seeded data.
  - Optional: automated pytest coverage around new aggregation helpers.
- **Data seeding**
  - Needs realistic users/transactions from upstream PRs (Aditya & Anushree) to fully exercise charts and CSV.

> Summary: All feature work is complete. Only validation/testing remains.

---

## 2. Getting Started

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Environment variables supplied via `.env`

### Environment Variables

Create `.env` in the project root with:

```env
# Database
DATABASE_URL=postgresql://username:password@host:port/database

# Admin portal guard (base64-encoded cleartext)
ADMIN_PASSWORD=your_admin_password_base64
ADMIN_PORTAL=/admin

# OTP service (if applicable)
OTP_AUTH_TOKEN=your_otp_auth_token

# Integration testing defaults
TEST_PHONE_NUMBER=7777777777
TEST_OTP=123456

# Uvicorn server port
PORT=8000
```

> The admin dashboard **requires** the header `TOKEN: <base64(admin_password)>`. The frontend prompts for the cleartext password and stores the base64 token in `localStorage`.

### Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Database Bootstrapping

```bash
# Create tables
python init_db.py

# Drop & recreate everything (destructive!)
python init_db.py --drop
```

The models live in `models/` and use SQLAlchemy. Alembic scaffolding (`alembic/`) is included if migration scripts are added later.

### Running the App

```bash
# Development
uvicorn app:app --reload --port 8000

# Production-style
uvicorn app:app --host 0.0.0.0 --port 8000

# Or via Python entrypoint
python app.py
```

Static assets are served from `static/` and Jinja templates come from `templates/`.

---

## 3. Admin Dashboard Smoke Test (Manual QA)

Testing is the only remaining checklist item. Follow this flow to verify the new functionality end-to-end:

1. **Seed data**
   - Ensure Aditya’s user model migration is applied (`init_db.py`).
   - Insert a few users with varying roles and credits.
   - Create transaction history entries (ALLOCATE/REDEEM) to populate charts.
   - You can use existing controllers or run custom SQL inserts.

2. **Run the service**
   ```bash
   uvicorn app:app --reload --port 8000
   ```

3. **Authenticate**
   - Visit `http://localhost:8000/admin/dashboard`.
   - When prompted, enter the cleartext admin password (same value that was base64-encoded in `.env`).

4. **Verify metrics**
   - Totals update to match seeded data.
   - Daily signups chart responds to range selector (7/14/30 days).
   - Minted vs redeemed bar chart switches ranges correctly.
   - Top users table honors the limit dropdown.

5. **CSV export**
   - Click “Download Transactions CSV”.
   - Confirm the CSV contains flattened transactions with `user_id`, `type`, `amount`, `timestamp`, `performed_by`, `balance`.

6. **Token guard**
   - Clear local storage, refresh page, ensure prompt reappears.
   - Try an incorrect password to see the guard returning `401`.

### Optional Automated Tests
- Extend `tests/` with pytest cases for:
  - `get_total_users_count`
  - `get_daily_signups`
  - `get_points_summary`
  - `get_transactions_flat`
- Use factory fixtures to seed temporary data into a transactional test database.

---

## 4. API Overview

The service exposes a wide set of routes; below is a condensed map.

### Authentication
- `POST /phone/auth` – Send verification code
- `POST /phone/verify_code` – Verify OTP
- `POST /phone/add_user` – Finalize user creation
- `POST /user/by_email` – Lookup by email
- `POST /user/by_phone` – Lookup by phone

### Users
- `POST /user/add`
- `PUT /user/update`
- `DELETE /user/delete`
- `GET /user/profile/{unique_id}`

### Credits
- `POST /points/allocate`
- `POST /points/redeem`
- `POST /transactions/history`
- `GET /leaderboard?limit=10`

### Admin (TOKEN header required)
- `GET /admin/users?sort=ascending`
- `PUT /admin/points/update`
- `POST /admin/users/add`
- `DELETE /admin/users/{user_id}`
- `PUT /admin/users/role`
- `GET /admin/metrics/total_users`
- `GET /admin/metrics/daily_signups?days=7`
- `GET /admin/metrics/points_minted?days=7`
- `GET /admin/metrics/points_redeemed?days=7`
- `GET /admin/metrics/top_users?limit=10`
- `GET /admin/transactions/export.csv`

### Data / Misc
- `GET /schedule`
- `GET /items`
- `GET /events`

### Admin Portal (Website)
- `GET {ADMIN_PORTAL}/` – Home (user list)
- `GET {ADMIN_PORTAL}/dashboard` – Metrics dashboard (new)
- `GET {ADMIN_PORTAL}/user/add` – Add user form
- `POST {ADMIN_PORTAL}/user/add` – Submit new user
- `GET {ADMIN_PORTAL}/user/{user_id}` – User details
- `POST {ADMIN_PORTAL}/user/points/update` – Adjust points
- `POST {ADMIN_PORTAL}/user/balance/update` – Adjust balance
- `POST {ADMIN_PORTAL}/user/role/update` – Change role
- `POST {ADMIN_PORTAL}/user/delete` – Delete user
- `GET {ADMIN_PORTAL}/user/{user_id}/transactions` – Transaction history

---

## 5. Database Snapshot

### `users_sql` table (`UserDB`)
- `unique_id` (string) – External identifier (primary business key)
- `first_name`, `last_name`
- `email`, `phone_number`
- `role` – Enum (`USER`, `SALES`, `ADMIN`)
- `credits`, `balance`
- `transaction_history` – JSON array (used by admin metrics)
- `referral_code`, `referred_by[]`, `referrals[]`
- `created_at` – used for daily signup chart

### `credit_transactions` table (`CreditTransaction`)
- Persists atomic allocate/redeem events (used by credits module)
- Currently not required for dashboard but available for future enhancements

### `cache` table (`CacheDB`)
- Used by leaderboard controller for 45-second TTL caching

### `phone_auth` table (`PhoneAuthDB`)
- Tracks OTP attempts and verification status

---

## 6. Next Steps & Recommendations

1. **Complete QA** – Run the smoke test instructions above and document any issues.
2. **Automate Tests (optional)** – Add pytest coverage if time permits.
3. **Performance Review** – For high-traffic scenarios, consider caching minted/redeemed summary results or moving to aggregation queries directly against `credit_transactions`.
4. **Visual Polish** – Iterate on dashboard styling once product requirements are finalized.

Once testing is marked complete, the admin panel PR can be upgraded from Draft to Ready for Review.

---

## 7. Contributors & Ownership

- **Aditya** – Core FastAPI skeleton, DB session, user CRUD.
- **Jash** – Security (hashing/JWT, auth deps).
- **Anushree** – Credits, transactions, leaderboard cache.
- **Swaraj** – Admin metrics API, dashboard UI. ✅ Feature-complete, testing pending.
- **Dayaan** – Vision service (image ingestion/CLIP).

Please coordinate cross-team changes through the shared fork → draft PR workflow (see project guidelines).

---

Happy hacking! Reach out to @swaraj for admin-panel follow-ups or @aditya / @anushree for user/credits data dependencies. Continuous integration should cover `lint`, `typecheck`, and `pytest` once the GitHub Actions pipeline is finalized.
