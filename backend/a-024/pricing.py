import json
from decimal import Decimal
from typing import Optional, List


class ModelPrice:
    def __init__(self, model_id: str, currency: str, input_per_million: Decimal, output_per_million: Decimal, display_name: Optional[str] = None, vendor: Optional[str] = None):
        self.model_id = model_id
        self.display_name = display_name or model_id
        self.currency = currency
        self.input_per_million = Decimal(str(input_per_million))
        self.output_per_million = Decimal(str(output_per_million))
        self.vendor = vendor

    def cost_for_input_tokens(self, tokens: int) -> Decimal:
        # price is per 1,000,000 tokens
        return (Decimal(tokens) / Decimal(1_000_000)) * self.input_per_million

    def cost_for_output_tokens(self, tokens: int) -> Decimal:
        return (Decimal(tokens) / Decimal(1_000_000)) * self.output_per_million

    def to_dict(self):
        return {
            "model": self.model_id,
            "display_name": self.display_name,
            "vendor": self.vendor,
            "currency": self.currency,
            "price_per_million": {
                "input": float(self.input_per_million),
                "output": float(self.output_per_million),
            },
        }


class PricingCatalog:
    def __init__(self, models):
        self._models = {m.model_id: m for m in models}

    def get(self, model_id: str) -> Optional[ModelPrice]:
        return self._models.get(model_id)

    def all_models(self) -> List[ModelPrice]:
        return list(self._models.values())

    def __len__(self):
        return len(self._models)

    @staticmethod
    def from_json(path: str) -> "PricingCatalog":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        models = []
        for row in data.get("models", []):
            models.append(
                ModelPrice(
                    model_id=row["model"],
                    display_name=row.get("display_name") or row.get("name"),
                    vendor=row.get("vendor"),
                    currency=row.get("currency", "USD"),
                    input_per_million=Decimal(str(row.get("price_per_million", {}).get("input", 0))),
                    output_per_million=Decimal(str(row.get("price_per_million", {}).get("output", 0))),
                )
            )
        return PricingCatalog(models)

