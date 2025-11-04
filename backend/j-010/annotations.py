from functools import wraps


def endpoint_doc(
    summary=None,
    description=None,
    params=None,  # path params: {name: {type, required, description, example}}
    query=None,   # query params
    body=None,    # request body schema (JSON schema-like)
    responses=None,  # {status: {description, body}}
    examples=None,   # optional manual examples
    tags=None,
):
    def decorator(fn):
        meta = {
            "summary": summary,
            "description": description,
            "params": params or {},
            "query": query or {},
            "body": body or {},
            "responses": responses or {},
            "examples": examples or {},
            "tags": tags or [],
        }
        setattr(fn, "_endpoint_doc", meta)
        return fn
    return decorator



if __name__ == '__main__':
    pass
