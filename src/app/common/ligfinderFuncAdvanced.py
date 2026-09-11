DEFAULT_MAX_VALUE_LENGTH = 255   # Max characters per filter value — prevents DoS via long strings
DEFAULT_MAX_LIST_SIZE = 200      # Max values per list — prevents DoS via large SQL arrays
DEFAULT_MAX_CRITERIA_ITEMS = 100 # Max criteria items per call — prevents DoS via query overload


class CriteriaLimitExceeded(ValueError):
    """Raised when input exceeds a configured safety limit.
    Callers should catch this and return a 4xx, not let it bubble as a 500."""
    pass


def _sanitise_list(raw_list, max_value_length: int) -> list:
    """
    Clean a list of filter values before SQL generation.
    Does NOT enforce list size — caller rejects oversized lists.
    Removes: None, empty strings, whitespace-only, null bytes.
    Converts: integers to strings.
    Raises CriteriaLimitExceeded if any value exceeds max_value_length.
    """
    if not raw_list:
        return []

    clean = []

    for val in raw_list:
        # Skip None values
        if val is None:
            continue

        # Convert to string and strip whitespace
        val = str(val).strip()
        if not val:
            continue

        # Remove null bytes BEFORE length check to prevent null byte injection
        val = val.replace('\x00', '')
        if not val:
            continue

        # Reject values exceeding max length — silent drop would give partial results
        if len(val) > max_value_length:
            raise CriteriaLimitExceeded(
                f"Filter value exceeds maximum length of {max_value_length} characters: "
                f"{val[:40]!r}{'...' if len(val) > 40 else ''}"
            )

        clean.append(val)

    # No size limit enforced here — caller checks len(clean) against
    # max_list_size and raises CriteriaLimitExceeded if it's too large.
    return clean


def generate_criteria_sql(
    criteria,
    max_value_length: int = DEFAULT_MAX_VALUE_LENGTH,
    max_list_size: int = DEFAULT_MAX_LIST_SIZE,
    max_criteria_items: int = DEFAULT_MAX_CRITERIA_ITEMS,
):
    """
    Build a parameterised SQL WHERE clause from a list of criteria items.

    Returns a tuple of (sql_string, params) where:
        - sql_string contains :p0, :p1, ... named placeholders
        - params is a dict of {"p0": value, "p1": value, ...}

    Usage with SQLAlchemy:
        from sqlalchemy import text
        sql, params = generate_criteria_sql(criteria)
        connection.execute(text(f"SELECT * FROM parcels WHERE {sql}"), params)

    Why named parameters:
        SQLAlchemy's text() binds by name regardless of the underlying DBAPI.
        Passing values separately means SQL injection is impossible — the driver
        handles all escaping, values never touch the SQL string.

    Raises:
        CriteriaLimitExceeded — oversized input is rejected, not silently
        truncated, so results are never partial without an error.
    """
    # Reject too many criteria items outright — do not process a partial set
    if len(criteria) > max_criteria_items:
        raise CriteriaLimitExceeded(
            f"Too many criteria items: {len(criteria)}. Maximum is {max_criteria_items}."
        )

    included = []
    excluded = []
    where_clauses = []
    params = {}       # named placeholders — SQLAlchemy text() requires a dict, not a list
    param_counter = 0

    def _next_placeholders(values):
        # Registers each value under a unique name and returns its :pN references
        nonlocal param_counter
        names = []
        for v in values:
            name = f"p{param_counter}"
            params[name] = v
            names.append(f":{name}")
            param_counter += 1
        return names

    for item in criteria:
        data = item.data
        status = item.status

        # Skip items whose data is not a dict — prevents crash on None/string data
        if not isinstance(data, dict):
            continue

        is_included = status == "included"
        clause = None

        # LGB ART (has children => art filter)
        if "children" in data:
            art_list = _sanitise_list(data.get("art"), max_value_length)
            if art_list:
                # Reject rather than truncate — a partial list gives silently wrong results
                if len(art_list) > max_list_size:
                    raise CriteriaLimitExceeded(
                        f"Art list has {len(art_list)} values, exceeds max_list_size={max_list_size}."
                    )
                placeholders = ', '.join(_next_placeholders(art_list))
                clause = f"ARRAY[{placeholders}]::text[] && string_to_array(lgb_art_values, ',')"

        # LGB TYP (has typ, no children => typ filter)
        elif "typ" in data:
            typ_list = _sanitise_list(data.get("typ"), max_value_length)
            if typ_list:
                if len(typ_list) > max_list_size:
                    raise CriteriaLimitExceeded(
                        f"Typ list has {len(typ_list)} values, exceeds max_list_size={max_list_size}."
                    )
                placeholders = ', '.join(_next_placeholders(typ_list))
                clause = f"ARRAY[{placeholders}]::text[] && string_to_array(lgb_typ_values, ',')"

        # Nutzung
        elif "nutzungvalue" in data:
            nutzung_list = _sanitise_list(data.get("nutzungvalue"), max_value_length)
            if nutzung_list:
                if len(nutzung_list) > max_list_size:
                    raise CriteriaLimitExceeded(
                        f"Nutzung list has {len(nutzung_list)} values, exceeds max_list_size={max_list_size}."
                    )
                placeholders = ', '.join(_next_placeholders(nutzung_list))
                clause = f"ARRAY[{placeholders}]::text[] && string_to_array(nutzart_list_final, ',')"

        # Add to included or excluded lists
        if clause:
            if is_included:
                included.append(clause)
            else:
                # NOT wraps the clause — params dict is unaffected by wrapping
                excluded.append(f"NOT ({clause})")

    # Final SQL
    if included:
        where_clauses.append("(" + " OR ".join(included) + ")")
    if excluded:
        where_clauses.append("(" + " AND ".join(excluded) + ")")

    sql = " AND ".join(where_clauses)
    return sql, params
