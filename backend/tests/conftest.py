"""Pytest configuration and test isolation fixtures."""

import pytest
from app.core.rate_limiter import reset_rate_limiters


@pytest.fixture(autouse=True)
def reset_rate_limiters_fixture():
    """Reset rate limiter state before and after each test to ensure test isolation."""
    reset_rate_limiters()
    yield
    reset_rate_limiters()
