import pytest
from unittest.mock import MagicMock
from .ligfinderFuncAdvanced import generate_criteria_sql, CriteriaLimitExceeded


# ── Helper: build a mock criteria item ────────────────────────────────────────
def make_item(status: str, data: dict) -> MagicMock:
    item = MagicMock()
    item.status = status
    item.data = data
    return item


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Empty / no-op cases
# ══════════════════════════════════════════════════════════════════════════════

class TestEmptyCases:

    def test_empty_criteria_list_returns_empty_string(self):
        sql, params = generate_criteria_sql([])
        assert sql == ""
        assert params == {}

    def test_item_with_no_matching_key_produces_no_clause(self):
        item = make_item("included", {"unknown_key": ["value"]})
        sql, params = generate_criteria_sql([item])
        assert sql == ""
        assert params == {}

    def test_item_with_empty_art_list_produces_no_clause(self):
        item = make_item("included", {"children": True, "art": []})
        sql, params = generate_criteria_sql([item])
        assert sql == ""

    def test_item_with_empty_typ_list_produces_no_clause(self):
        item = make_item("included", {"typ": []})
        sql, params = generate_criteria_sql([item])
        assert sql == ""

    def test_item_with_empty_nutzung_list_produces_no_clause(self):
        item = make_item("included", {"nutzungvalue": []})
        sql, params = generate_criteria_sql([item])
        assert sql == ""


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Single included clauses
# ══════════════════════════════════════════════════════════════════════════════

class TestSingleIncludedClauses:

    def test_single_included_art_value(self):
        """One included ART value: column in SQL, value in params."""
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])
        assert "string_to_array(lgb_art_values, ',')" in sql
        assert "080" in params.values()

    def test_single_included_art_wrapped_in_or_group(self):
        """Included clauses are wrapped in (... OR ...)."""
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])
        assert sql.startswith("(")
        assert sql.endswith(")")

    def test_single_included_typ_value(self):
        item = make_item("included", {"typ": ["3020"]})
        sql, params = generate_criteria_sql([item])
        assert "string_to_array(lgb_typ_values, ',')" in sql
        assert "3020" in params.values()

    def test_single_included_nutzung_value(self):
        item = make_item("included", {"nutzungvalue": ["wohnbauflaeche"]})
        sql, params = generate_criteria_sql([item])
        assert "string_to_array(nutzart_list_final, ',')" in sql
        assert "wohnbauflaeche" in params.values()

    def test_multiple_art_values_in_single_item(self):
        """Multiple art values in one item are all registered in params."""
        item = make_item("included", {"children": True, "art": ["080", "081", "085"]})
        sql, params = generate_criteria_sql([item])
        assert "080" in params.values()
        assert "081" in params.values()
        assert "085" in params.values()

    def test_multiple_nutzung_values_in_single_item(self):
        item = make_item("included", {"nutzungvalue": ["wohnbauflaeche", "strassenverkehr"]})
        sql, params = generate_criteria_sql([item])
        assert "wohnbauflaeche" in params.values()
        assert "strassenverkehr" in params.values()


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Single excluded clauses
# ══════════════════════════════════════════════════════════════════════════════

class TestSingleExcludedClauses:

    def test_single_excluded_art_value(self):
        item = make_item("excluded", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])
        assert "NOT (" in sql
        assert "lgb_art_values" in sql

    def test_single_excluded_typ_value(self):
        item = make_item("excluded", {"typ": ["3020"]})
        sql, params = generate_criteria_sql([item])
        assert "NOT (" in sql
        assert "lgb_typ_values" in sql

    def test_single_excluded_nutzung_value(self):
        item = make_item("excluded", {"nutzungvalue": ["strassenverkehr"]})
        sql, params = generate_criteria_sql([item])
        assert "NOT (" in sql
        assert "nutzart_list_final" in sql

    def test_excluded_clauses_joined_with_and(self):
        items = [
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
            make_item("excluded", {"nutzungvalue": ["weg"]}),
        ]
        sql, params = generate_criteria_sql(items)
        assert " AND " in sql


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Mixed included + excluded
# ══════════════════════════════════════════════════════════════════════════════

class TestMixedIncludedAndExcluded:

    def test_included_and_excluded_joined_with_and(self):
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
        ]
        sql, params = generate_criteria_sql(items)
        assert " AND " in sql
        assert "lgb_art_values" in sql
        assert "NOT (" in sql
        assert "nutzart_list_final" in sql

    def test_multiple_included_joined_with_or(self):
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"nutzungvalue": ["wohnbauflaeche"]}),
        ]
        sql, params = generate_criteria_sql(items)
        assert " OR " in sql

    def test_multiple_excluded_joined_with_and(self):
        items = [
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
            make_item("excluded", {"nutzungvalue": ["weg"]}),
            make_item("excluded", {"nutzungvalue": ["platz"]}),
        ]
        sql, params = generate_criteria_sql(items)
        assert sql.count("NOT (") == 3
        assert " AND " in sql


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Priority / key precedence
# ══════════════════════════════════════════════════════════════════════════════

class TestKeyPrecedence:

    def test_children_key_takes_priority_over_typ(self):
        item = make_item("included", {"children": True, "art": ["080"], "typ": ["3020"]})
        sql, params = generate_criteria_sql([item])
        assert "lgb_art_values" in sql
        assert "lgb_typ_values" not in sql

    def test_typ_takes_priority_over_nutzung_when_no_children(self):
        item = make_item("included", {"typ": ["3020"], "nutzungvalue": ["wohnbauflaeche"]})
        sql, params = generate_criteria_sql([item])
        assert "lgb_typ_values" in sql
        assert "nutzart_list_final" not in sql

    def test_children_without_art_key_produces_no_clause(self):
        item = make_item("included", {"children": True})
        sql, params = generate_criteria_sql([item])
        assert sql == ""


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — SQL correctness (named placeholders + params dict)
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLCorrectness:

    def test_art_placeholder_in_sql_value_in_params(self):
        """Values never appear in the SQL string — only in params."""
        item = make_item("included", {"children": True, "art": ["Allgemeines Grundvermögen"]})
        sql, params = generate_criteria_sql([item])
        assert ":p0" in sql
        assert "Allgemeines Grundvermögen" not in sql        # value must NOT be in SQL
        assert "Allgemeines Grundvermögen" in params.values()

    def test_typ_placeholder_in_sql_value_in_params(self):
        item = make_item("included", {"typ": ["2631"]})
        sql, params = generate_criteria_sql([item])
        assert ":p0" in sql
        assert "2631" not in sql
        assert "2631" in params.values()

    def test_nutzung_placeholder_in_sql_value_in_params(self):
        item = make_item("included", {"nutzungvalue": ["industrieundgewerbeflaeche"]})
        sql, params = generate_criteria_sql([item])
        assert ":p0" in sql
        assert "industrieundgewerbeflaeche" not in sql
        assert "industrieundgewerbeflaeche" in params.values()

    def test_art_uses_lgb_art_values_column(self):
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])
        assert "lgb_art_values" in sql

    def test_typ_uses_lgb_typ_values_column(self):
        item = make_item("included", {"typ": ["3020"]})
        sql, params = generate_criteria_sql([item])
        assert "lgb_typ_values" in sql

    def test_nutzung_uses_nutzart_list_final_column(self):
        item = make_item("included", {"nutzungvalue": ["wohnbauflaeche"]})
        sql, params = generate_criteria_sql([item])
        assert "nutzart_list_final" in sql

    def test_array_overlap_operator_present(self):
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])
        assert "&&" in sql

    def test_string_to_array_function_present(self):
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])
        assert "string_to_array" in sql
        assert "','" in sql

    def test_cast_to_text_array_present(self):
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])
        assert "::text[]" in sql

    def test_named_placeholders_are_unique_across_multiple_items(self):
        """Each value gets a unique :pN key — no collisions across items."""
        items = [
            make_item("included", {"children": True, "art": ["080", "081"]}),
            make_item("included", {"nutzungvalue": ["wohnbauflaeche"]}),
        ]
        sql, params = generate_criteria_sql(items)
        assert len(params) == 3
        assert set(params.values()) == {"080", "081", "wohnbauflaeche"}


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — Limits and rejection (replaces old silent-truncation tests)
# ══════════════════════════════════════════════════════════════════════════════

class TestLimitsAndRejection:

    def test_too_many_criteria_raises_criteria_limit_exceeded(self):
        """Exceeding max_criteria_items raises CriteriaLimitExceeded, not generic ValueError."""
        items = [make_item("included", {"children": True, "art": ["080"]}) for _ in range(5)]
        with pytest.raises(CriteriaLimitExceeded):
            generate_criteria_sql(items, max_criteria_items=3)

    def test_oversized_art_list_raises_criteria_limit_exceeded(self):
        """Art list over max_list_size raises CriteriaLimitExceeded — data is never silently dropped."""
        big_list = [str(i) for i in range(10)]
        item = make_item("included", {"children": True, "art": big_list})
        with pytest.raises(CriteriaLimitExceeded):
            generate_criteria_sql([item], max_list_size=5)

    def test_oversized_typ_list_raises_criteria_limit_exceeded(self):
        big_list = [str(i) for i in range(10)]
        item = make_item("included", {"typ": big_list})
        with pytest.raises(CriteriaLimitExceeded):
            generate_criteria_sql([item], max_list_size=5)

    def test_oversized_nutzung_list_raises_criteria_limit_exceeded(self):
        big_list = [f"nutzung_{i}" for i in range(10)]
        item = make_item("included", {"nutzungvalue": big_list})
        with pytest.raises(CriteriaLimitExceeded):
            generate_criteria_sql([item], max_list_size=5)

    def test_exactly_at_limit_does_not_raise(self):
        """A list exactly at the configured limit passes through."""
        items = [make_item("included", {"children": True, "art": ["080"]}) for _ in range(3)]
        sql, params = generate_criteria_sql(items, max_criteria_items=3)
        assert sql != ""

    def test_limits_are_configurable_per_call(self):
        """Limits are per-call — raising the limit on a large payload makes it succeed."""
        big_items = [make_item("included", {"children": True, "art": ["080"]}) for _ in range(10)]
        with pytest.raises(CriteriaLimitExceeded):
            generate_criteria_sql(big_items, max_criteria_items=5)
        # Same payload succeeds when the limit is raised
        sql, params = generate_criteria_sql(big_items, max_criteria_items=20)
        assert sql != ""


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — Real-world scenario tests
# ══════════════════════════════════════════════════════════════════════════════

class TestRealWorldScenarios:

    def test_scenario_art_080_or_081(self):
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"children": True, "art": ["081"]}),
        ]
        sql, params = generate_criteria_sql(items)
        assert "080" in params.values()
        assert "081" in params.values()
        assert " OR " in sql
        assert "lgb_art_values" in sql

    def test_scenario_art_and_nutzung_included(self):
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"nutzungvalue": ["wohnbauflaeche"]}),
        ]
        sql, params = generate_criteria_sql(items)
        assert "lgb_art_values" in sql
        assert "nutzart_list_final" in sql
        assert " OR " in sql

    def test_scenario_art_included_nutzung_excluded(self):
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"children": True, "art": ["081"]}),
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
        ]
        sql, params = generate_criteria_sql(items)
        assert "lgb_art_values" in sql
        assert "NOT (" in sql
        assert "strassenverkehr" in params.values()
        assert " AND " in sql

    def test_scenario_multiple_exclusions(self):
        items = [
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
            make_item("excluded", {"nutzungvalue": ["weg"]}),
            make_item("excluded", {"nutzungvalue": ["platz"]}),
        ]
        sql, params = generate_criteria_sql(items)
        assert sql.count("NOT (") == 3
        assert "strassenverkehr" in params.values()
        assert "weg" in params.values()
        assert "platz" in params.values()

    def test_scenario_only_excluded_art(self):
        items = [
            make_item("excluded", {"children": True, "art": ["080"]}),
            make_item("excluded", {"children": True, "art": ["081"]}),
        ]
        sql, params = generate_criteria_sql(items)
        assert sql.count("NOT (") == 2
        assert "lgb_art_values" in sql

    def test_scenario_typ_included(self):
        item = make_item("included", {"typ": ["2649"]})
        sql, params = generate_criteria_sql([item])
        assert "2649" in params.values()
        assert "lgb_typ_values" in sql

    def test_scenario_all_three_column_types(self):
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"typ": ["3020"]}),
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
        ]
        sql, params = generate_criteria_sql(items)
        assert "lgb_art_values" in sql
        assert "lgb_typ_values" in sql
        assert "nutzart_list_final" in sql
        assert "NOT (" in sql

    def test_scenario_items_with_mixed_valid_and_invalid(self):
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"unknown_key": ["value"]}),   # skipped
            make_item("included", {"nutzungvalue": []}),          # skipped
        ]
        sql, params = generate_criteria_sql(items)
        assert "lgb_art_values" in sql
        assert "unknown_key" not in sql
        assert " OR " not in sql   # only one valid clause, no OR needed

    def test_scenario_realistic_composite_filter(self):
        """20 nutzung exclusions + 3 art inclusions + 2 typ inclusions — stays under default limits."""
        nutzung_items = [
            make_item("excluded", {"nutzungvalue": [f"nutzung_{i}"]}) for i in range(20)
        ]
        art_items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"children": True, "art": ["081"]}),
            make_item("included", {"children": True, "art": ["085"]}),
        ]
        typ_items = [
            make_item("included", {"typ": ["3020"]}),
            make_item("included", {"typ": ["2649"]}),
        ]
        items = art_items + typ_items + nutzung_items  # 25 items — well under default limit of 100
        sql, params = generate_criteria_sql(items)
        assert sql.count("NOT (") == 20
        assert "lgb_art_values" in sql
        assert "lgb_typ_values" in sql
        assert len(params) == 25   # 3 art + 2 typ + 20 nutzung values
