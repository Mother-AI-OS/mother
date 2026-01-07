"""German legal and business plugins for Mother AI OS.

These plugins provide Germany-specific functionality:
- taxlord: Tax and document management, ELSTER integration
- leads: Lead generation from German tenders and Upwork

Note: These plugins require additional configuration and may have
external dependencies. They gracefully degrade if not configured.
"""

from .leads import LeadsPlugin
from .taxlord import TaxlordPlugin

__all__ = ["TaxlordPlugin", "LeadsPlugin"]
