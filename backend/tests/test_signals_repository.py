import uuid

from backend.app.signals.repository import new_audit
from backend.app.models import SignalAuditEvent

def test_new_audit_creates_event_with_uuid():
    audit = new_audit(
        actor_kind="user",
        actor_subject="usr_123",
        route_id="rt_456",
        event_id="evt_789",
        request_id="req_000",
        transition="started",
    )

    assert isinstance(audit, SignalAuditEvent)
    assert audit.id is not None
    # Verify id is a valid UUID
    assert uuid.UUID(audit.id)

    assert audit.actor_kind == "user"
    assert audit.actor_subject == "usr_123"
    assert audit.route_id == "rt_456"
    assert audit.event_id == "evt_789"
    assert audit.request_id == "req_000"
    assert audit.transition == "started"

    # Defaults
    assert audit.reason_code is None
    assert audit.route_version is None
    assert audit.policy_version is None
    assert audit.details is None

def test_new_audit_optional_params():
    details = {"key": "value"}
    audit = new_audit(
        actor_kind="system",
        actor_subject=None,
        route_id=None,
        event_id=None,
        request_id=None,
        transition="completed",
        reason_code="success",
        route_version=2,
        policy_version="v1.0",
        details=details
    )

    assert audit.actor_kind == "system"
    assert audit.actor_subject is None
    assert audit.route_id is None
    assert audit.event_id is None
    assert audit.request_id is None
    assert audit.transition == "completed"

    assert audit.reason_code == "success"
    assert audit.route_version == 2
    assert audit.policy_version == "v1.0"
    assert audit.details == details
