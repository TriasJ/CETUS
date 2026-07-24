"""Admin recovery: admin-key gating, password reset, clinician listing."""

from cravingcrave.data.database import Database
from cravingcrave.data.repositories import Repositories
from cravingcrave.services import auth
from cravingcrave.services.auth import AuthService


def _repos():
    return Repositories(Database(":memory:"))


def test_admin_key_default_then_custom():
    r = _repos()
    assert auth.admin_key_is_default(r.settings)
    assert auth.verify_admin_key(r.settings, "cetus-admin")
    assert not auth.verify_admin_key(r.settings, "wrong-key")

    auth.set_admin_key(r.settings, "clinic-secret")
    assert not auth.admin_key_is_default(r.settings)
    assert auth.verify_admin_key(r.settings, "clinic-secret")
    # default no longer works once a custom key is set
    assert not auth.verify_admin_key(r.settings, "cetus-admin")


def test_reset_password_and_list():
    r = _repos()
    svc = AuthService(r.clinicians)
    c = svc.register("AlanH", "Dr. Alan Hinojosa", "oldpass")
    assert svc.login("AlanH", "oldpass") is not None

    svc.reset_password(c.id, "newpass")
    assert svc.login("AlanH", "oldpass") is None       # old password invalid
    assert svc.login("AlanH", "newpass").id == c.id      # new password works
    assert [x.username for x in svc.list_clinicians()] == ["AlanH"]
