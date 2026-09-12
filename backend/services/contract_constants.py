# Contract-related audit event types and action names.
# Kept in one place so the service, validator and agent stay consistent.

# Audit event types
CONTRACT_CREATED = "CONTRACT_CREATED"
CONTRACT_UPDATED = "CONTRACT_UPDATED"
CONTRACT_ACTIVATED = "CONTRACT_ACTIVATED"
CONTRACT_CHECK = "CONTRACT_CHECK"
CONTRACT_VIOLATION = "CONTRACT_VIOLATION"
CONTRACT_ACTION_BLOCKED = "CONTRACT_ACTION_BLOCKED"
CONTRACT_COMPLETED = "CONTRACT_COMPLETED"
CONTRACT_CANCELLED = "CONTRACT_CANCELLED"

# Agent actions that the contract validator can be asked to check
ACTION_SEARCH = "search_products"
ACTION_SELECT = "select_product"
ACTION_RECOMMEND = "recommend_product"
ACTION_ADD_TO_CART = "add_to_cart"
ACTION_PAYMENT = "payment"

# Restricted actions are never allowed for the AI agent regardless of other rules
RESTRICTED_ACTIONS = [ACTION_PAYMENT]
