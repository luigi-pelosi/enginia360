FROM node:24.22.0-alpine3.24@sha256:44fce696f38ba8c987c4db89954051000bbd05ffd8d8659ba15ed4a8602e937f AS build
WORKDIR /source
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
ARG VITE_B04_TEST_UI=false
ARG VITE_B06_TEST_UI=false
ARG VITE_B07_TEST_UI=false
ARG VITE_B08_TEST_UI=false
ARG VITE_B09_TEST_UI=false
ARG VITE_B12_TEST_UI=false
ENV VITE_B12_TEST_UI=${VITE_B12_TEST_UI}
ARG VITE_B10_TEST_UI=false
ENV VITE_B10_TEST_UI=${VITE_B10_TEST_UI}
ENV VITE_B09_TEST_UI=${VITE_B09_TEST_UI}
ENV VITE_B08_TEST_UI=${VITE_B08_TEST_UI}
ENV VITE_B07_TEST_UI=${VITE_B07_TEST_UI}
ENV VITE_B06_TEST_UI=${VITE_B06_TEST_UI}
ARG VITE_B05_TEST_UI=false
ENV VITE_B05_TEST_UI=${VITE_B05_TEST_UI}
ENV VITE_B04_TEST_UI=${VITE_B04_TEST_UI}
ARG VITE_B03_TEST_UI=false
ENV VITE_B03_TEST_UI=${VITE_B03_TEST_UI}
ARG VITE_B02_TEST_UI=false
ENV VITE_B02_TEST_UI=${VITE_B02_TEST_UI}
RUN VITE_B12_TEST_UI=false VITE_B10_TEST_UI=false VITE_B09_TEST_UI=false VITE_B08_TEST_UI=false VITE_B07_TEST_UI=false VITE_B06_TEST_UI=false VITE_B05_TEST_UI=false npm test && npm run build

FROM nginx:1.30.6-alpine3.24@sha256:750f6c5456af731b47295d124fbed55664eeb1daab4f6bac0b092b7406235091
COPY web/nginx.conf /etc/nginx/nginx.conf
COPY --from=build /source/dist /usr/share/nginx/html
USER 101:101
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8080/health/ready || exit 1
ENTRYPOINT ["nginx", "-g", "daemon off;"]
