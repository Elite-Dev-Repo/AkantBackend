# Bills — Expense Sharing API

A production-ready backend API for splitting bills, tracking debts, and paying with Paystack.

---

## Tech Stack

| Layer            | Technology                          |
| ---------------- | ----------------------------------- |
| Framework        | Django 4.2 + Django REST Framework  |
| Auth             | SimpleJWT (access + refresh tokens) |
| Database         | PostgreSQL 15                       |
| Task Queue       | Celery + Redis                      |
| Payments         | Paystack                            |
| Docs             | drf-spectacular (Swagger + ReDoc)   |
| Tests            | pytest + factory_boy                |
| Containerisation | Docker + Docker Compose             |

---

## Project Structure

```
bills/
├── apps/
│   ├── users/          # Custom user model, auth, profile
│   ├── groups/         # Groups, memberships, invites
│   ├── expenses/       # Expenses, splits, debts, balance engine
│   ├── payments/       # Paystack integration, webhook handler
│   ├── reports/        # Monthly expense reports
│   └── reminders/      # Email reminders, Celery tasks
├── config/
│   ├── settings.py     # All settings (env-driven)
│   ├── urls.py         # Root URL config
│   ├── celery.py       # Celery app
│   ├── pagination.py   # Standard pagination
│   └── exceptions.py   # Custom error handler
├── tests/
│   ├── conftest.py     # Shared fixtures
│   ├── factories.py    # factory_boy factories
│   ├── test_users.py
│   ├── test_groups.py
│   ├── test_expenses.py
│   ├── test_payments.py
│   └── test_reports_reminders.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── manage.py
└── .env.example
```

---

## Quick Start (Docker)

### 1. Clone and configure environment

```bash
git clone https://github.com/yourname/bills.git
cd bills
cp .env.example .env
```

Edit `.env` with your secrets:

```env
SECRET_KEY=your-super-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=bills_db
DB_USER=bills_user
DB_PASSWORD=bills_password
DB_HOST=db
DB_PORT=5432

PAYSTACK_SECRET_KEY=sk_test_xxxxxxxxxxxx
PAYSTACK_PUBLIC_KEY=pk_test_xxxxxxxxxxxx

FRONTEND_URL=https://akant.vercel.app
```

### 2. Build and start all services

```bash
docker compose up --build -d
```

This starts:

- `db` — PostgreSQL on port 5432
- `redis` — Redis on port 6379
- `api` — Django API on port 8000 (runs migrations automatically)
- `celery_worker` — Async task worker
- `celery_beat` — Periodic task scheduler

### 3. Create a superuser

```bash
docker compose exec api python manage.py createsuperuser
```

### 4. Access the API

| URL                                | Description  |
| ---------------------------------- | ------------ |
| `http://localhost:8000/api/docs/`  | Swagger UI   |
| `http://localhost:8000/api/redoc/` | ReDoc        |
| `http://localhost:8000/admin/`     | Django admin |

---

## Local Development (without Docker)

### 1. Create virtualenv

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Set up PostgreSQL locally

```bash
createdb bills_db
createuser bills_user
psql -c "ALTER USER bills_user WITH PASSWORD 'bills_password';"
psql -c "GRANT ALL PRIVILEGES ON DATABASE bills_db TO bills_user;"
```

### 3. Configure `.env`

```bash
cp .env.example .env
# Set DB_HOST=localhost
```

### 4. Run migrations and start server

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 5. Start Celery (separate terminal)

```bash
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info   # in another terminal
```

---

## Running Tests

```bash
# All tests with coverage
pytest

# Specific test file
pytest tests/test_expenses.py

# Specific test class
pytest tests/test_expenses.py::TestBalanceService

# Single test
pytest tests/test_groups.py::TestGroupService::test_accept_invite_creates_membership

# With verbose output
pytest -v

# Coverage report only
pytest --cov=apps --cov-report=html
open htmlcov/index.html
```

---

## API Reference

### Authentication

All endpoints require `Authorization: Bearer <access_token>` except:

- `POST /api/v1/auth/register/`
- `POST /api/v1/auth/login/`
- `POST /api/v1/payments/webhook/paystack/` (Paystack signature verified instead)

### Auth Endpoints

```
POST   /api/v1/auth/register/          Register new user
POST   /api/v1/auth/login/             Login (returns JWT pair)
POST   /api/v1/auth/token/refresh/     Refresh access token
POST   /api/v1/auth/token/verify/      Verify token validity
POST   /api/v1/auth/logout/            Blacklist refresh token
```

### User Endpoints

```
GET    /api/v1/users/me/               Get own profile
PATCH  /api/v1/users/me/               Update own profile
POST   /api/v1/users/change-password/  Change password
GET    /api/v1/users/{id}/             Get user public profile
```

### Group Endpoints

```
GET    /api/v1/groups/                         List my groups
POST   /api/v1/groups/                         Create a group
GET    /api/v1/groups/{id}/                    Get group detail
PATCH  /api/v1/groups/{id}/                    Update group (admin only)
DELETE /api/v1/groups/{id}/                    Deactivate group (admin only)

GET    /api/v1/groups/{id}/members/            List members
DELETE /api/v1/groups/{id}/members/{user_id}/  Remove member / leave group
POST   /api/v1/groups/{id}/members/{user_id}/promote/  Promote to admin

POST   /api/v1/groups/{id}/invites/            Send invite
GET    /api/v1/groups/{id}/invites/list/       List group invites
POST   /api/v1/groups/invites/accept/          Accept invite by token
```

### Expense Endpoints

```
GET    /api/v1/groups/{group_pk}/expenses/             List group expenses
POST   /api/v1/groups/{group_pk}/expenses/             Create expense
GET    /api/v1/groups/{group_pk}/expenses/{id}/        Get expense
DELETE /api/v1/groups/{group_pk}/expenses/{id}/        Delete expense
POST   /api/v1/groups/{group_pk}/expenses/{id}/splits/{split_id}/pay/  Mark split paid

GET    /api/v1/groups/{group_pk}/debts/                List group debts
GET    /api/v1/groups/{group_pk}/debts/{id}/           Get debt detail
POST   /api/v1/groups/{group_pk}/debts/{id}/settle/    Settle debt manually
GET    /api/v1/groups/{group_pk}/debts/my-balance/     My balance summary
```

### Payment Endpoints

```
GET    /api/v1/payments/               List my payments
POST   /api/v1/payments/initiate/      Initiate Paystack payment for a debt
POST   /api/v1/payments/verify/        Verify payment by reference
POST   /api/v1/payments/webhook/paystack/  Paystack webhook (no auth)
```

### Report Endpoints

```
GET    /api/v1/reports/                List my reports
GET    /api/v1/reports/{id}/           Get report detail
POST   /api/v1/reports/generate/       Generate / refresh monthly report
```

### Reminder Endpoints

```
GET    /api/v1/reminders/              List reminders sent to me
POST   /api/v1/reminders/send/         Send reminder to debtor (creditor only)
```

---

## Creating an Expense — Example

### Equal split (3 members, ₦300)

```bash
POST /api/v1/groups/{group_id}/expenses/
Authorization: Bearer <token>

{
  "title": "Team lunch",
  "amount": "300.00",
  "currency": "NGN",
  "category": "food",
  "split_type": "equal",
  "paid_by_id": "<your-user-uuid>",
  "date": "2024-03-15"
}
```

The signal automatically creates 3 splits of ₦100 each. Debts are recalculated immediately.

### Exact split

```json
{
  "title": "Hotel",
  "amount": "500.00",
  "split_type": "exact",
  "paid_by_id": "...",
  "date": "2024-03-16",
  "split_data": [
    { "user_id": "uuid1", "amount": "200.00" },
    { "user_id": "uuid2", "amount": "150.00" },
    { "user_id": "uuid3", "amount": "150.00" }
  ]
}
```

### Percentage split

```json
{
  "title": "Airbnb",
  "amount": "600.00",
  "split_type": "percentage",
  "paid_by_id": "...",
  "date": "2024-03-17",
  "split_data": [
    { "user_id": "uuid1", "percentage": "50" },
    { "user_id": "uuid2", "percentage": "30" },
    { "user_id": "uuid3", "percentage": "20" }
  ]
}
```

---

## Paystack Payment Flow

```
1. POST /api/v1/payments/initiate/  { "debt_id": "..." }
   → Returns authorization_url

2. Redirect user to authorization_url (Paystack checkout)

3a. User completes payment → Paystack fires webhook to:
       POST /api/v1/payments/webhook/paystack/
    → Debt is auto-settled

3b. (Alternatively) Frontend polls:
       POST /api/v1/payments/verify/  { "reference": "bills_xxx" }
    → Debt is settled on success
```

---

## Celery Periodic Tasks

Configure in Django admin under **Periodic Tasks** (django-celery-beat):

| Task                                            | Recommended Schedule    | Description                               |
| ----------------------------------------------- | ----------------------- | ----------------------------------------- |
| `apps.reminders.tasks.send_debt_reminders`      | Daily at 09:00 UTC      | Email all debtors with unpaid debts       |
| `apps.reminders.tasks.generate_monthly_reports` | 1st of month, 01:00 UTC | Pre-compute monthly reports for all users |

---

## Balance Calculation Algorithm

The debt simplification uses a **greedy min-cash-flow** approach:

1. For each expense, the payer is owed their share back by each split member.
2. Net balances are accumulated: `+` means owed money, `-` means owes money.
3. The debt graph is simplified: if A→B 100 and B→C 100, this becomes A→C 100 (one transaction instead of two).
4. Results are persisted to the `Debt` table and recalculated whenever expenses change.

---

## Permissions Summary

| Action                | Required                                  |
| --------------------- | ----------------------------------------- |
| Read/write group data | Active group member                       |
| Update/delete group   | Group admin                               |
| Remove another member | Group admin                               |
| Create/delete expense | Group member (creator or admin to delete) |
| Mark split paid       | Payer (creditor) or the split's user      |
| Settle debt           | Either party (debtor or creditor)         |
| Initiate payment      | Debtor only                               |
| Send reminder         | Creditor only                             |

---

## Environment Variables

| Variable                        | Required | Default                    | Description                    |
| ------------------------------- | -------- | -------------------------- | ------------------------------ |
| `SECRET_KEY`                    | ✅       | —                          | Django secret key              |
| `DEBUG`                         |          | `False`                    | Enable debug mode              |
| `ALLOWED_HOSTS`                 | ✅       | `localhost`                | Comma-separated hostnames      |
| `DB_NAME`                       | ✅       | `bills_db`                 | PostgreSQL database name       |
| `DB_USER`                       | ✅       | `bills_user`               | PostgreSQL user                |
| `DB_PASSWORD`                   | ✅       | —                          | PostgreSQL password            |
| `DB_HOST`                       | ✅       | `db`                       | PostgreSQL host                |
| `DB_PORT`                       |          | `5432`                     | PostgreSQL port                |
| `PAYSTACK_SECRET_KEY`           | ✅       | —                          | Paystack secret key            |
| `PAYSTACK_PUBLIC_KEY`           | ✅       | —                          | Paystack public key            |
| `CELERY_BROKER_URL`             | ✅       | `redis://redis:6379/0`     | Redis broker URL               |
| `FRONTEND_URL`                  |          | `https://akant.vercel.app` | Frontend base URL (for emails) |
| `ACCESS_TOKEN_LIFETIME_MINUTES` |          | `60`                       | JWT access token lifetime      |
| `REFRESH_TOKEN_LIFETIME_DAYS`   |          | `7`                        | JWT refresh token lifetime     |

---

## Makefile Shortcuts

```bash
make build          # docker compose up --build -d
make down           # docker compose down
make logs           # docker compose logs -f api
make shell          # docker compose exec api python manage.py shell
make migrate        # docker compose exec api python manage.py migrate
make test           # docker compose exec api pytest
make superuser      # docker compose exec api python manage.py createsuperuser
```

---

## Contributing

1. Fork the repo and create a feature branch: `git checkout -b feat/my-feature`
2. Write tests for new functionality
3. Ensure `pytest` passes with no failures
4. Open a pull request

---

## License

MIT
#   A k a n t B a c k e n d  
 