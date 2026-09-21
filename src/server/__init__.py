"""Secure, simulation-only TradingView webhook receiver.

This package intentionally has no broker adapter.  Accepted orders are persisted as
paper orders only; adding a live execution path requires a separate application.
"""

from .app import create_app

__all__ = ["create_app"]
