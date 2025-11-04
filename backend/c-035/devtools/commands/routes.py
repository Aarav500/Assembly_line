from typing import Iterable

from devtools import dev_command
from app import create_app


def _iter_routes(app) -> Iterable[tuple[str, str, str]]:
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: (str(r), r.endpoint)):
        methods = ",".join(sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"}))
        yield (methods, str(rule), rule.endpoint)


@dev_command(help="List registered Flask routes")
def routes():
    app = create_app()
    rows = list(_iter_routes(app))
    if not rows:
        print("No routes registered.")
        return
    width_m = max(len(r[0]) for r in rows)
    width_p = max(len(r[1]) for r in rows)
    header = f"{ 'METHODS'.ljust(width_m) }  { 'PATH'.ljust(width_p) }  ENDPOINT"
    print(header)
    print("-" * len(header))
    for methods, path, endpoint in rows:
        print(f"{methods.ljust(width_m)}  {path.ljust(width_p)}  {endpoint}")

