# Unified App - Simple Deployment

## Architecture
- **1 Backend Service**: Dynamically loads all 437 modules on-demand
- **1 PostgreSQL**: Database
- **1 Redis**: Cache
- **1 Nginx**: Reverse proxy

Total: **4 containers** instead of 439!

## Local Deployment

```bash
./deploy_simple.sh
```

Access: http://localhost

## Cloud Deployment (Automatic)

1. Add secrets to GitHub:
   - `SSH_PRIVATE_KEY`: Your VM SSH key

2. Push to main branch:
   ```bash
   git add .
   git commit -m "Deploy unified app"
   git push origin main
   ```

3. GitHub Actions automatically deploys to http://100.31.44.107

## API Usage

### List all services
```bash
curl http://localhost/api/services
```

### Call a specific module
```bash
# GitHub Importer
curl -X POST http://localhost/api/backend/a-001/api/github/import \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/user/repo"}'

# Project Detector
curl -X POST http://localhost/api/backend/a-003/api/detect/project \
  -H "Content-Type: application/json" \
  -d '{"path": "/path/to/project"}'
```

## Benefits

- Single backend service - Not 366 separate containers
- Dynamic loading - Modules loaded on-demand
- Low memory - ~2-4GB RAM instead of 60GB+
- Fast deployment - Seconds instead of hours
- Auto-deploy - Push to GitHub -> Automatically deployed
- Easy to scale - Just increase Gunicorn workers

## Monitoring

```bash
# View logs
docker-compose -f docker-compose.yml logs -f backend

# Check health
curl http://localhost/health

# Restart
docker-compose -f docker-compose.yml restart backend
```
