order_list_schema_example = {
    "id": 1,
    "date": "2025-03-02 23:26",
    "movies": ["La vida es bella", "Schindler's List"],
    "total_amount": 19.98,
    "status": "pending",
}

order_list_full_schema_example = {
    "user_id": 1,
    **order_list_schema_example
}

