# Base build with dependencies
FROM node:20-alpine AS base
WORKDIR /usr/src/app
ENV PATH=/usr/src/app/node_modules/.bin:$PATH
COPY package*.json ./
RUN npm ci
COPY src ./src
COPY scripts ./scripts
COPY nodemon.json ./nodemon.json

# Development image
FROM base AS dev
# Tools needed for wait-for and debugging convenience
RUN apk add --no-cache bash netcat-openbsd
COPY docker/dev-entrypoint.sh /usr/local/bin/dev-entrypoint.sh
RUN chmod +x /usr/local/bin/dev-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/dev-entrypoint.sh"]
EXPOSE 3000 9229
CMD ["npm", "run", "dev"]

# Production image
FROM base AS prod
ENV NODE_ENV=production
RUN npm prune --production
EXPOSE 3000
CMD ["npm", "start"]

