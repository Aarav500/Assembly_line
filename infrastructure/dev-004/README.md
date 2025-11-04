api-client-sdk-generation-multiple-languages

This tool generates API client SDKs for Python, TypeScript, and Go from an OpenAPI 3.x specification. It includes basic authentication support (API Key, HTTP Bearer, HTTP Basic) and error handling.

Quick start:
- Install: pip install -e .
- Generate: sdkgen --spec example/openapi.yaml --out dist --languages python,typescript,go

Outputs:
- dist/python/client.py
- dist/typescript/client.ts and package.json
- dist/go/client/client.go and go.mod

