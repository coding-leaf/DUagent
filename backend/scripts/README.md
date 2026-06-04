# Scripts

## seed_e2e_data.py

Creates repeatable test data for Playwright E2E tests.

### Usage

```bash
# 1. Create test database (once)
mysql -u root -p123456 -e "CREATE DATABASE IF NOT EXISTS duagent_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. Run seeder (idempotent, safe to re-run)
ALLOW_E2E_SEED=true DATABASE_URL='mysql+aiomysql://root:123456@localhost:3306/duagent_test?charset=utf8mb4' python scripts/seed_e2e_data.py

# 3. Start backend with same test DB
DATABASE_URL='mysql+aiomysql://root:123456@localhost:3306/duagent_test?charset=utf8mb4' python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# 4. Run E2E tests
cd ../frontend && npm run test:e2e
```

### Safety

- Requires `ALLOW_E2E_SEED=true`
- Database name must contain "test"
- Idempotent: safe to re-run

### Accounts Created

| Email | Password | Role |
|-------|----------|------|
| s@t.com | Abc12345 | student |
| t@t.com | Abc12345 | teacher |
