#!/bin/bash
echo "Starting all services..."
docker-compose up --build -d
echo "All services started"
docker-compose ps
