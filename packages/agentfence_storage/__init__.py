"""AgentFence storage — local SQLite persistence for scan history.

Local-only by design. The database lives under .agentfence/ and is never
uploaded. Only redacted evidence is ever persisted.
"""

from __future__ import annotations
