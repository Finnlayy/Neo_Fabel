"""Advisory-only trading orchestrator.

This package deliberately has no imports from order, broker, or execution modules.
"""

from .service import AdvisoryOrchestrator

__all__ = ["AdvisoryOrchestrator"]
