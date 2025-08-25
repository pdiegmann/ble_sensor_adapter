"""Mock data entry flow for testing."""

class FlowResult:
    """Mock flow result."""
    
    def __init__(self, flow_type, **kwargs):
        self.type = flow_type
        self.__dict__.update(kwargs)

class AbortFlow(Exception):
    """Exception to abort flow."""
    
    def __init__(self, reason="aborted"):
        self.reason = reason
        super().__init__(reason)

RESULT_TYPE_FORM = "form"
RESULT_TYPE_CREATE_ENTRY = "create_entry"
RESULT_TYPE_ABORT = "abort"