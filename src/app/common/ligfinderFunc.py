"""Helpers for building ligfinder criteria SQL fragments.

This module converts grouped request criteria into parameterized SQL clauses
that can be combined by the routers when building the final query.
"""

COLUMNS = {
    "art": "lgb_art_values",
    "typ": "lgb_typ_values",
    "nutzung": "nutzart_list_final",
}


def _build_criterion_clause(data, param_prefix):
    """Build a single SQL clause for one criteria item.

    Returns a tuple of:
    - SQL fragment using parameter placeholders
    - dictionary of parameters for that fragment
    """
    params = {}

    # Art criteria are identified by the presence of both ``children`` and ``art``.
    if "children" in data and "art" in data:
        art_list = data.get("art", [])
        if art_list:
            param_key = f"{param_prefix}_art"
            params[param_key] = art_list
            return f"%({param_key})s::text[] && string_to_array({COLUMNS['art']}, ',')", params

    # Type criteria are handled when ``typ`` is present.
    elif "typ" in data:
        typ_list = data.get("typ", [])
        if typ_list:
            param_key = f"{param_prefix}_typ"
            params[param_key] = typ_list
            return f"%({param_key})s::text[] && string_to_array({COLUMNS['typ']}, ',')", params

    # Usage criteria are handled when ``nutzungvalue`` is present.
    elif "nutzungvalue" in data:
        nutzung_list = data.get("nutzungvalue", [])
        if nutzung_list:
            param_key = f"{param_prefix}_nutzung"
            params[param_key] = nutzung_list
            return f"%({param_key})s::text[] && string_to_array({COLUMNS['nutzung']}, ',')", params

    return "", {}


def generate_criteria_sql(groups):
    """Build the final SQL WHERE fragment for grouped criteria.

    The expected payload shape is:
    - between_groups_operator: controls how groups are combined
    - groups: list of group objects
        - inner_operator: controls how criteria inside the group are combined
        - criteria: list of criteria items

    Returns a tuple of:
    - SQL fragment string
    - merged parameters dictionary
    """
    between_op = groups.get("between_groups_operator", "AND").upper()
    group_clauses = []
    params = {}

    for group_idx, group in enumerate(groups.get("groups", [])):
        inner_op = group.get("inner_operator", "OR").upper()
        item_clauses = []

        for item_idx, item in enumerate(group.get("criteria", [])):
            data = item.get("data", {})
            status = item.get("status")
            is_included = status == "included"

            clause, item_params = _build_criterion_clause(data, f"g{group_idx}_i{item_idx}")

            if clause:
                params.update(item_params)
                if not is_included:
                    # Excluded criteria are wrapped in NOT to invert the filter.
                    clause = f"NOT ({clause})"
                item_clauses.append(clause)

        if item_clauses:
            # Combine criteria within a group using the requested inner operator.
            inner_sql = f" {inner_op} ".join(item_clauses)
            group_clauses.append(f"({inner_sql})")

    if not group_clauses:
        return "", {}

    # Combine groups using the requested between_groups operator.
    return f" {between_op} ".join(group_clauses), params