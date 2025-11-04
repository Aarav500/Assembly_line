from prometheus_client import Gauge

# Currency label is included for grouping; can be omitted if needed
cost_total_gauge = Gauge("cost_estimated_total", "Total estimated cost over window", ["currency"])
cost_breakdown_gauge = Gauge(
    "cost_breakdown_total", "Estimated cost by resource over window", ["resource", "currency"]
)
cost_namespace_gauge = Gauge(
    "cost_breakdown_namespace", "Estimated cost by resource per namespace over window", ["namespace", "resource", "currency"]
)

budget_amount_gauge = Gauge("budget_amount", "Configured budget for the month", ["currency"])
budget_spent_gauge = Gauge("budget_spent_mtd", "Estimated month-to-date spend", ["currency"])
budget_remaining_gauge = Gauge("budget_remaining", "Remaining budget for the month", ["currency"])
budget_alert_gauge = Gauge("budget_alert", "1 if budget threshold exceeded", ["level"])  # level=warn|crit
budget_forecast_gauge = Gauge("budget_forecast_end_of_month", "Forecasted end-of-month spend", ["currency"])

recommended_savings_gauge = Gauge("recommended_savings_total", "Total potential savings identified", ["currency"])
recommended_savings_breakdown_gauge = Gauge(
    "recommended_savings_breakdown", "Potential savings by resource", ["resource", "currency"]
)
underutilized_count_gauge = Gauge(
    "underutilized_resources_count", "Count of underutilized containers/pods", ["kind"]
)
overutilized_count_gauge = Gauge(
    "overutilized_resources_count", "Count of overutilized containers/pods", ["kind"]
)

