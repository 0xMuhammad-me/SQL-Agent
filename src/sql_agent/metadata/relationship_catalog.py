"""
Database relationship metadata.

This file defines valid join paths
for SQL generation.

The SQL Agent should use these relationships
instead of inventing joins.
"""


RELATIONSHIPS = (

    # Customer -> Orders
    "orders.customer_id = customers.customer_id",


    # Orders -> Order Items
    "order_items.order_id = orders.order_id",


    # Products -> Order Items
    "order_items.product_id = products.product_id",


    # Variants
    "order_items.variant_id = product_variants.variant_id",

    "product_variants.product_id = products.product_id",


    # Reviews
    "reviews.customer_id = customers.customer_id",

    "reviews.product_id = products.product_id",

    "reviews.order_id = orders.order_id",


    # Wishlist
    "wishlist.customer_id = customers.customer_id",

    "wishlist.product_id = products.product_id",


    # Cart
    "carts.customer_id = customers.customer_id",

    "cart_items.cart_id = carts.cart_id",

    "cart_items.product_id = products.product_id",

    "cart_items.variant_id = product_variants.variant_id",


    # Customer behavior
    "customer_events.customer_id = customers.customer_id",

    "customer_events.product_id = products.product_id",

    "customer_events.order_id = orders.order_id",


    # Inventory
    "inventory_events.variant_id = product_variants.variant_id",

)

