# Domain heuristics and mapping rules that connect detected functionality
# to monetization and packaging patterns.

FEATURE_RULES = {
    "real_time_collaboration": {
        "pricing_models": ["per_seat"],
        "plan_gates": ["seat_caps", "workspace_limits"],
        "value_metrics": ["seats", "active_users"],
        "plan_inclusions": {
            "free": ["basic_collaboration"],
            "pro": ["advanced_collaboration"],
            "business": ["multi_workspace", "role_based_access"],
            "enterprise": ["scim", "detailed_audit_logs"]
        },
        "rationale": "Collaboration value scales with team size; per-seat aligns monetization with value."
    },
    "api_access": {
        "pricing_models": ["usage_based", "tiered_quotas"],
        "value_metrics": ["api_calls"],
        "plan_gates": ["rate_limits", "keys_per_account"],
        "plan_inclusions": {
            "free": ["limited_api_access"],
            "pro": ["standard_api_access"],
            "business": ["higher_rate_limits"],
            "enterprise": ["custom_rate_limits", "dedicated_instances"]
        },
        "rationale": "API consumption maps cleanly to usage-based pricing with tiered quotas and overages."
    },
    "analytics_dashboard": {
        "pricing_models": ["tiered"],
        "value_metrics": ["reports", "dashboards"],
        "plan_inclusions": {
            "free": ["basic_analytics"],
            "pro": ["advanced_analytics"],
            "business": ["shared_dashboards"],
            "enterprise": ["governance_controls"]
        },
        "rationale": "Analytics sophistication is a strong plan differentiator."
    },
    "ai_generation": {
        "pricing_models": ["usage_based", "credit_based"],
        "value_metrics": ["ai_tokens", "gpu_minutes"],
        "plan_gates": ["ai_model_types", "daily_credit_caps"],
        "add_ons": ["AI Pack"],
        "rationale": "AI workloads have volatile costs; token or credit metering with add-ons controls margin."
    },
    "webhooks": {
        "pricing_models": ["tiered"],
        "plan_inclusions": {
            "pro": ["webhooks"],
            "business": ["replay_deadletter"],
            "enterprise": ["delivery_sla"]
        },
        "rationale": "Reliability features can be gated to higher plans."
    },
    "sso": {
        "pricing_models": ["per_seat", "enterprise_uplift"],
        "plan_gates": ["saml_sso"],
        "plan_inclusions": {
            "business": ["saml_sso"],
            "enterprise": ["scim", "just_in_time_provisioning"]
        },
        "rationale": "SSO is an enterprise signal and should drive higher tier packaging."
    },
    "role_based_access": {
        "pricing_models": ["per_seat"],
        "plan_inclusions": {
            "business": ["advanced_rbac"]
        },
        "rationale": "RBAC sophistication aligns with business/enterprise packaging."
    },
    "mobile_offline": {
        "pricing_models": ["tiered"],
        "plan_inclusions": {
            "pro": ["offline_mode"]
        },
        "rationale": "Offline support is a Pro-tier differentiator."
    },
    "white_label": {
        "pricing_models": ["enterprise_uplift"],
        "add_ons": ["White Label"],
        "rationale": "White-labeling is high willingness-to-pay for enterprise and partners."
    },
    "on_prem": {
        "pricing_models": ["annual_license"],
        "plan_inclusions": {
            "enterprise": ["on_prem"]
        },
        "rationale": "On-prem delivery model priced as annual enterprise license."
    },
    "audit_logs": {
        "pricing_models": ["tiered"],
        "plan_inclusions": {
            "business": ["audit_logs"],
            "enterprise": ["long_retention_audit"]
        },
        "rationale": "Audit and retention are enterprise controls."
    },
    "encryption_kms": {
        "pricing_models": ["enterprise_uplift"],
        "plan_inclusions": {
            "enterprise": ["customer_managed_keys"]
        },
        "rationale": "CMK/KMS typically reserved for enterprise contracts."
    },
    "marketplace": {
        "pricing_models": ["take_rate", "listing_fees"],
        "add_ons": ["Partner Program"],
        "rationale": "Two-sided marketplaces monetize via take rate and partner tiers."
    }
}

DEFAULT_PLAN_SHELLS = [
    {"name": "Free", "internal_key": "free"},
    {"name": "Pro", "internal_key": "pro"},
    {"name": "Business", "internal_key": "business"},
    {"name": "Enterprise", "internal_key": "enterprise"}
]

SUPPORTED_COST_KEYS = [
    "api_call",
    "ai_token",
    "gpu_minute",
    "storage_gb_month",
    "bandwidth_gb"
]

DEFAULT_COGS = {
    "api_call": 0.0015,
    "ai_token": 0.000002,
    "gpu_minute": 0.04,
    "storage_gb_month": 0.02,
    "bandwidth_gb": 0.03
}

MARGIN_TARGET_DEFAULT = 0.8

# Fallback usage expectations per plan if not provided by client.
DEFAULT_USAGE_BY_PLAN = {
    "free": {
        "api_calls": 1000,
        "ai_tokens": 50000,
        "gpu_minutes": 0,
        "storage_gb": 1
    },
    "pro": {
        "api_calls": 10000,
        "ai_tokens": 500000,
        "gpu_minutes": 30,
        "storage_gb": 10
    },
    "business": {
        "api_calls": 100000,
        "ai_tokens": 3000000,
        "gpu_minutes": 300,
        "storage_gb": 100
    },
    "enterprise": {
        "api_calls": 1000000,
        "ai_tokens": 20000000,
        "gpu_minutes": 3000,
        "storage_gb": 1000
    }
}

# Add-on templates keyed by concept names commonly referenced by rules.
ADD_ON_LIBRARY = {
    "AI Pack": {
        "description": "Prepaid AI tokens/credits with discounted overage rates.",
        "value_metric": "ai_tokens",
        "bundles": [
            {"name": "Starter AI", "included_tokens": 200000, "discount": 0.1},
            {"name": "Growth AI", "included_tokens": 2000000, "discount": 0.2},
            {"name": "Scale AI", "included_tokens": 20000000, "discount": 0.3}
        ]
    },
    "White Label": {
        "description": "Remove branding, custom domain, and theme controls.",
        "value_metric": None,
        "bundles": [
            {"name": "White Label", "flat_monthly": True}
        ]
    },
    "Partner Program": {
        "description": "Marketplace/partner listing, co-marketing benefits.",
        "value_metric": None,
        "bundles": [
            {"name": "Partner Silver"},
            {"name": "Partner Gold"}
        ]
    }
}

