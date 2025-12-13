#!/bin/bash
# Simple Local Deployment

echo "========================================="
echo "UNIFIED APP - SIMPLE DEPLOYMENT"
echo "========================================="
echo ""
echo "Services: 4 containers (backend, postgres, redis, nginx)"
echo "Backend: Dynamically loads all 437 modules"
echo ""

# Build and start
docker-compose -f docker-compose.simple.yml down
docker-compose -f docker-compose.simple.yml build
docker-compose -f docker-compose.simple.yml up -d

echo ""
echo "Waiting for services to start..."
sleep 5

# Show status
docker-compose -f docker-compose.simple.yml ps

echo ""
echo "========================================="
echo "DEPLOYMENT COMPLETE"
echo "========================================="
echo "Access: http://localhost"
echo "API: http://localhost/api/services"
echo "Health: http://localhost/health"
echo ""
echo "View logs: docker-compose -f docker-compose.simple.yml logs -f"
echo "Stop: docker-compose -f docker-compose.simple.yml down"
echo "========================================="
