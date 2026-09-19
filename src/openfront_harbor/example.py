"""Worked example wiring for the harbor gates: the plains-smoke task.

Every domain-specific value lives here and only here. The process
modules (``runner``, ``reconcile``, ``config``, ``proxy``, ``evidence``,
``execution``) take these as explicit inputs and name no task, port,
host, or package version of their own.
"""

from __future__ import annotations

EXPECTED_HARBOR_VERSION = "0.21.0"

REQUIRED_FILES: tuple[str, ...] = (
    "config/pinned-images-amd64-native.toml",
    "jobs/tests/live-smoke-openfront-k1.yaml",
    "tasks/plains-smoke/task.toml",
    "tasks/plains-smoke/environment/Dockerfile",
    "tasks/plains-smoke/instruction.md",
    "tasks/plains-smoke/tests/test.sh",
)

SMOKE_JOB = "jobs/tests/live-smoke-openfront-k1.yaml"

BASE_PORT = 8801

PROXY_URL_TEMPLATE = "http://host.docker.internal:{port}/v1"
