from prometheus_client import Counter, Histogram, Gauge, Info

# HTTP metrics
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "Duration of HTTP requests in seconds",
    ["method", "endpoint", "status_code"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

IN_FLIGHT = Gauge(
    "http_in_flight_requests",
    "Current number of in-flight requests",
)

# Business metrics
ORDERS_CREATED = Counter(
    "business_orders_created_total",
    "Total number of orders created",
    ["status", "currency", "payment_method"],
)

ORDER_VALUE = Histogram(
    "business_order_value",
    "Distribution of order value",
    # Currency can be tracked via labels elsewhere; bucket in typical ranges
    buckets=[1, 5, 10, 20, 50, 100, 200, 500, 1000],
)

ORDER_PROCESSING_SECONDS = Histogram(
    "business_order_processing_seconds",
    "Time spent processing orders",
    ["status"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
)

ACTIVE_USERS = Gauge(
    "business_active_users",
    "Number of active users currently online",
)

INVENTORY_LEVEL = Gauge(
    "business_inventory_level",
    "Current inventory level for a product",
    ["product_id"],
)

QUEUE_DEPTH = Gauge(
    "business_queue_depth",
    "Depth of queued items for a named queue",
    ["queue_name"],
)

REVENUE_TOTAL = Counter(
    "business_revenue_total",
    "Total revenue collected",
    ["currency"],
)

# Static service metadata; set at app init
SERVICE_INFO = Info(
    "service_info",
    "Static service metadata (name, environment, version)",
)

