"""Application boundary for expense management.

HTTP and future planning adapters consume ``ExpenseService`` or the neutral
``remaining_budget`` projection; they do not access expense tables directly.
"""
