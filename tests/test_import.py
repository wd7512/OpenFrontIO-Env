from __future__ import annotations

import logging

import pytest

from python_template.__main__ import main


def test_main_callable() -> None:
    assert callable(main)


def test_main_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="python_template.__main__"):
        main()
    assert any(
        record.message == "Hello from python-template!" and record.levelname == "INFO"
        for record in caplog.records
    )
