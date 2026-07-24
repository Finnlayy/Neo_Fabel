import uuid
from datetime import datetime
from backend.app.academy.schemas import ScoutIdentity

def test_scout_identity_default_factories():
    scout1 = ScoutIdentity(name="Scout One", archetype="Analyst")
    scout2 = ScoutIdentity(name="Scout Two", archetype="Trader")

    # Check scout_id
    assert isinstance(scout1.scout_id, str)
    assert isinstance(scout2.scout_id, str)
    assert scout1.scout_id != scout2.scout_id

    # Verify valid UUID string
    try:
        uuid.UUID(scout1.scout_id)
        uuid.UUID(scout2.scout_id)
    except ValueError:
        assert False, "scout_id is not a valid UUID string"

    # Check created_at
    assert isinstance(scout1.created_at, str)
    assert isinstance(scout2.created_at, str)

    # Verify valid ISO format string
    try:
        dt1 = datetime.fromisoformat(scout1.created_at)
        dt2 = datetime.fromisoformat(scout2.created_at)
        assert dt1.tzinfo is not None, "created_at should be timezone aware"
        assert dt2.tzinfo is not None, "created_at should be timezone aware"
    except ValueError:
        assert False, "created_at is not a valid ISO datetime string"
