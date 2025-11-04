# Flask Auto-Deploy Application

## Local Development

```bash
pip install -r requirements.txt
python app.py
```

## Run Tests

```bash
pytest tests/
```

## Deploy to Oracle VM

```bash
export REMOTE_HOST=your-oracle-vm-ip
export REMOTE_USER=opc
export REMOTE_DIR=/home/opc/flask-app
chmod +x deploy.sh
./deploy.sh
```

## Endpoints

- GET / - Home endpoint
- GET /health - Health check
- GET /api/info - App information

