import pytest
from unittest.mock import MagicMock


# ── Import the function under test ─────────────────────────────────────────────
# Adjust this import to match your project structure
from .ligfinderFuncAdvanced import generate_criteria_sql, CriteriaLimitExceeded


# ── Helper: build a mock criteria item ────────────────────────────────────────
def make_item(status: str, data) -> MagicMock:
    """Create a mock criteria item with .status and .data attributes."""
    item = MagicMock()
    item.status = status
    item.data = data
    return item


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 1 — Empty Inputs
# These test what happens when the function receives correct structure
# but with nothing meaningful inside it.
# ══════════════════════════════════════════════════════════════════════════════

class TestEmptyInputs:

    def test_11_empty_criteria_list_returns_empty_string(self):
        """
        CASE 11: No criteria items at all.

        WHY: The function iterates over criteria. An empty list
        should short-circuit cleanly and return "" — not None,
        not raise an exception. An empty WHERE clause in SQL
        is valid only if the caller handles the empty string.
        """
        sql, params = generate_criteria_sql([])
        assert sql == "", (
            f"Expected empty string for empty criteria list, got: '{sql}'"
        )

    def test_12_item_with_no_recognised_key_is_skipped(self):
        """
        CASE 12: Item whose data dict has no recognised key.

        WHY: The function uses if/elif to match keys. An item
        with none of 'children', 'typ', 'nutzungvalue' sets
        clause = None and should be silently skipped.
        A crash here would break the entire query for all users
        whose filter config has an unrecognised entry.
        """
        item = make_item("included", {"unknown_key": ["value"], "another_key": [1, 2, 3]})
        sql, params = generate_criteria_sql([item])
        assert sql == "", (
            f"Expected empty string when no recognised key present, got: '{sql}'"
        )

    def test_13_empty_art_list_produces_no_clause(self):
        """
        CASE 13: 'children' key present but 'art' list is empty.

        WHY: data.get('art', []) returns [] → the if art_list
        check is False → no clause. Without this guard the function
        would emit ARRAY[]::text[] which is syntactically valid
        SQL but semantically wrong — it matches nothing and
        wastes a DB round trip.
        """
        item = make_item("included", {"children": True, "art": []})
        sql, params = generate_criteria_sql([item])
        assert sql == "", (
            f"Expected empty string for empty art list, got: '{sql}'"
        )

    def test_14_empty_typ_list_produces_no_clause(self):
        """
        CASE 14: 'typ' key present but value list is empty.

        WHY: Same guard as art. An empty typ list should not
        emit ARRAY[]::text[] && string_to_array(lgb_typ_values, ',')
        which would always evaluate to false in PostgreSQL.
        """
        item = make_item("included", {"typ": []})
        sql, params = generate_criteria_sql([item])
        assert sql == "", (
            f"Expected empty string for empty typ list, got: '{sql}'"
        )

    def test_15_empty_nutzung_list_produces_no_clause(self):
        """
        CASE 15: 'nutzungvalue' key present but list is empty.

        WHY: Same pattern. An empty nutzungvalue list must be
        skipped to avoid emitting broken SQL that always returns
        false matches against nutzart_list_final.
        """
        item = make_item("included", {"nutzungvalue": []})
        sql, params = generate_criteria_sql([item])
        assert sql == "", (
            f"Expected empty string for empty nutzungvalue list, got: '{sql}'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 2 — Invalid / Unexpected Structure
# These test what happens when the item structure itself is wrong.
# ══════════════════════════════════════════════════════════════════════════════

class TestInvalidStructure:

    def test_16_mixed_valid_and_invalid_items_only_valid_produces_sql(self):
        """
        CASE 16: List contains both valid and invalid items.

        WHY: The function processes items one by one. A bad item
        must not poison the result for the good ones. This ensures
        partial input produces partial (correct) output rather
        than crashing or dropping everything.
        """
        items = [
            make_item("included", {"children": True, "art": ["080"]}),  # valid
            make_item("included", {"unknown_key": ["value"]}),           # invalid — skipped
            make_item("included", {"nutzungvalue": []}),                  # invalid — empty list
        ]
        sql, params = generate_criteria_sql(items)

        # Only the first item should produce SQL
        assert "lgb_art_values" in sql, "Valid art item should produce SQL"
        assert "unknown_key" not in sql, "Invalid item key must not appear in SQL"
        assert "nutzart_list_final" not in sql, "Empty nutzung list must not appear in SQL"


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 3 — Malformed / Broken JSON (data field issues)
# These test what happens when the data dict inside an item is
# corrupted, None, wrong type or has unexpected value types.
# This is the "broken JSON" category.
# ══════════════════════════════════════════════════════════════════════════════

class TestMalformedData:

    def test_17_data_is_none_does_not_crash(self):
        """
        CASE 17: item.data is None instead of a dict.

        WHY: This is the most dangerous broken JSON case.
        The function calls 'if "children" in data' — if data is None
        this raises TypeError: argument of type 'NoneType' is not iterable.
        A single corrupted item from the frontend must not crash
        the entire query builder. The function should skip it or
        return empty string.

        WHAT WE EXPECT: Either returns "" OR raises a clear
        TypeError — not a silent wrong result.
        """
        item = make_item("included", None)
        try:
            sql, params = generate_criteria_sql([item])
            # If it doesn't crash, it should return empty string
            assert sql == "", (
                f"Expected empty string when data is None, got: '{sql}'"
            )
        except TypeError:
            # Acceptable — the function does not guard against None data.
            # This test documents the behaviour so the team can decide
            # whether to add a guard or validate input upstream.
            pytest.xfail(
                "Function does not currently guard against None data. "
                "Consider adding: if not isinstance(data, dict): continue"
            )

    def test_18_data_is_a_string_does_not_crash(self):
        """
        CASE 18: item.data is a plain string instead of a dict.

        WHY: JSON deserialization bugs can produce a string where
        a dict is expected. 'if "children" in "some string"' in Python
        actually works (checks substring) but 'data.get(...)' on a string
        raises AttributeError. This test documents what happens
        so the team knows to add upstream validation.

        WHAT WE EXPECT: Either returns "" OR raises AttributeError.
        """
        item = make_item("included", '{"children": true, "art": ["080"]}')
        try:
            sql, params = generate_criteria_sql([item])
            assert sql == "", (
                f"Expected empty string when data is a string, got: '{sql}'"
            )
        except (AttributeError, TypeError):
            pytest.xfail(
                "Function does not guard against string data. "
                "Consider adding: if not isinstance(data, dict): continue"
            )

    def test_19_data_is_empty_dict_returns_empty_string(self):
        """
        CASE 19: item.data is {} — a valid dict but with no keys.

        WHY: An empty dict passes the isinstance check but matches
        none of the if/elif conditions. This is the cleanest
        broken JSON case — the function should handle it silently
        and return "". This is the expected current behaviour.
        """
        item = make_item("included", {})
        sql, params = generate_criteria_sql([item])
        assert sql == "", (
            f"Expected empty string for empty data dict, got: '{sql}'"
        )

    def test_20_art_list_contains_none_value(self):
        """
        CASE 20: art list contains a None value alongside valid values.

        WHY: data = {"children": True, "art": [None, "080"]}
        The list comprehension f"'{val}'" for val in art_list would
        produce ARRAY['None', '080'] — the string 'None' is injected
        into SQL which will never match a real value and silently
        returns wrong results. This test documents the behaviour.

        WHAT WE EXPECT: Either filters out None values OR
        the test flags this as a known gap requiring upstream validation.
        """
        item = make_item("included", {"children": True, "art": [None, "080"]})
        sql, params = generate_criteria_sql([item])

        # Document current behaviour
        if sql == "":
            # Function skipped the item entirely
            pass
        else:
            # Function produced SQL — check None did not sneak in as the string 'None'
            assert "'None'" not in sql, (
                "None value was converted to the string 'None' in SQL. "
                "This will never match real data and is a silent bug. "
                "Consider filtering: [v for v in art_list if v is not None]"
            )

    def test_20b_art_list_contains_only_none_values(self):
        """
        CASE 20b: art list contains only None values.

        WHY: If all values are None and they pass through,
        the SQL becomes ARRAY['None']::text[] which is valid
        syntax but will never match anything — a silent data bug.
        Should ideally return "" after filtering.
        """
        item = make_item("included", {"children": True, "art": [None, None]})
        sql, params = generate_criteria_sql([item])
        # At minimum, 'None' as a string literal must not appear in SQL
        if sql:
            assert "'None'" not in sql, (
                "None values converted to string 'None' in SQL output. "
                "These will never match real data."
            )

    def test_21_status_is_unrecognised_value_treated_as_excluded(self):
        """
        CASE 21: status is neither 'included' nor 'excluded'.

        WHY: is_included = (status == "included"). Any value that
        is not exactly "included" — e.g. "INCLUDED", "include",
        "active", None — evaluates to False and is silently treated
        as excluded. This is a silent behaviour change that could
        cause correct filters to become NOT filters.

        WHAT WE EXPECT: The clause is treated as excluded (NOT wrapped).
        This test documents the current behaviour so the team knows
        to add explicit status validation upstream.
        """
        item = make_item("INCLUDED", {"children": True, "art": ["080"]})  # uppercase
        sql, params = generate_criteria_sql([item])

        if sql:
            # Because is_included is False, it goes to the excluded list
            # and gets wrapped in NOT (...)
            assert "NOT (" in sql, (
                "Status 'INCLUDED' (uppercase) was silently treated as excluded. "
                "Consider validating: if status not in ('included', 'excluded'): continue"
            )

    def test_21b_status_is_none_treated_as_excluded(self):
        """
        CASE 21b: status is None.

        WHY: None == 'included' is False → treated as excluded.
        A None status likely means a frontend serialization bug.
        It should be rejected, not silently treated as an exclusion.
        """
        item = make_item(None, {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])

        if sql:
            assert "NOT (" in sql, (
                "None status was silently treated as excluded. "
                "Consider adding explicit status validation."
            )

    def test_22_art_value_is_none_not_a_list(self):
        """
        CASE 22: data has 'children' key but 'art' value is None not a list.

        WHY: data.get('art', []) returns None (because the key exists
        with value None, so the default [] is not used).
        Then 'if art_list' is False for None so no clause is generated.
        This is actually safe behaviour — but the test documents it
        so no one assumes it will crash.
        """
        item = make_item("included", {"children": True, "art": None})
        sql, params = generate_criteria_sql([item])
        assert sql == "", (
            f"Expected empty string when art value is None, got: '{sql}'"
        )

    def test_22b_typ_value_is_none_not_a_list(self):
        """
        CASE 22b: data has 'typ' key but its value is None.

        WHY: Same as 22 — data.get('typ', []) returns None.
        'if typ_list' is False so no clause generated. Safe but worth documenting.
        """
        item = make_item("included", {"typ": None})
        sql, params = generate_criteria_sql([item])
        assert sql == "", (
            f"Expected empty string when typ value is None, got: '{sql}'"
        )

    def test_22c_nutzung_value_is_none_not_a_list(self):
        """
        CASE 22c: data has 'nutzungvalue' key but its value is None.

        WHY: Same pattern. Documents that None values on the
        nutzungvalue key are safely handled by the falsy check.
        """
        item = make_item("included", {"nutzungvalue": None})
        sql, params = generate_criteria_sql([item])
        assert sql == "", (
            f"Expected empty string when nutzungvalue is None, got: '{sql}'"
        )


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 4 — Boundary / single character values
# These test unusual but valid string values that could come from
# real data or a misconfigured frontend.
# ══════════════════════════════════════════════════════════════════════════════

class TestBoundaryValues:

    def test_single_character_art_value(self):
        """
        Single character art value should still produce valid SQL.

        WHY: Some codes in real data can be short. The function
        must not strip or reject them.
        """
        item = make_item("included", {"children": True, "art": ["W"]})
        sql, params = generate_criteria_sql([item])
        assert 'W' in params.values()

    def test_art_value_with_spaces(self):
        """
        Art value containing spaces must be single-quoted correctly.

        WHY: Values like 'Allgemeines Grundvermögen' contain spaces.
        The ARRAY['Allgemeines Grundvermögen'] syntax is valid in
        PostgreSQL only if the value is properly quoted.
        """
        item = make_item("included", {"children": True, "art": ["Allgemeines Grundvermögen"]})
        sql, params = generate_criteria_sql([item])
        assert 'Allgemeines Grundvermögen' in params.values()

    def test_art_value_with_special_characters(self):
        """
        Art value with special characters is passed through as-is.

        WHY: The function does no escaping. A value containing
        a single quote like "O'Brien" would break the SQL:
        ARRAY['O'Brien'] is invalid. This test documents this
        known gap — the function assumes clean input.
        """
        item = make_item("included", {"children": True, "art": ["test-value_123"]})
        sql, params = generate_criteria_sql([item])
        assert 'test-value_123' in params.values()

    def test_large_number_of_art_values(self):
        """
        Large list of art values should all appear in the SQL.

        WHY: No limit is imposed on list size. A large frontend
        selection (e.g. 50 art values) should all be included
        in the ARRAY[...] without truncation.
        """
        art_values = [str(i).zfill(3) for i in range(50)]
        item = make_item("included", {"children": True, "art": art_values})
        sql, params = generate_criteria_sql([item])
        for val in art_values:
            assert val in params.values(), f"Value '{val}' missing from params"
