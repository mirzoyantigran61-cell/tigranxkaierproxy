from tools.registry import ToolRegistry


class _FakeFirebase:
    def log_action(self, *args, **kwargs): return True
    def is_connected(self): return True
    def get_payment(self, oid): return None


class _FakeSessions:
    def count(self): return 0


def test_tool_registry_admin_only():
    reg = ToolRegistry(_FakeFirebase(), _FakeSessions())
    user_defs = reg.get_definitions("user")
    admin_defs = reg.get_definitions("admin")
    assert len(user_defs) < len(admin_defs)
    user_names = {d["name"] for d in user_defs}
    assert "get_active_sessions" not in user_names


def test_tool_execute_permission_denied():
    reg = ToolRegistry(_FakeFirebase(), _FakeSessions())
    result = reg.execute("get_active_sessions", {}, {"role": "user", "login": "u"})
    assert result["status"] == "error"


def test_tool_execute_admin_ok():
    reg = ToolRegistry(_FakeFirebase(), _FakeSessions())
    result = reg.execute("get_active_sessions", {}, {"role": "admin", "login": "a"})
    assert result["status"] == "success"


def test_unknown_tool():
    reg = ToolRegistry(_FakeFirebase(), _FakeSessions())
    result = reg.execute("nonexistent", {}, {"role": "admin", "login": "a"})
    assert result["status"] == "error"
