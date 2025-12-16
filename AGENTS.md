# Agent notes (repo conventions)

## Running code

- Use the Taskfiles to run scripts whenever possible: `task app:<task-name>`.
- Python virtual environment lives in `.venv`. Tasks activate it automatically; if you run scripts manually, activate it first:
  - `source .venv/bin/activate`

## Environment configuration

- Tasks load `.env` automatically (see `Taskfile.yaml`).
- Do not add inline comments on the same line as variables in `.env`; put comments on their own line above the variable.
- Treat `.env` as sensitive (credentials). Prefer `AWS_PROFILE`/SSO over long-lived static keys.
