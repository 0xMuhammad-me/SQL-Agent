from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class ColumnSchema:
    name: str
    data_type: str
    nullable: bool
    description: str = ""
    foreign_key: Optional[str] = None


@dataclass(frozen=True)
class TableSchema:
    name: str
    description: str
    columns: Tuple[ColumnSchema, ...]


SCHEMA_CATALOG = (

    TableSchema(
        name="customers",
        description="Customer master information",
        columns=(

            ColumnSchema("customer_id", "bigint", False),

            ColumnSchema("first_name", "varchar", False),

            ColumnSchema("last_name", "varchar", False),

            ColumnSchema("email", "varchar", False),

            ColumnSchema(
                "phone",
                "varchar",
                True
            ),

            ColumnSchema(
                "gender",
                "varchar",
                True
            ),

            ColumnSchema(
                "birth_date",
                "date",
                True
            ),

            ColumnSchema(
                "city",
                "varchar",
                True
            ),

            ColumnSchema(
                "province",
                "varchar",
                True
            ),

            ColumnSchema(
                "country",
                "varchar",
                True
            ),

            ColumnSchema(
                "signup_date",
                "timestamp",
                False
            ),

            ColumnSchema(
                "segment",
                "varchar",
                True
            ),

            ColumnSchema(
                "loyalty_points",
                "integer",
                False
            ),

            ColumnSchema(
                "is_active",
                "boolean",
                False
            ),
        )
    ),

    TableSchema(
        name="products",
        description="Product catalog",
        columns=(

            ColumnSchema("product_id", "bigint", False),

            ColumnSchema("sku", "varchar", False),

            ColumnSchema("brand", "varchar", True),

            ColumnSchema("product_name", "varchar", False),

            ColumnSchema("category", "varchar", True),

            ColumnSchema("frame_shape", "varchar", True),

            ColumnSchema("frame_material", "varchar", True),

            ColumnSchema("frame_color", "varchar", True),

            ColumnSchema("gender_target", "varchar", True),

            ColumnSchema("size", "varchar", True),

            ColumnSchema("lens_type", "varchar", True),

            ColumnSchema("price", "numeric", False),

            ColumnSchema("cost", "numeric", False),

            ColumnSchema("rating", "numeric", True),

            ColumnSchema("review_count", "integer", False),

            ColumnSchema("popularity_score", "numeric", True),

            ColumnSchema("launch_date", "date", True),

            ColumnSchema("is_active", "boolean", False),

        )
    ),

    TableSchema(

        name="product_variants",

        description="Product variant information",

        columns=(

            ColumnSchema(
                "variant_id",
                "bigint",
                False
            ),

            ColumnSchema(
                "product_id",
                "bigint",
                False,
                foreign_key="products.product_id"
            ),

            ColumnSchema(
                "variant_sku",
                "varchar",
                False
            ),

            ColumnSchema(
                "color",
                "varchar",
                True
            ),

            ColumnSchema(
                "size",
                "varchar",
                True
            ),

            ColumnSchema(
                "stock_quantity",
                "integer",
                False
            ),

            ColumnSchema(
                "price_adjustment",
                "numeric",
                False
            ),

            ColumnSchema(
                "is_active",
                "boolean",
                False
            ),

        )
    ),

    TableSchema(

        name="orders",

        description="Customer orders",

        columns=(

            ColumnSchema(
                "order_id",
                "bigint",
                False
            ),

            ColumnSchema(
                "customer_id",
                "bigint",
                False,
                foreign_key="customers.customer_id"
            ),

            ColumnSchema(
                "order_date",
                "timestamp",
                False
            ),

            ColumnSchema(
                "status",
                "varchar",
                False
            ),

            ColumnSchema(
                "payment_method",
                "varchar",
                True
            ),

            ColumnSchema(
                "subtotal",
                "numeric",
                False
            ),

            ColumnSchema(
                "discount_amount",
                "numeric",
                False
            ),

            ColumnSchema(
                "shipping_amount",
                "numeric",
                False
            ),

            ColumnSchema(
                "total_amount",
                "numeric",
                False
            ),

            ColumnSchema(
                "shipping_city",
                "varchar",
                True
            ),

        )
    ),

    TableSchema(

        name="order_items",

        description="Products included in orders",

        columns=(

            ColumnSchema("order_item_id", "bigint", False),

            ColumnSchema(
                "order_id",
                "bigint",
                False,
                foreign_key="orders.order_id"
            ),

            ColumnSchema(
                "product_id",
                "bigint",
                False,
                foreign_key="products.product_id"
            ),

            ColumnSchema(
                "variant_id",
                "bigint",
                True,
                foreign_key="product_variants.variant_id"
            ),

            ColumnSchema(
                "quantity",
                "integer",
                False
            ),

            ColumnSchema(
                "unit_price",
                "numeric",
                False
            ),

            ColumnSchema(
                "discount_amount",
                "numeric",
                False
            ),

            ColumnSchema(
                "total_price",
                "numeric",
                False
            ),

        )
    ),

    TableSchema(

        name="inventory_events",

        description="Inventory movement history",

        columns=(

            ColumnSchema(
                "inventory_event_id",
                "bigint",
                False
            ),

            ColumnSchema(
                "variant_id",
                "bigint",
                False,
                foreign_key="product_variants.variant_id"
            ),

            ColumnSchema(
                "event_type",
                "varchar",
                False
            ),

            ColumnSchema(
                "quantity_change",
                "integer",
                False
            ),

            ColumnSchema(
                "reason",
                "varchar",
                True
            ),

            ColumnSchema(
                "event_time",
                "timestamp",
                False
            ),

        )
    ),

    TableSchema(

        name="reviews",

        description="Customer product reviews",

        columns=(

            ColumnSchema("review_id", "bigint", False),

            ColumnSchema(
                "customer_id",
                "bigint",
                False,
                foreign_key="customers.customer_id"
            ),

            ColumnSchema(
                "product_id",
                "bigint",
                False,
                foreign_key="products.product_id"
            ),

            ColumnSchema(
                "order_id",
                "bigint",
                True,
                foreign_key="orders.order_id"
            ),

            ColumnSchema(
                "rating",
                "integer",
                False
            ),

            ColumnSchema(
                "review_title",
                "varchar",
                True
            ),

            ColumnSchema(
                "review_text",
                "text",
                True
            ),

            ColumnSchema(
                "review_date",
                "timestamp",
                False
            ),

            ColumnSchema(
                "verified_purchase",
                "boolean",
                False
            ),

        )
    ),

    TableSchema(

        name="wishlist",

        description="Customer wishlist",

        columns=(

            ColumnSchema("wishlist_id", "bigint", False),

            ColumnSchema(
                "customer_id",
                "bigint",
                False,
                foreign_key="customers.customer_id"
            ),

            ColumnSchema(
                "product_id",
                "bigint",
                False,
                foreign_key="products.product_id"
            ),

            ColumnSchema(
                "added_at",
                "timestamp",
                False
            ),

        )
    ),

    TableSchema(

        name="carts",

        description="Shopping carts",

        columns=(

            ColumnSchema("cart_id", "bigint", False),

            ColumnSchema(
                "customer_id",
                "bigint",
                False,
                foreign_key="customers.customer_id"
            ),

            ColumnSchema(
                "status",
                "varchar",
                False
            ),

            ColumnSchema(
                "added_at",
                "timestamp",
                False
            ),

            ColumnSchema(
                "updated_at",
                "timestamp",
                False
            ),

        )
    ),

    TableSchema(
        name="cart_items",
        description="Items inside carts",
        columns=(
            ColumnSchema("cart_item_id", "bigint", False),

            ColumnSchema("cart_id", "bigint", False, foreign_key="carts.cart_id"),

            ColumnSchema("product_id", "bigint", False, foreign_key="products.product_id"),

            ColumnSchema("variant_id", "bigint", True, foreign_key="product_variants.variant_id"),

            ColumnSchema("quantity", "integer", False)
        )
    ),

    TableSchema(
        name="customer_events",
        description="Customer behavioral events",
        columns=(

            ColumnSchema("event_id", "bigint", False),

            ColumnSchema("customer_id", "bigint", False, foreign_key="customers.customer_id"),

            ColumnSchema("product_id", "bigint", True, foreign_key="products.product_id"),

            ColumnSchema("order_id", "bigint", True, foreign_key="orders.order_id"),

            ColumnSchema("event_type", "varchar", False),

            ColumnSchema("event_time", "timestamp", False),

            ColumnSchema("source", "varchar", True),

            ColumnSchema("metadata", "jsonb", True)
        )
    ),

)

