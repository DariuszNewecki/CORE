# src/main.py
"""Provides functionality for the main module."""

from __future__ import annotations

from fastapi import FastAPI


app = FastAPI()


@app.get("/healthz")
# ID: 89de6b05-7f14-4a8d-b938-b5abf9385cdb
async def health_check():
    return {"status": "ok"}
