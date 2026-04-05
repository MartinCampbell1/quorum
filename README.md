# Multi-Agent / Quorum

## Backend Environment

The backend is pinned to Python `3.13`.

Python `3.14` currently triggers a `langchain_core` warning around legacy Pydantic v1 compatibility, so the repository bootstrap and test flow are standardized on `3.13`.

### Bootstrap

```bash
bash ./scripts/bootstrap_backend_env.sh
```

### Test

```bash
bash ./scripts/test_backend.sh

# or a targeted file
bash ./scripts/test_backend.sh tests/test_api_contracts.py -q
```

### Override the Python binary

```bash
QUORUM_PYTHON_BIN=/path/to/python3.13 bash ./scripts/bootstrap_backend_env.sh
```
