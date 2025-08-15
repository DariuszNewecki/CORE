# FastAPI Hello World

A simple FastAPI web server that returns hello world.

## Installation

1. Install Poetry (if not already installed):
   ```bash
   pip install poetry
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

## Running the Server

```bash
poetry run uvicorn src.main:app --reload
```

Open your browser to [http://localhost:8000](http://localhost:8000) to see the response.
