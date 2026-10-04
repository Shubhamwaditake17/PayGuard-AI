import pytest
from payguard.tools import TransactionTool, UnsafeSQL, validate_select


@pytest.mark.parametrize("bad", ["DROP TABLE transactions", "SELECT * FROM users",
                                 "SELECT 1; DELETE FROM transactions", "SELECT * FROM transactions -- x",
                                 "UPDATE transactions SET amount=0"])
def test_unsafe_sql_rejected(bad):
    with pytest.raises(UnsafeSQL):
        validate_select(bad)


def test_limit_added():
    assert "LIMIT 50" in validate_select("SELECT * FROM transactions")


def test_row_level_security(agent):
    t = TransactionTool()
    rows = t.run("C001", "SELECT DISTINCT customer_id FROM transactions")
    assert rows == [{"customer_id": "C001"}]
