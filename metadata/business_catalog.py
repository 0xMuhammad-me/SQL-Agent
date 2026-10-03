"""
Business semantic definitions.

This file explains business concepts
that cannot be understood only from database schema.
"""


BUSINESS_DEFINITIONS = {


    "successful_order":
    """
    Successful orders are orders where:

    orders.status IN (
        'delivered',
        'shipped'
    )

    Cancelled, returned and processing orders
    are not considered successful sales.
    """,



    "cancelled_order":
    """
    Cancelled order means:

    orders.status = 'cancelled'
    """,



    "returned_order":
    """
    Returned order means:

    orders.status = 'returned'
    """,



    "processing_order":
    """
    Processing order means:

    orders.status = 'processing'
    """,



    "product_view":
    """
    Product view event means:

    customer_events.event_type = 'view_product'
    """,



    "product_search":
    """
    Product search event means:

    customer_events.event_type = 'search'
    """,



    "purchase_event":
    """
    Purchase behavior event means:

    customer_events.event_type = 'purchase'

    For financial calculations,
    use orders and order_items tables.
    """,



    "cart_activity":
    """
    Cart activities are tracked using:

    customer_events.event_type:

    - add_to_cart
    - remove_from_cart
    """,



    "wishlist_activity":
    """
    Wishlist activity is tracked using:

    customer_events.event_type:

    - wishlist_add

    Direct wishlist table can also be used
    for current wishlist state.
    """,



    "inventory_change":
    """
    Inventory changes are stored in:

    inventory_events


    Available event types:

    - initial_stock
    - adjustment
    - damage
    - restock
    """,



    "inventory_damage":
    """
    Inventory damage means:

    inventory_events.event_type = 'damage'
    """,



    "inventory_restock":
    """
    Inventory restock means:

    inventory_events.event_type = 'restock'
    """,



    "verified_purchase_review":
    """
    Verified review means:

    reviews.verified_purchase = true
    """,



    "customer_segment":
    """
    Customer grouping information:

    customers.segment
    """,



    "restock":
    """
    Restock means:

    inventory_events.event_type = 'restock'
    """,



    "inventory_adjustment":
    """
    Inventory adjustment means a manual inventory correction.

    It is represented by:

    inventory_events.event_type = 'adjustment'
    """,


    "revenue":
    """
    Revenue represents the monetary value of successful orders.

    Revenue is based on:

    orders.total_amount

    Only successful orders are included.
    """,



    "sales_amount":
    """
    Sales amount depends on the analysis level.

    For order-level analysis:
    orders.total_amount

    For product-level analysis:
    order_items.total_price

    Successful orders should be used for sales metrics.
    """,



    "customer_behavior":
    """
    Customer behavior is tracked in customer_events.

    Available event types:

    - view_product
    - search
    - add_to_cart
    - remove_from_cart
    - purchase
    - wishlist_add
    - product_share
    """,
}