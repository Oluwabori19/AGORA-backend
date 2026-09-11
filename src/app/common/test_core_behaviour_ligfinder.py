import pytest
from unittest.mock import MagicMock


# ── Import the function under test ─────────────────────────────────────────────
from .ligfinderFuncAdvanced import generate_criteria_sql


# ── Helper ─────────────────────────────────────────────────────────────────────
def make_item(status: str, data) -> MagicMock:
    item = MagicMock()
    item.status = status
    item.data = data
    return item


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 1 — Core Behaviour
# Tests the fundamental happy-path behaviour of each column type.
# If any of these fail, nothing else can be trusted.
# ══════════════════════════════════════════════════════════════════════════════

class TestSingleIncludedClauses:

    def test_1_single_included_art_value(self):
        """
        CASE 1: One included ART value.

        WHY: Most basic case. Confirms the 'children' key triggers
        the lgb_art_values column and produces valid SQL.
        If this fails, the entire ART filter branch is broken.
        """
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])

        assert "ARRAY[" in sql
        assert "::text[] && string_to_array(lgb_art_values, ',')" in sql
        assert "080" in params.values()
        assert sql.startswith("(")
        assert sql.endswith(")")

    def test_2_single_included_typ_value(self):
        """
        CASE 2: One included TYP value.

        WHY: Confirms the 'typ' key triggers lgb_typ_values correctly
        and the elif branch works independently of the art branch.
        """
        item = make_item("included", {"typ": ["3020"]})
        sql, params = generate_criteria_sql([item])

        assert "ARRAY[" in sql
        assert "::text[] && string_to_array(lgb_typ_values, ',')" in sql
        assert "3020" in params.values()

    def test_3_single_included_nutzung_value(self):
        """
        CASE 3: One included nutzungvalue.

        WHY: Confirms the 'nutzungvalue' key triggers nutzart_list_final.
        This is the most commonly used filter type in practice.
        """
        item = make_item("included", {"nutzungvalue": ["wohnbauflaeche"]})
        sql, params = generate_criteria_sql([item])

        assert "ARRAY[" in sql
        assert "::text[] && string_to_array(nutzart_list_final, ',')" in sql
        assert "wohnbauflaeche" in params.values()

    def test_4_single_excluded_art_value(self):
        """
        CASE 4: One excluded ART value.

        WHY: Confirms NOT (...) wrapping works for art exclusions.
        Excluded items must be negated — without this a user's
        exclusion filter would be treated as inclusion.
        """
        item = make_item("excluded", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])

        assert "NOT (" in sql
        assert "lgb_art_values" in sql

    def test_5_single_excluded_nutzung_value(self):
        """
        CASE 5: One excluded nutzungvalue.

        WHY: The most commonly excluded type in real usage.
        For example excluding 'strassenverkehr' from results.
        Must produce NOT (...) correctly.
        """
        item = make_item("excluded", {"nutzungvalue": ["strassenverkehr"]})
        sql, params = generate_criteria_sql([item])

        assert "NOT (" in sql
        assert "nutzart_list_final" in sql

    def test_multiple_art_values_in_single_item(self):
        """
        Multiple art values in one item are combined into one ARRAY[...].

        WHY: A user may select multiple art codes at once.
        All must appear in the same ARRAY clause, not split
        into separate clauses.
        """
        item = make_item("included", {"children": True, "art": ["080", "081", "085"]})
        sql, params = generate_criteria_sql([item])

        assert '080' in params.values()
        assert '081' in params.values()
        assert '085' in params.values()

    def test_multiple_nutzung_values_in_single_item(self):
        """
        Multiple nutzung values in one item are combined into one ARRAY[...].

        WHY: Same as above — a user selecting multiple nutzung types
        must get all of them in one ARRAY clause.
        """
        item = make_item("included", {"nutzungvalue": ["wohnbauflaeche", "industrieundgewerbeflaeche"]})
        sql, params = generate_criteria_sql([item])

        assert 'wohnbauflaeche' in params.values()
        assert 'industrieundgewerbeflaeche' in params.values()


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 2 — Combination Tests
# Tests how multiple criteria items interact with each other.
# ══════════════════════════════════════════════════════════════════════════════

class TestCombinations:

    def test_6_two_included_items_same_type_joined_with_or(self):
        """
        CASE 6: Two included ART items joined with OR.

        WHY: Multiple included items of the same type should be
        combined with OR — a parcel matches if it has EITHER value.
        This is the core logic of the included list.
        """
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"children": True, "art": ["081"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert '080' in params.values()
        assert '081' in params.values()
        assert " OR " in sql
        assert "lgb_art_values" in sql

    def test_7_two_excluded_items_joined_with_and(self):
        """
        CASE 7: Two excluded nutzung items joined with AND.

        WHY: Multiple exclusions must ALL be satisfied simultaneously.
        A parcel must NOT have strassenverkehr AND NOT have weg.
        If OR was used instead, excluding one would not exclude the other.
        """
        items = [
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
            make_item("excluded", {"nutzungvalue": ["weg"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert sql.count("NOT (") == 2
        assert " AND " in sql

    def test_8_one_included_and_one_excluded(self):
        """
        CASE 8: One included AND one excluded item.

        WHY: The most common real-world pattern — include certain
        art types AND exclude certain nutzung types.
        The two groups must be joined with AND at the top level.
        """
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert "lgb_art_values" in sql
        assert "NOT (" in sql
        assert "nutzart_list_final" in sql
        assert " AND " in sql

    def test_9_multiple_included_types_joined_with_or(self):
        """
        CASE 9: Included ART, TYP and Nutzung all in one call.

        WHY: Tests that items from different column types can all
        appear in the same included group and are joined with OR.
        All three column types must be represented.
        """
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"typ": ["3020"]}),
            make_item("included", {"nutzungvalue": ["wohnbauflaeche"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert "lgb_art_values" in sql
        assert "lgb_typ_values" in sql
        assert "nutzart_list_final" in sql
        assert " OR " in sql

    def test_10_multiple_exclusions_across_different_column_types(self):
        """
        CASE 10: Excluded ART and excluded nutzung.

        WHY: Exclusions must work across all three columns simultaneously.
        Each excluded item from a different column must produce its
        own NOT (...) clause joined with AND.
        """
        items = [
            make_item("excluded", {"children": True, "art": ["080"]}),
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert sql.count("NOT (") == 2
        assert "lgb_art_values" in sql
        assert "nutzart_list_final" in sql
        assert " AND " in sql

    def test_only_excluded_no_included_returns_valid_sql(self):
        """
        All exclusions and no inclusions should still produce valid SQL.

        WHY: Some implementations break when the included list is empty
        and only the excluded group exists. The result must still be
        a valid WHERE clause with only NOT (...) clauses.
        """
        items = [
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
            make_item("excluded", {"nutzungvalue": ["weg"]}),
            make_item("excluded", {"nutzungvalue": ["platz"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert sql != ""
        assert sql.count("NOT (") == 3
        assert " OR " not in sql


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 3 — Priority / Key Precedence
# Tests the if/elif chain to confirm correct column is selected
# when multiple keys are present in the same data dict.
# ══════════════════════════════════════════════════════════════════════════════

class TestKeyPrecedence:

    def test_17_children_key_takes_priority_over_typ(self):
        """
        CASE 17: Both 'children' and 'typ' present — children wins.

        WHY: The function uses if/elif so 'children' is checked first.
        If this breaks, the wrong column gets queried silently —
        a typ filter would be applied instead of an art filter.
        """
        item = make_item("included", {"children": True, "art": ["080"], "typ": ["3020"]})
        sql, params = generate_criteria_sql([item])

        assert "lgb_art_values" in sql
        assert "lgb_typ_values" not in sql

    def test_18_typ_takes_priority_over_nutzung_when_no_children(self):
        """
        CASE 18: Both 'typ' and 'nutzungvalue' present, no 'children' — typ wins.

        WHY: Same elif chain issue. nutzungvalue should only be used
        when neither children nor typ is present. If this breaks,
        a typ filter silently becomes a nutzung filter.
        """
        item = make_item("included", {"typ": ["3020"], "nutzungvalue": ["wohnbauflaeche"]})
        sql, params = generate_criteria_sql([item])

        assert "lgb_typ_values" in sql
        assert "nutzart_list_final" not in sql

    def test_19_children_without_art_key_produces_no_clause(self):
        """
        CASE 19: 'children' key present but no 'art' key at all.

        WHY: data.get('art') returns None → or [] makes it [] →
        list comprehension produces [] → if art_list is False.
        No clause should be generated. Without this guard the
        function would emit ARRAY[]::text[] which is broken SQL.
        """
        item = make_item("included", {"children": True})
        sql, params = generate_criteria_sql([item])

        assert sql == ""


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 4 — SQL Output Format
# Tests that the SQL string produced is syntactically correct
# and uses the right operators, column names and quoting.
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLOutputFormat:

    def test_20_art_values_are_in_params_not_sql(self):
        """
        CASE 20: With parameterised queries, values are in params not SQL.

        WHY: After Fix 3 the SQL contains %s placeholders and values
        are passed separately to the DB driver. The driver handles
        quoting — we must not quote them ourselves.
        """
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])

        assert ":p" in sql, "SQL should contain named :p placeholder"
        assert "080" in params.values(), "Value should be in params values"
        assert "'080'" not in sql, "Value must not be quoted in SQL string"

    def test_21_correct_column_name_for_art(self):
        """
        CASE 21: ART clause references lgb_art_values column.

        WHY: A typo in the column name silently queries the wrong
        column — the query runs but returns wrong results.
        """
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])

        assert "lgb_art_values" in sql

    def test_21b_correct_column_name_for_typ(self):
        """TYP clause references lgb_typ_values column."""
        item = make_item("included", {"typ": ["3020"]})
        sql, params = generate_criteria_sql([item])

        assert "lgb_typ_values" in sql

    def test_21c_correct_column_name_for_nutzung(self):
        """Nutzung clause references nutzart_list_final column."""
        item = make_item("included", {"nutzungvalue": ["wohnbauflaeche"]})
        sql, params = generate_criteria_sql([item])

        assert "nutzart_list_final" in sql

    def test_22_array_overlap_operator_present(self):
        """
        CASE 22: SQL uses the && array overlap operator.

        WHY: The && operator is what makes the PostgreSQL array
        intersection work. Any other operator would produce wrong
        results or a syntax error.
        """
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])

        assert "&&" in sql

    def test_23_string_to_array_with_comma_separator(self):
        """
        CASE 23: SQL uses string_to_array with comma separator.

        WHY: The column values are stored as comma-separated strings.
        string_to_array splits them for the && comparison. If the
        separator changes or the function is wrong, no rows match.
        """
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])

        assert "string_to_array" in sql
        assert "','" in sql

    def test_24_cast_to_text_array_present(self):
        """
        CASE 24: SQL casts the ARRAY to text[].

        WHY: Without ::text[] PostgreSQL may throw a type mismatch
        error when comparing the ARRAY literal against the result
        of string_to_array which returns text[].
        """
        item = make_item("included", {"children": True, "art": ["080"]})
        sql, params = generate_criteria_sql([item])

        assert "::text[]" in sql

    def test_25_included_group_wrapped_in_parentheses(self):
        """
        CASE 25: Included group is wrapped in parentheses.

        WHY: Without parentheses, SQL operator precedence can cause
        AND to bind tighter than OR, producing logically wrong results.
        (A OR B) AND (NOT C) is different from A OR B AND NOT C.
        """
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"children": True, "art": ["081"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert sql.startswith("(")
        assert sql.endswith(")")

    def test_26_excluded_group_wrapped_in_parentheses(self):
        """
        CASE 26: Excluded group is wrapped in parentheses.

        WHY: Same reason as test_25. The NOT clauses joined
        with AND must be grouped so they apply together.
        """
        items = [
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
            make_item("excluded", {"nutzungvalue": ["weg"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert sql.startswith("(")
        assert sql.endswith(")")


# ══════════════════════════════════════════════════════════════════════════════
# GROUP 5 — Real-World Scenario Tests
# End-to-end tests matching actual queries used in production.
# ══════════════════════════════════════════════════════════════════════════════

class TestRealWorldScenarios:

    def test_27_art_080_or_art_081(self):
        """
        CASE 27: (Art 080 OR Art 081) — most common real query.

        WHY: Two included art items must be combined with OR
        inside one group. This is the first query most users build.
        """
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"children": True, "art": ["081"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert '080' in params.values()
        assert '081' in params.values()
        assert " OR " in sql

    def test_28_art_included_nutzung_excluded(self):
        """
        CASE 28: (Art 080 OR Art 081) AND NOT strassenverkehr.

        WHY: The classic pattern — include art types, exclude
        a nutzung type. Both groups must appear joined with AND.
        """
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

    def test_29_all_exclusions_no_inclusions(self):
        """
        CASE 29: NOT Art 080 AND NOT Art 081 AND NOT strassenverkehr.

        WHY: All exclusions, no inclusions. The included list is
        empty — only the excluded group appears in the output.
        Some implementations break when included is empty.
        """
        items = [
            make_item("excluded", {"children": True, "art": ["080"]}),
            make_item("excluded", {"children": True, "art": ["081"]}),
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert sql != ""
        assert sql.count("NOT (") == 3
        assert " OR " not in sql

    def test_30_all_three_column_types_included(self):
        """
        CASE 30: Art + TYP + Nutzung all included together.

        WHY: All three column types in one included group.
        Tests the full OR chain across different columns.
        """
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"typ": ["3020"]}),
            make_item("included", {"nutzungvalue": ["wohnbauflaeche"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert "lgb_art_values" in sql
        assert "lgb_typ_values" in sql
        assert "nutzart_list_final" in sql
        assert " OR " in sql
        assert " AND " not in sql

    def test_31_art_and_typ_included_nutzung_excluded(self):
        """
        CASE 31: (Art 080 OR TYP 3020) AND NOT strassenverkehr.

        WHY: Mixed column types in included group with an exclusion.
        Confirms the full pipeline works end to end across all
        three column types with both inclusion and exclusion.
        """
        items = [
            make_item("included", {"children": True, "art": ["080"]}),
            make_item("included", {"typ": ["3020"]}),
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
        ]
        sql, params = generate_criteria_sql(items)

        assert "lgb_art_values" in sql
        assert "lgb_typ_values" in sql
        assert "NOT (" in sql
        assert "strassenverkehr" in params.values()
        assert " AND " in sql
        assert " OR " in sql

    def test_32_multiple_values_across_all_types(self):
        """
        CASE 32: Multiple values in each type.

        WHY: Simulates a heavy real-world filter with multiple
        art codes, multiple typ codes and multiple nutzung exclusions.
        Confirms the function scales to real usage.
        """
        items = [
            make_item("included", {"children": True, "art": ["080", "081", "085"]}),
            make_item("included", {"typ": ["2631", "2649", "3020"]}),
            make_item("excluded", {"nutzungvalue": ["strassenverkehr"]}),
            make_item("excluded", {"nutzungvalue": ["weg"]}),
            make_item("excluded", {"nutzungvalue": ["platz"]}),
        ]
        sql, params = generate_criteria_sql(items)

        for val in ["'080'", "'081'", "'085'", "'2631'", "'2649'", "'3020'"]:
            assert val.strip("'") in params.values(), f"Expected {val} in params"

        assert sql.count("NOT (") == 3
        assert " AND " in sql
        assert " OR " in sql
