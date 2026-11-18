FROM node:24.22.0-alpine3.24 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
ARG API_URL=http://backend:8080
ENV API_URL=$API_URL
RUN npm run build
FROM node:24.22.0-alpine3.24 AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000 API_URL=http://backend:8080
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
COPY --chown=node:node start.cjs ./start.cjs
USER node
EXPOSE 3000
CMD ["node","start.cjs"]
