from typing import List, Dict, Any

TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "Search the product catalog for matching products. Returns a list of products that match the criteria. Use this when the user wants to find products. The category should match a category name from the database (e.g., 'headphones', 'laptops', 'smartphones', 'earbuds', 'smartwatches', 'tablets', 'tvs', 'speakers', 'cameras', 'keyboards', 'mice'). If unsure about the exact category, leave it empty and the system will try to match.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Product category (will be matched against database categories dynamically)"
                    },
                    "max_price": {
                        "type": "number",
                        "description": "Maximum (upper bound) price in INR. Use ONLY for 'under', 'below', 'less than', or 'budget' requests."
                    },
                    "min_price": {
                        "type": "number",
                        "description": "Minimum (lower bound) price in INR. Use for 'above', 'over', 'more than', 'at least', or 'starting from' requests."
                    },
                    "brand": {
                        "type": "string",
                        "description": "Preferred brand name"
                    },
                    "query": {
                        "type": "string",
                        "description": "Free-text search query (e.g., 'wireless ergonomic', '4K display')"
                    },
                    "attributes": {
                        "type": "object",
                        "description": "Generic attribute filters as key-value pairs. Keys should match product attribute names. Supported operators: numeric values are treated as minimums, booleans as exact matches, strings as contains/equality. Examples: {\"ram_gb\": 16}, {\"noise_cancellation\": true}, {\"wireless\": true}, {\"screen_size_inches\": 55}"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": "Get detailed information about a specific product by its ID. Use this when the user asks about a specific product or wants more details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The unique product ID (e.g., 'sony-wh-ch520', 'jbl-tune-510bt')"
                    }
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_products",
            "description": "Compare multiple products side by side. Returns structured comparison data including prices, features, and specifications. Use this when the user wants to compare products.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "List of product IDs to compare (minimum 2 products)"
                    }
                },
                "required": ["product_ids"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_cart",
            "description": "Add a product to the user's shopping cart. Use this when the user wants to add an item to their cart or says 'add to cart', 'buy', 'I'll take it', etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The unique product ID to add to cart"
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Quantity to add (default: 1)",
                        "default": 1
                    }
                },
                "required": ["product_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "view_cart",
            "description": "View the current contents of the user's shopping cart. Returns all items, quantities, prices, and totals. Use this when the user asks about their cart.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_from_cart",
            "description": "Remove an item from the user's shopping cart. Use this when the user wants to remove an item from their cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "The cart item ID to remove"
                    }
                },
                "required": ["item_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "verify_cart",
            "description": "Verify the cart by checking prices and inventory availability. Use this before checkout to ensure all items are available and prices are correct.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_checkout_approval",
            "description": "Request user approval to proceed with checkout. Use this after verifying the cart and before payment. The cart must be verified first.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "initiate_payment",
            "description": "Initiate payment for an approved cart. Use this when the user wants to proceed with payment after checkout approval. The cart must be APPROVED_FOR_PAYMENT.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_payment_status",
            "description": "Get the current status of a payment. Use this when the user asks about their payment status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "payment_id": {
                        "type": "string",
                        "description": "The payment ID to check"
                    }
                },
                "required": ["payment_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_details",
            "description": "Get details of an order. Use this when the user asks about their order status or details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The order ID to look up"
                    }
                },
                "required": ["order_id"]
            }
        }
    }
]
