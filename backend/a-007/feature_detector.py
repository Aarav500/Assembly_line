from flask import Flask


def _rule_evidence(rule):
    try:
        return f"route:{rule.rule} methods:{','.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))} endpoint:{rule.endpoint}"
    except (AttributeError, TypeError) as e:
        return f"route:unknown error:{str(e)}"


def detect_features(app: Flask):
    try:
        # Prepare feature report
        features = {
            "auth": {"implemented": False, "evidence": []},
            "payments": {"implemented": False, "evidence": []},
            "search": {"implemented": False, "evidence": []},
            "upload": {"implemented": False, "evidence": []},
            "rate_limits": {"implemented": False, "evidence": []},
            "caching": {"implemented": False, "evidence": []},
        }

        # 1) Blueprints and routes evidence
        try:
            bp_names = set(app.blueprints.keys())
        except (AttributeError, TypeError):
            bp_names = set()

        # map endpoints for function introspection
        try:
            endpoint_to_view = dict(app.view_functions)
        except (AttributeError, TypeError):
            endpoint_to_view = {}

        try:
            for rule in app.url_map.iter_rules():
                try:
                    rule_info = _rule_evidence(rule)
                    endpoint = rule.endpoint
                    view_fn = endpoint_to_view.get(endpoint)
                    rule_str = rule.rule

                    # Auth detection
                    try:
                        if ("auth" in endpoint) or any(x in rule_str for x in ["/login", "/logout", "/me"]):
                            features["auth"]["implemented"] = True
                            features["auth"]["evidence"].append(rule_info)
                    except (TypeError, AttributeError):
                        pass

                    try:
                        if view_fn is not None and getattr(view_fn, "__requires_auth__", False):
                            features["auth"]["implemented"] = True
                            features["auth"]["evidence"].append(f"protected-endpoint:{endpoint}")
                    except (AttributeError, TypeError):
                        pass

                    # Payments detection
                    try:
                        if ("payments" in endpoint) or ("/payments" in rule_str):
                            features["payments"]["implemented"] = True
                            features["payments"]["evidence"].append(rule_info)
                    except (TypeError, AttributeError):
                        pass

                    # Search detection
                    try:
                        if "/search" in rule_str or endpoint.startswith("search"):
                            features["search"]["implemented"] = True
                            features["search"]["evidence"].append(rule_info)
                    except (TypeError, AttributeError):
                        pass

                    # Upload detection
                    try:
                        if "/upload" in rule_str or endpoint.startswith("upload"):
                            features["upload"]["implemented"] = True
                            features["upload"]["evidence"].append(rule_info)
                    except (TypeError, AttributeError):
                        pass

                    # Caching detection by decorator tag on view
                    try:
                        if view_fn is not None and getattr(view_fn, "__uses_caching__", False):
                            features["caching"]["implemented"] = True
                            features["caching"]["evidence"].append(f"cached-endpoint:{endpoint}")
                    except (AttributeError, TypeError):
                        pass
                except Exception:
                    continue
        except (AttributeError, TypeError):
            pass

        # 2) Blueprint names as evidence
        try:
            for name in ["auth", "payments", "search", "upload"]:
                try:
                    if name in bp_names:
                        key = "rate_limits" if name == "rate_limits" else name
                        if key in features:
                            features[key]["implemented"] = True or features[key]["implemented"]
                            features[key]["evidence"].append(f"blueprint:{name}")
                except (KeyError, TypeError):
                    continue
        except Exception:
            pass

        # 3) Extensions for rate limits and caching
        try:
            exts = getattr(app, "extensions", {}) or {}
        except (AttributeError, TypeError):
            exts = {}

        # Rate limits
        try:
            if "rate_limiter" in exts:
                rl = exts["rate_limiter"]
                features["rate_limits"]["implemented"] = True
                features["rate_limits"]["evidence"].append(f"extension:rate_limiter")
        except (KeyError, TypeError):
            pass

        # Caching
        try:
            if "simple_cache" in exts:
                cache = exts["simple_cache"]
                features["caching"]["implemented"] = True
                features["caching"]["evidence"].append(f"extension:simple_cache")
        except (KeyError, TypeError):
            pass

        return features
    except Exception as e:
        # Return empty features on catastrophic failure
        return {
            "auth": {"implemented": False, "evidence": [f"error:{str(e)}"]},
            "payments": {"implemented": False, "evidence": []},
            "search": {"implemented": False, "evidence": []},
            "upload": {"implemented": False, "evidence": []},
            "rate_limits": {"implemented": False, "evidence": []},
            "caching": {"implemented": False, "evidence": []},
        }
