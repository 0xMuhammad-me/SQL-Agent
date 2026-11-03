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

    SUM(orders.total_amount) / COUNT(DISTINCT orders.order_id)


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

    purchase events / product view events


    Source:

    customer_events
    """,



    "cart_abandonment_rate":
    """
    Formula:

    abandoned carts / all carts


    carts.status='abandoned'
    """,



    "cart_conversion_rate":
    """
    Formula:

    converted carts / all carts


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



    "customer_event_count":
    """
    Total number of customer behavior events.
    
    Formula:
    
    COUNT(customer_events.event_id)
    
    Source:
    customer_events
    
    No event_type filter by default.
    
    This metric may be grouped by:
    - event_type
    - product_id
    - customer_id
    - event_time
    """,



    "product_count":
    """
    Total number of products.
    
    Formula:
    
    COUNT(products.product_id)
    
    Source:
    products
    
    Product filters such as category or brand may be applied
    when explicitly requested.
    """,



    "available_product_count":
    """
    Number of distinct products that currently have stock available.
    
    Formula:
    
    COUNT(DISTINCT product_variants.product_id)
    
    Source:
    product_variants
    
    Availability rule:
    
    product_variants.stock_quantity > 0
    
    A product is considered available when at least one
    of its variants has positive stock.
    
    Do not require product or variant is_active unless
    an explicit business definition specifies that availability
    also depends on active status.
    """,



    "customer_count":
    """
    Total number of customers.
    
    Formula:
    
    COUNT(customers.customer_id)
    
    Source:
    customers
    
    Customer dimensions such as city or segment may be used
    when explicitly requested.
    """,



    "product_view_count":
    """
    Total number of product view events.
    
    Formula:
    
    COUNT(customer_events.event_id)
    
    Source:
    customer_events
    
    Filter:
    
    customer_events.event_type = 'view_product'
    
    This metric may be grouped by product_id.
    """,



    "delivered_order_revenue":
    """
    Revenue from delivered orders.
    
    Formula:
    
    SUM(orders.total_amount)
    
    Filter:
    
    orders.status = 'delivered'
    
    Source:
    orders
    """,



    "average_product_price":
    """
    Average product price.
    
    Formula:
    
    AVG(products.price)
    
    Source:
    products
    
    Product filters such as brand or category may be applied
    when explicitly requested.
    """,



    "order_count":
    """
    Total number of orders placed.
    
    Formula:
    
    COUNT(orders.order_id)
    
    Source:
    orders
    
    No successful-order status filter by default.
    
    This metric may be grouped by order_date, including
    monthly grouping using DATE_TRUNC('month', order_date).
    """,



    "average_order_value_all_orders":
    """
    Average order value across all orders.
    
    Formula:
    
    AVG(orders.total_amount)
    
    Source:
    orders
    
    No successful-order status filter by default.
    
    This metric may be grouped by customer segment or
    other customer dimensions through the orders.customer_id
    relationship.
    """,



    "product_category_revenue":
    """
    Revenue by product category based on order item sales.
    
    Formula:
    
    SUM(
        order_items.quantity
        * (order_items.unit_price - order_items.discount_amount)
    )
    
    Source:
    order_items
    
    Join:
    
    order_items.product_id = products.product_id
    
    Product category is obtained from:
    
    products.category
    
    No successful-order status filter by default.
    """,



    "average_rating_by_product_category":
    """
    Average product rating by product category.
    
    Formula:
    
    AVG(reviews.rating)
    
    Source:
    reviews
    
    Join:
    
    reviews.product_id = products.product_id
    
    Product category is obtained from:
    
    products.category
    """,



    "product_units_sold_all_orders":
    """
    Total product units sold across all orders.
    
    Formula:
    
    SUM(order_items.quantity)
    
    Source:
    order_items
    
    Join:
    
    order_items.product_id = products.product_id
    
    No successful-order status filter by default.
    
    This metric may be grouped by product_id or product_name.
    """,

}