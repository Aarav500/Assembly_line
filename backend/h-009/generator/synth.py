import math
import random
import re
import uuid
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dateutil.parser import parse as parse_date
from faker import Faker

from .utils import coerce_bool, to_probability, weighted_choice, safe_eval_template


TYPE_ALIASES = {
    "int": "integer",
    "float": "float",
    "double": "float",
    "str": "string",
}

FAKER_MAP = {
    "name": "name",
    "first_name": "first_name",
    "last_name": "last_name",
    "email": "email",
    "phone": "phone_number",
    "address": "address",
    "city": "city",
    "state": "state",
    "zip": "postcode",
    "country": "country",
    "company": "company",
    "job": "job",
    "iban": "iban",
    "credit_card": "credit_card_number",
}


def _parse_date(value: Any, default: Optional[date] = None) -> date:
    if value is None:
        return default or date.today()
    if isinstance(value, (date, datetime)):
        return value.date() if isinstance(value, datetime) else value
    return parse_date(str(value)).date()


def _parse_datetime(value: Any, default: Optional[datetime] = None) -> datetime:
    if value is None:
        return default or datetime.utcnow()
    if isinstance(value, datetime):
        return value
    dt = parse_date(str(value))
    if isinstance(dt, date) and not isinstance(dt, datetime):
        return datetime(dt.year, dt.month, dt.day)
    return dt


class SyntheticDataGenerator:
    def __init__(self, locale: str = "en_US"):
        self.faker = Faker(locale)
        # Make Faker threadsafe when used in concurrent contexts
        Faker.seed()

    def _gen_integer(self, n: int, col: Dict) -> np.ndarray:
        mn = col.get("min", 0)
        mx = col.get("max", 1000)
        if mn > mx:
            mn, mx = mx, mn
        unique = coerce_bool(col.get("unique", False))
        if unique and (mx - mn + 1) >= n:
            return np.random.choice(np.arange(mn, mx + 1), size=n, replace=False)
        dist = col.get("distribution")
        if isinstance(dist, dict) and dist.get("name") == "normal":
            mean = float(dist.get("mean", (mn + mx) / 2))
            std = float(dist.get("std", max(1.0, (mx - mn) / 6)))
            vals = np.clip(np.random.normal(mean, std, size=n), mn, mx)
            return np.floor(vals).astype(int)
        return np.random.randint(mn, mx + 1, size=n)

    def _gen_float(self, n: int, col: Dict) -> np.ndarray:
        mn = float(col.get("min", 0.0))
        mx = float(col.get("max", 1.0))
        if mn > mx:
            mn, mx = mx, mn
        dist = col.get("distribution")
        if isinstance(dist, dict) and dist.get("name") == "normal":
            mean = float(dist.get("mean", (mn + mx) / 2))
            std = float(dist.get("std", max(1e-6, (mx - mn) / 6)))
            vals = np.clip(np.random.normal(mean, std, size=n), mn, mx)
            return vals.astype(float)
        return np.random.uniform(mn, mx, size=n)

    def _gen_boolean(self, n: int, col: Dict) -> np.ndarray:
        p_true = to_probability(col.get("p_true", 0.5))
        return np.random.rand(n) < p_true

    def _gen_string(self, n: int, col: Dict) -> List[str]:
        length = int(col.get("length", 12))
        alphabet = col.get("alphabet", "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
        return ["".join(random.choices(alphabet, k=length)) for _ in range(n)]

    def _gen_uuid(self, n: int) -> List[str]:
        return [str(uuid.uuid4()) for _ in range(n)]

    def _gen_date(self, n: int, col: Dict) -> List[str]:
        start = _parse_date(col.get("start_date"), default=date(2000, 1, 1))
        end = _parse_date(col.get("end_date"), default=date.today())
        if start > end:
            start, end = end, start
        days = (end - start).days + 1
        choices = np.random.randint(0, days, size=n)
        return [(start + timedelta(days=int(x))).isoformat() for x in choices]

    def _gen_datetime(self, n: int, col: Dict) -> List[str]:
        start = _parse_datetime(col.get("start"), default=datetime(2000, 1, 1))
        end = _parse_datetime(col.get("end"), default=datetime.utcnow())
        if start > end:
            start, end = end, start
        total_seconds = int((end - start).total_seconds()) + 1
        choices = np.random.randint(0, max(1, total_seconds), size=n)
        return [(start + timedelta(seconds=int(x))).isoformat() for x in choices]

    def _gen_categorical(self, n: int, col: Dict) -> List[Any]:
        choices = col.get("choices") or col.get("categories")
        if not isinstance(choices, list) or len(choices) == 0:
            raise ValueError(f"categorical column '{col.get('name')}' requires non-empty 'choices'")
        probs = col.get("p") or col.get("probabilities")
        if probs is not None:
            if len(probs) != len(choices):
                raise ValueError("Length of probabilities must match choices")
            probs = np.array(probs, dtype=float)
            probs = probs / probs.sum()
        else:
            probs = np.array([1 / len(choices)] * len(choices))
        return list(np.random.choice(choices, size=n, p=probs))

    def _gen_email(self, n: int, col: Dict) -> List[str]:
        domains = None
        constraints = col.get("constraints") or {}
        if isinstance(constraints, dict):
            domains = constraints.get("domain_whitelist")
        emails = []
        for _ in range(n):
            if domains:
                user = self.faker.user_name()
                domain = random.choice(domains)
                emails.append(f"{user}@{domain}")
            else:
                emails.append(self.faker.email())
        return emails

    def _gen_faker(self, n: int, provider_name: str) -> List[Any]:
        out = []
        for _ in range(n):
            provider = getattr(self.faker, provider_name)
            out.append(provider())
        return out

    def _apply_nullability(self, series: List[Any], p_null: float) -> List[Any]:
        if p_null <= 0:
            return series
        mask = np.random.rand(len(series)) < p_null
        return [None if m else v for v, m in zip(series, mask)]

    def _apply_masking(self, series: List[Any], col: Dict) -> List[Any]:
        privacy = col.get("privacy") or {}
        if not isinstance(privacy, dict):
            return series
        if privacy.get("redact"):
            token = privacy.get("token", "REDACTED")
            return [token for _ in series]
        mask = privacy.get("mask")
        if mask == "last4":
            masked = []
            for v in series:
                s = str(v) if v is not None else ""
                if len(s) <= 4:
                    masked.append(s)
                else:
                    masked.append("*" * (len(s) - 4) + s[-4:])
            return masked
        return series

    def _generate_base_columns(self, n: int, schema: List[Dict]) -> Tuple[pd.DataFrame, Dict[str, Dict]]:
        data = {}
        templates = {}
        meta = {}
        for col in schema:
            name = col.get("name")
            if not name:
                raise ValueError("All columns must include a 'name'")
            ctype = (col.get("type") or "string").lower()
            ctype = TYPE_ALIASES.get(ctype, ctype)

            # Template columns are evaluated after base generation
            template = col.get("template")
            if isinstance(template, str) and "{" in template and "}" in template:
                templates[name] = template
                data[name] = [None] * n
                meta[name] = {"type": "template", "source": template}
                continue

            # Column generation paths
            if ctype == "integer":
                series = list(map(int, self._gen_integer(n, col)))
            elif ctype == "float":
                series = list(map(float, self._gen_float(n, col)))
            elif ctype == "boolean":
                series = list(map(bool, self._gen_boolean(n, col)))
            elif ctype == "uuid":
                series = self._gen_uuid(n)
            elif ctype == "date":
                series = self._gen_date(n, col)
            elif ctype == "datetime":
                series = self._gen_datetime(n, col)
            elif ctype == "categorical":
                series = self._gen_categorical(n, col)
            elif ctype == "email":
                series = self._gen_email(n, col)
            elif ctype in FAKER_MAP:
                series = self._gen_faker(n, FAKER_MAP[ctype])
            elif ctype == "string":
                series = self._gen_string(n, col)
            else:
                # fallback to faker if available
                if ctype in FAKER_MAP:
                    series = self._gen_faker(n, FAKER_MAP[ctype])
                else:
                    # default string
                    series = self._gen_string(n, col)

            # Uniqueness at column level
            if coerce_bool(col.get("unique", False)):
                unique_count = len(set(series))
                if unique_count < n:
                    # Try to fix by regenerating with uuid suffix
                    seen = set()
                    fixed = []
                    for v in series:
                        new_v = v
                        while new_v in seen:
                            new_v = f"{v}-{uuid.uuid4().hex[:8]}"
                        seen.add(new_v)
                        fixed.append(new_v)
                    series = fixed

            # Nullability
            p_null = to_probability(col.get("p_null", 0.0))
            series = self._apply_nullability(series, p_null)

            # Column-level privacy masking
            series = self._apply_masking(series, col)

            data[name] = series
            meta[name] = {"type": ctype}

        return pd.DataFrame(data), {"columns": meta}

    def _evaluate_templates(self, df: pd.DataFrame, templates: Dict[str, str]) -> pd.DataFrame:
        for name, tpl in templates.items():
            df[name] = [safe_eval_template(tpl, row) for _, row in df.iterrows()]
        return df

    def generate(self, rows: int, schema: List[Dict], seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
            Faker.seed(seed)
        df, meta = self._generate_base_columns(rows, schema)

        # Evaluate templates if any
        templates = {col.get("name"): col.get("template") for col in schema if isinstance(col.get("template"), str)}
        templates = {k: v for k, v in templates.items() if k in df.columns and v}
        if templates:
            df = self._evaluate_templates(df, templates)

        return df, meta

