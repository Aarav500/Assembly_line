Edge Runtime Code Generation Service (Flask)

Endpoints:
- POST /codegen/edge
  body: {
    platform: "cloudflare-workers" | "vercel-edge",
    language?: "ts" | "js" = "ts",
    backend_url?: string = "http://localhost:5000",
    api_prefix?: string = "/api/",
    cors_origin?: string = "*",
    pass_through_headers?: string[] = ["authorization","content-type","accept","x-requested-with"]
  }

Response:
- { files: [{ path, content }] }

Dev:
- pip install -r requirements.txt
- FLASK_APP=app.py flask run

