def generate_criteria_sql(criteria):
    included = []
    excluded = []
    where_clauses = []

    for item in criteria:
        data = item.data  # data type dict
        status = item.status
        is_included = status == "included"

        clause = None

        # LGB ART (has children => art filter)
        if "children" in data:
            art_list = data.get("art", [])
            if art_list:
                art_values = ', '.join(f"'{val}'" for val in art_list)
                clause = f"ARRAY[{art_values}]::text[] && string_to_array(lgb_art_values, ',')"

        # LGB TYP (has typ, no children => typ filter)
        elif "typ" in data:
            typ_list = data.get("typ", [])
            if typ_list:
                typ_values = ', '.join(f"'{val}'" for val in typ_list)
                clause = f"ARRAY[{typ_values}]::text[] && string_to_array(lgb_typ_values, ',')"

        # Nutzung
        elif "nutzungvalue" in data:
            nutzung_list = data.get("nutzungvalue", [])
            if nutzung_list:
                nutzung_values = ', '.join(f"'{val}'" for val in nutzung_list)
                clause = f"ARRAY[{nutzung_values}]::text[] && string_to_array(nutzart_list_final, ',')"

        # Add to included or excluded lists
        if clause:
            if is_included:
                included.append(clause)
            else:
                excluded.append(f"NOT ({clause})")

    # Final SQL
    if included:
        where_clauses.append("(" + " OR ".join(included) + ")")
    if excluded:
        where_clauses.append("(" + " AND ".join(excluded) + ")")

    return " AND ".join(where_clauses)
