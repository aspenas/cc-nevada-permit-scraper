# Clark County Permit Scraper

## Secure Credential Loading

This project uses **AWS Secrets Manager** for all sensitive credentials (such as database URLs and API keys). You do **not** need to store secrets in your `.env` file. The application will automatically fetch credentials from AWS at runtime if they are not present in the environment.

### How it works
- On startup, the config loader checks for `DATABASE_URL` in the environment or `.env` file.
- If not found, it fetches the secret from AWS Secrets Manager (using the secret name in `DB_SECRET_NAME`, default: `clark-county-permit-db`).
- The secret is expected to be a JSON object with keys like `DATABASE_URL`.
- AWS credentials are loaded from your AWS CLI profile or environment variables.

### Required Environment Variables
- `AWS_REGION` (default: `us-west-2`)
- `DB_SECRET_NAME` (default: `clark-county-permit-db`)
- (Optional) `DATABASE_URL` (overrides AWS secret if set)

### Example AWS Secret (JSON)
```json
{
  "DATABASE_URL": "postgresql://user:password@host:5432/dbname"
}
```

### Local Development
1. Configure your AWS CLI (`aws configure`) or set AWS credentials in your environment.
2. (Optional) Create a `.env` file to override any variables for local testing.
3. Run your scripts as normal. Credentials will be loaded securely.

---

## Docker & CI/CD Readiness

- The project is ready for containerization. Add a `Dockerfile` and use environment variables for secrets.
- In CI/CD, set AWS credentials as environment variables or use an IAM role.
- No secrets should be hardcoded or checked into version control.

---

## Test Scaffolding

- The codebase is structured for easy unit and integration testing.
- You can mock AWS Secrets Manager and the database for tests.
- Add your tests in a `tests/` directory and use `pytest` or your preferred framework.

---

## Example Usage

```python
from scraper.database.manager import DatabaseManager

db_manager = DatabaseManager()  # Uses AWS Secrets Manager for credentials
```

---

## Questions?
Open an issue or check the code comments for more details.

## Code Quality & Pre-commit Hooks

This project enforces code style, linting, and type checking using [pre-commit](https://pre-commit.com/) with Black, Ruff, and Mypy. All code must pass these checks before being committed.

### Setup
1. Install pre-commit if you haven't already:
   ```sh
   pip install pre-commit
   ```
2. Install the hooks:
   ```sh
   pre-commit install
   ```
3. (Optional) Run all hooks on all files:
   ```sh
   pre-commit run --all-files
   ``` 