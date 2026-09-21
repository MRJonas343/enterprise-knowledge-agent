"""Test-session setup shared by every test module.

telemetry isolation: api.py calls load_dotenv(ROOT / ".env") at import, and a
developer's real .env carries a live Application Insights connection string set
by the tracing work. Without this switch, importing api would run
_configure_telemetry and build real Azure Monitor exporters, so the suite would
attempt to export telemetry while it runs. OTEL_SDK_DISABLED is the OpenTelemetry
standard kill switch and _configure_telemetry returns early on it.

pytest imports conftest.py before collecting and importing test modules, so
setting the variable at module import is enough: it is in the environment before
any test module reaches `from enterprise_knowledge_agent import api`.
"""

import os

os.environ["OTEL_SDK_DISABLED"] = "true"
