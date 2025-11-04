import random
import string
from datetime import datetime, timedelta, date
from faker import Faker
import rstr


def _safe_int(v, default=None):
    try:
        return int(v)
    except Exception:
        return default


class SafeDict(dict):
    def __missing__(self, key):
        return ""


class DataGenerator:
    def __init__(self, seed=None, locale=None):
        # locale can be 'en_US' or ["en_US", "de_DE"]
        self.faker = Faker(locale or ["en_US"])  # Faker handles list of locales
        if seed is not None:
            try:
                iseed = int(seed)
            except Exception:
                # hash string seeds deterministically
                iseed = abs(hash(str(seed))) % (2**32)
            random.seed(iseed)
            Faker.seed(iseed)
            self.faker.seed_instance(iseed)
        self.unique_trackers = {}
        self.sequence_counters = {}

    def generate(self, schema: dict, count: int | None = None):
        norm = self._normalize_schema(schema)
        n = count if count is not None else norm.get("count", 1)
        if n < 1:
            n = 1
        records = []
        # reset uniqueness for each batch
        self.unique_trackers = {}
        for i in range(n):
            rec = self._generate_record(norm.get("fields", {}))
            records.append(rec)
        return records

    def _normalize_schema(self, schema: dict) -> dict:
        # Support two styles: custom {fields: {...}, count?} OR JSON Schema with type object/properties
        if "fields" in schema:
            fields = schema.get("fields", {})
            count = _safe_int(schema.get("count"))
            return {"fields": fields, "count": count or 1}
        # JSON Schema style
        if schema.get("type") == "object" and isinstance(schema.get("properties"), dict):
            fields = {}
            for name, spec in schema["properties"].items():
                fields[name] = self._normalize_field_spec(name, spec)
            return {"fields": fields, "count": _safe_int(schema.get("count")) or 1}
        # If someone passes direct mapping name->spec treat as fields
        if all(isinstance(v, (dict, str)) for v in schema.values()):
            return {"fields": schema, "count": 1}
        raise ValueError("Unrecognized schema format. Provide {fields:{...}} or JSON Schema with type=object.")

    def _normalize_field_spec(self, name, spec):
        # If spec is a string, turn into {type: spec}
        if isinstance(spec, str):
            return {"type": spec}
        if not isinstance(spec, dict):
            # guess by name
            return self._guess_spec_from_name(name)
        if "type" not in spec:
            # attempt to infer from JSON Schema facets
            inferred = spec.copy()
            guessed = self._guess_spec_from_name(name)
            if guessed:
                inferred.setdefault("type", guessed.get("type"))
                for k, v in guessed.items():
                    inferred.setdefault(k, v)
            inferred.setdefault("type", "string")
            return inferred
        return spec

    def _guess_spec_from_name(self, name):
        n = (name or "").lower()
        # id/ids => sequence integer
        if n == "id" or n.endswith("_id"):
            return {"type": "integer", "sequence": True, "start": 1}
        if "email" in n:
            return {"type": "string", "format": "email"}
        if "first" in n and "name" in n:
            return {"faker": "first_name"}
        if "last" in n and "name" in n:
            return {"faker": "last_name"}
        if n.endswith("name") or n == "name":
            return {"faker": "name"}
        if "phone" in n or "mobile" in n or "tel" in n:
            return {"faker": "phone_number"}
        if "address" in n and not n.endswith("email_address"):
            return {"faker": "address"}
        if n == "city":
            return {"faker": "city"}
        if "state" in n:
            return {"faker": "state"}
        if "zip" in n or "postal" in n:
            return {"faker": "postcode"}
        if "country" in n:
            return {"faker": "country"}
        if n == "url" or "url" in n:
            return {"format": "url", "type": "string"}
        if "ip" in n:
            return {"format": "ipv4", "type": "string"}
        if "uuid" in n or n == "guid":
            return {"format": "uuid", "type": "string"}
        if "company" in n:
            return {"faker": "company"}
        if "job" in n or ("title" in n and "job" in n):
            return {"faker": "job"}
        if n in {"created_at", "updated_at", "timestamp"} or "_at" in n:
            return {"type": "datetime"}
        if n in {"date", "birthdate", "dob"}:
            return {"type": "date"}
        if n in {"lat", "latitude"}:
            return {"type": "latitude"}
        if n in {"lng", "lon", "longitude"}:
            return {"type": "longitude"}
        if any(k in n for k in ["price", "amount", "total", "cost"]):
            return {"type": "number", "min": 1, "max": 1000, "decimals": 2}
        # default to string
        return {"type": "string"}

    def _generate_record(self, fields_spec: dict):
        record = {}
        templates = []  # collect fields with template to render after first pass
        # First pass: generate non-template values
        for fname, fspec in fields_spec.items():
            spec = self._normalize_field_spec(fname, fspec)
            if isinstance(spec, dict) and "template" in spec:
                templates.append((fname, spec))
                continue
            record[fname] = self._generate_value(fname, spec, record)
        # Second pass: render templates
        for fname, spec in templates:
            tpl = spec.get("template", "")
            value = tpl.format_map(SafeDict(record))
            record[fname] = value
        return record

    def _maybe_null(self, spec):
        if spec is None:
            return False
        if isinstance(spec.get("nullable"), (int, float)):
            p = float(spec.get("nullable"))
            return random.random() < max(0.0, min(1.0, p))
        if spec.get("nullable") is True:
            # default 10% chance
            return random.random() < 0.1
        return False

    def _apply_unique(self, field_name, value, generator_fn, max_attempts=100):
        tracker = self.unique_trackers.setdefault(field_name, set())
        if value is None:
            # generate until non-null unique
            attempts = 0
            while attempts < max_attempts:
                v = generator_fn()
                if v not in tracker:
                    tracker.add(v)
                    return v
                attempts += 1
            raise ValueError(f"Unable to generate unique value for field '{field_name}' after {max_attempts} attempts")
        if value not in tracker:
            tracker.add(value)
            return value
        # try regenerate
        attempts = 0
        while attempts < max_attempts:
            v = generator_fn()
            if v not in tracker:
                tracker.add(v)
                return v
            attempts += 1
        raise ValueError(f"Unable to generate unique value for field '{field_name}' after {max_attempts} attempts")

    def _generate_value(self, field_name: str, spec: dict | str, context: dict):
        # spec can be shorthand string
        if isinstance(spec, str):
            spec = {"type": spec}
        if spec is None:
            spec = {"type": "string"}

        # null chance
        if self._maybe_null(spec):
            return None

        # enum support
        if isinstance(spec.get("enum"), list) and len(spec["enum"]) > 0:
            def gen_choice():
                return random.choice(spec["enum"])  # noqa: S311
            value = gen_choice()
            if spec.get("unique"):
                return self._apply_unique(field_name, value, gen_choice)
            return value

        # faker direct
        if "faker" in spec:
            provider = spec.get("faker")
            args = spec.get("args") or []
            kwargs = spec.get("kwargs") or {}
            def gen_faker():
                f = getattr(self.faker, provider, None)
                if not callable(f):
                    raise ValueError(f"Unknown faker provider '{provider}' for field '{field_name}'")
                return f(*args, **kwargs)
            value = gen_faker()
            if spec.get("unique"):
                return self._apply_unique(field_name, value, gen_faker)
            return value

        # pattern (regex)
        if spec.get("pattern"):
            pattern = spec["pattern"]
            def gen_regex():
                return rstr.xeger(pattern)
            value = gen_regex()
            if spec.get("unique"):
                return self._apply_unique(field_name, value, gen_regex)
            return value

        # arrays
        if spec.get("type") == "array":
            items_spec = spec.get("items", {"type": "string"})
            if "length" in spec:
                length = max(0, int(spec["length"]))
            else:
                min_items = int(spec.get("minItems", spec.get("min_items", 0)))
                max_items = int(spec.get("maxItems", spec.get("max_items", min_items + 5)))
                if max_items < min_items:
                    max_items = min_items
                length = random.randint(min_items, max_items)
            arr = []
            for _ in range(length):
                arr.append(self._generate_value(field_name + "[]", items_spec, context))
            return arr

        # object
        if spec.get("type") == "object":
            props = spec.get("properties", {})
            return self._generate_record(props)

        # sequence
        if spec.get("sequence"):
            start = _safe_int(spec.get("start"), 1)
            step = _safe_int(spec.get("step"), 1)
            cur = self.sequence_counters.get(field_name, start - step)
            cur += step
            self.sequence_counters[field_name] = cur
            value = cur
            if spec.get("unique"):
                # sequence by design unique across batch
                self.unique_trackers.setdefault(field_name, set()).add(value)
            return value

        ftype = spec.get("type", "string")
        # numbers
        if ftype in ("integer", "number", "float"):
            min_v = spec.get("minimum", spec.get("min", 0))
            max_v = spec.get("maximum", spec.get("max", 1000))
            if ftype == "integer":
                def gen_int():
                    return random.randint(int(min_v), int(max_v))
                value = gen_int()
                if spec.get("unique"):
                    return self._apply_unique(field_name, value, gen_int)
                return value
            else:
                decimals = _safe_int(spec.get("decimals"), None)
                def gen_float():
                    v = random.random() * (float(max_v) - float(min_v)) + float(min_v)
                    if decimals is not None:
                        return round(v, decimals)
                    return v
                value = gen_float()
                if spec.get("unique"):
                    return self._apply_unique(field_name, value, gen_float)
                return value

        # boolean
        if ftype == "boolean":
            true_p = spec.get("true_probability")
            if isinstance(true_p, (int, float)):
                value = random.random() < max(0.0, min(1.0, float(true_p)))
            else:
                value = random.choice([True, False])
            if spec.get("unique"):
                return self._apply_unique(field_name, value, lambda: random.choice([True, False]))
            return value

        # date/datetime special
        if ftype in ("date", "datetime"):
            start = spec.get("start")
            end = spec.get("end")
            if isinstance(start, str):
                try:
                    start_dt = datetime.fromisoformat(start)
                except Exception:
                    start_dt = datetime.now() - timedelta(days=365 * 5)
            else:
                start_dt = datetime.now() - timedelta(days=365 * 5)
            if isinstance(end, str):
                try:
                    end_dt = datetime.fromisoformat(end)
                except Exception:
                    end_dt = datetime.now()
            else:
                end_dt = datetime.now()
            if end_dt < start_dt:
                end_dt = start_dt
            delta = end_dt - start_dt
            seconds = delta.total_seconds()
            rsec = random.uniform(0, seconds)
            dt = start_dt + timedelta(seconds=rsec)
            if ftype == "date":
                value = dt.date().isoformat()
            else:
                value = dt.isoformat()
            if spec.get("unique"):
                return self._apply_unique(field_name, value, lambda: dt.isoformat())
            return value

        # latitude/longitude
        if ftype == "latitude":
            return float(self.faker.latitude())
        if ftype == "longitude":
            return float(self.faker.longitude())

        # string and formats
        if ftype == "string" or ftype is None:
            fmt = spec.get("format")
            min_len = spec.get("minLength", spec.get("min_length", 5))
            max_len = spec.get("maxLength", spec.get("max_length", 20))
            if max_len < min_len:
                max_len = min_len
            def gen_str_default():
                length = random.randint(int(min_len), int(max_len))
                return self.faker.pystr(min_chars=length, max_chars=length)

            if fmt == "email":
                def gen_email():
                    return self.faker.unique.email() if spec.get("unique") else self.faker.email()
                value = gen_email()
                if spec.get("unique"):
                    # using faker.unique ensures uniqueness locally but we also track
                    return self._apply_unique(field_name, value, gen_email)
                return value
            if fmt == "uuid":
                def gen_uuid():
                    return str(self.faker.uuid4())
                value = gen_uuid()
                if spec.get("unique"):
                    return self._apply_unique(field_name, value, gen_uuid)
                return value
            if fmt == "ipv4":
                def gen_ipv4():
                    return self.faker.ipv4()
                value = gen_ipv4()
                if spec.get("unique"):
                    return self._apply_unique(field_name, value, gen_ipv4)
                return value
            if fmt in ("url", "uri"):
                def gen_url():
                    return self.faker.url()
                value = gen_url()
                if spec.get("unique"):
                    return self._apply_unique(field_name, value, gen_url)
                return value
            if fmt in ("date-time", "datetime"):
                def gen_dt():
                    return self.faker.date_time_between(start_date='-5y', end_date='now').isoformat()
                value = gen_dt()
                if spec.get("unique"):
                    return self._apply_unique(field_name, value, gen_dt)
                return value
            if fmt == "date":
                def gen_d():
                    return self.faker.date_between(start_date='-30y', end_date='today').isoformat()
                value = gen_d()
                if spec.get("unique"):
                    return self._apply_unique(field_name, value, gen_d)
                return value

            # default string
            value = gen_str_default()
            if spec.get("unique"):
                return self._apply_unique(field_name, value, gen_str_default)
            return value

        # fallback: try faker-by-name guess
        guessed = self._guess_spec_from_name(field_name)
        return self._generate_value(field_name, guessed, context)

