import pytest
from unittest.mock import MagicMock

from .ligfinderFuncAdvanced import (
    generate_criteria_sql,
    CriteriaLimitExceeded,
    DEFAULT_MAX_VALUE_LENGTH,
    DEFAULT_MAX_LIST_SIZE,
    DEFAULT_MAX_CRITERIA_ITEMS,
)


def make_item(status: str, data) -> MagicMock:
    item = MagicMock()
    item.status = status
    item.data = data
    return item


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 1 — SQL Injection
# Values now travel through named params dict, never into the SQL string.
# All injection payloads below must appear in params only, never in sql.
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLInjection:

    def test_sec_01_single_quote_in_art_value(self):
        """Single quote must land in params, never break the SQL string."""
        payload = "080' OR '1'='1"
        item = make_item("included", {"children": True, "art": [payload]})
        sql, params = generate_criteria_sql([item])
        assert payload not in sql
        assert payload in params.values()

    def test_sec_02_sql_comment_injection_in_art(self):
        """SQL comment -- must land in params, not the SQL string."""
        payload = "080'--"
        item = make_item("included", {"children": True, "art": [payload]})
        sql, params = generate_criteria_sql([item])
        assert payload not in sql
        assert payload in params.values()

    def test_sec_03_union_attack_in_nutzung_value(self):
        """UNION SELECT payload must land in params, not the SQL string."""
        payload = "x' UNION SELECT table_name FROM information_schema.tables--"
        item = make_item("included", {"nutzungvalue": [payload]})
        sql, params = generate_criteria_sql([item])
        assert "UNION SELECT" not in sql
        assert payload in params.values()

    def test_sec_04_semicolon_statement_termination_in_typ(self):
        """DROP TABLE payload must land in params, not the SQL string."""
        payload = "3020'; DROP TABLE parcels;--"
        item = make_item("included", {"typ": [payload]})
        sql, params = generate_criteria_sql([item])
        assert "DROP TABLE" not in sql
        assert payload in params.values()

    def test_sec_05_backslash_escape_attempt(self):
        """Backslash value is handled safely — no crash, no SQL breakage."""
        item = make_item("included", {"children": True, "art": ["080\\"]})
        sql, params = generate_criteria_sql([item])
        assert isinstance(sql, str)
        assert "080\\" in params.values()

    def test_sec_06_null_byte_injection(self):
        """Null bytes are stripped by _sanitise_list before reaching SQL or params."""
        item = make_item("included", {"children": True, "art": ["080\x00 OR 1=1"]})
        sql, params = generate_criteria_sql([item])
        assert "\x00" not in sql
        # Null byte stripped — cleaned value "080 OR 1=1" lands in params (not the SQL)
        assert "080 OR 1=1" in params.values()

    def test_sec_07_injection_via_excluded_item(self):
        """Injection via an excluded item must land in params, not the SQL string."""
        payload = "x' OR '1'='1"
        item = make_item("excluded", {"nutzungvalue": [payload]})
        sql, params = generate_criteria_sql([item])
        assert "OR '1'='1" not in sql
        assert payload in params.values()

    def test_sec_14_mixed_valid_and_injection_values(self):
        """Mixed clean + injection values: injection payload in params only, not SQL."""
        item = make_item("included", {"children": True, "art": ["080", "081' OR '1'='1"]})
        sql, params = generate_criteria_sql([item])
        assert "OR '1'='1" not in sql
        assert "080" in params.values()
        assert "081' OR '1'='1" in params.values()


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 2 — Denial of Service
# ══════════════════════════════════════════════════════════════════════════════

class TestDenialOfService:

    def test_sec_08_extremely_long_single_value_is_blocked(self):
        """Values over DEFAULT_MAX_VALUE_LENGTH raise CriteriaLimitExceeded — never silently dropped."""
        long_value = "A" * 100_000
        item = make_item("included", {"children": True, "art": [long_value]})
        with pytest.raises(CriteriaLimitExceeded):
            generate_criteria_sql([item])

    def test_sec_09_large_list_raises_criteria_limit_exceeded(self):
        """10,000 values in one list raises CriteriaLimitExceeded — never silently truncated."""
        large_list = [str(i).zfill(5) for i in range(10_000)]
        item = make_item("included", {"children": True, "art": large_list})
        with pytest.raises(CriteriaLimitExceeded):
            generate_criteria_sql([item])

    def test_sec_10_large_number_of_criteria_items_raises_error(self):
        """More than DEFAULT_MAX_CRITERIA_ITEMS criteria items raises CriteriaLimitExceeded."""
        items = [
            make_item("included", {"children": True, "art": [str(i).zfill(3)]})
            for i in range(DEFAULT_MAX_CRITERIA_ITEMS + 1)
        ]
        with pytest.raises(CriteriaLimitExceeded, match="Too many criteria items"):
            generate_criteria_sql(items)


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 3 — Semantically Invalid Values
# ══════════════════════════════════════════════════════════════════════════════

class TestSemanticallySuspiciousValues:

    def test_sec_11_whitespace_only_value_is_rejected(self):
        """Whitespace-only value is stripped to empty string and dropped."""
        item = make_item("included", {"children": True, "art": ["   "]})
        sql, params = generate_criteria_sql([item])
        assert sql == "", f"Expected empty result for whitespace-only value, got: '{sql}'"

    def test_sec_12_empty_string_value_is_rejected(self):
        """Empty string value is dropped by _sanitise_list."""
        item = make_item("included", {"children": True, "art": [""]})
        sql, params = generate_criteria_sql([item])
        assert sql == "", f"Expected empty result for empty string value, got: '{sql}'"

    def test_sec_13_integer_value_is_converted_to_string(self):
        """Integer value is converted to string and lands in params."""
        item = make_item("included", {"children": True, "art": [80]})
        sql, params = generate_criteria_sql([item])
        assert "80" in params.values(), (
            f"Expected integer 80 to be converted to '80' in params, got: {params}"
        )

    def test_sec_15_none_value_in_list_is_dropped(self):
        """None values in a list are skipped — no crash, no empty placeholder."""
        item = make_item("included", {"children": True, "art": [None, "080"]})
        sql, params = generate_criteria_sql([item])
        assert "080" in params.values()
        assert len(params) == 1   # None was dropped, only one value registered

    def test_sec_16_non_dict_data_is_skipped(self):
        """Items whose data is not a dict are skipped without crashing."""
        item = make_item("included", "not a dict")
        sql, params = generate_criteria_sql([item])
        assert sql == ""
        assert params == {}
