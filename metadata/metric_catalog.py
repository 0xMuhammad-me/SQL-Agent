"""
Business metrics definitions.

Used by SQL planning and validation.
"""


METRIC_DEFINITIONS = {


    "total_revenue":
    """
    Revenue calculation:

    SUM(orders.total_amount)


    Filter:

    orders.status IN (
        'delivered',
        'shipped'
    )
    """,



    "total_orders":
    """
    Number of successful orders:

    COUNT(DISTINCT orders.order_id)


    Filter:

    successful orders only.
    """,



    "average_order_value":
    """
    Average order value:

    SUM(orders.total_amount)
    /
    COUNT(DISTINCT orders.order_id)


    Successful orders only.
    """,



    "units_sold":
    """
    Total sold quantity:

    SUM(order_items.quantity)


    Join:

    order_items -> orders


    Successful orders only.
    """,



    "product_revenue":
    """
    Product revenue:

    SUM(order_items.total_price)


    GROUP BY:

    product_id
    """,



    "customer_lifetime_value":
    """
    Customer lifetime value:

    SUM(orders.total_amount)


    GROUP BY:

    customers.customer_id


    Successful orders only.
    """,



    "repeat_customer":
    """
    Repeat customer means:

    Customer with more than one
    successful order.
    """,



    "product_conversion_rate":
    """
    Product conversion rate:

    purchase events
    /
    product view events


    Source:

    customer_events
    """,



    "cart_abandonment_rate":
    """
    Formula:

    abandoned carts
    /
    all carts


    carts.status='abandoned'
    """,



    "cart_conversion_rate":
    """
    Formula:

    converted carts
    /
    all carts


    carts.status='converted'
    """,



    "average_product_rating":
    """
    Average product rating:

    AVG(reviews.rating)


    GROUP BY:

    product_id
    """,



    "inventory_damage_loss":
    """
    Inventory loss:

    SUM(inventory_events.quantity_change)


    Filter:

    event_type='damage'
    """,



    "inventory_restock_amount":
    """
    Restocked quantity:

    SUM(inventory_events.quantity_change)


    Filter:

    event_type='restock'
    """,



    "top_selling_products":
    """
    Rank products by units sold.
    
    Formula:
    
    SUM(order_items.quantity)
    
    Join:
    
    order_items.order_id = orders.order_id
    
    Only successful orders are included:
    
    orders.status IN (
        'delivered',
        'shipped'
    )
    
    Group by product.
    """,



    "top_revenue_products":
    """
    Rank products by product-level revenue.
    
    Formula:
    
    SUM(order_items.total_price)
    
    Join:
    
    order_items.order_id = orders.order_id
    
    Only successful orders are included:
    
    orders.status IN (
        'delivered',
        'shipped'
    )
    
    Group by product.
    """,



    "product_interest":
    """
    Product interest is measured using customer behavior events.
    
    Relevant events:
    
    - view_product
    - wishlist_add
    - add_to_cart
    
    These signals should be reported separately by default.
    
    Optional combined interest score may be defined only
    when an explicit weighting scheme is provided.
    """,



    "inventory_restocked_units":
    """
    Total units added through restocking.
    
    Formula:
    
    SUM(inventory_events.quantity_change)
    
    Filter:
    
    inventory_events.event_type = 'restock'
    """,



    "current_variant_stock":
    """
    Current stock for a product variant is stored in:
    
    product_variants.stock_quantity
    """,

}