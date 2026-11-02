FROM node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f AS verify
WORKDIR /app
RUN mkdir /scratch && chown node:node /app /scratch
USER node
ENV NEXT_TELEMETRY_DISABLED=1 TMPDIR=/scratch HOME=/scratch
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-fund && npm audit --audit-level=low
COPY --chown=node:node . .
RUN npm test && npm run build && npm run typecheck

FROM node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000 TMPDIR=/scratch HOME=/scratch
COPY --from=verify --chown=node:node /app/.next/standalone ./
COPY --from=verify --chown=node:node /app/.next/static ./.next/static
USER node
EXPOSE 3000
HEALTHCHECK --interval=2s --timeout=3s --start-period=5s --retries=15 CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["node", "server.js"]

FROM mcr.microsoft.com/playwright:v1.58.2-noble@sha256:6446946a1d9fd62d9ae501312a2d76a43ee688542b21622056a372959b65d63d AS browser
WORKDIR /app
COPY --from=verify /app/node_modules ./node_modules
COPY playwright.config.ts ./
COPY tests/acceptance.spec.ts ./tests/acceptance.spec.ts
ENV TMPDIR=/scratch HOME=/scratch
USER 1001:1001
ENTRYPOINT ["node", "node_modules/@playwright/test/cli.js", "test"]
