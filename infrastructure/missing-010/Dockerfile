# Minimal example app container with a static health endpoint
FROM alpine:3.20

# Create non-root user and install minimal tools
RUN adduser -D -H -u 10001 app \
    && apk add --no-cache ca-certificates busybox-extras curl \
    && mkdir -p /app/public \
    && echo '{"status":"ok"}' > /app/public/health.json

WORKDIR /app
EXPOSE 8080
USER app

# Serve static content on :8080
CMD ["sh","-c","busybox httpd -f -p 0.0.0.0:8080 -h /app/public"]

