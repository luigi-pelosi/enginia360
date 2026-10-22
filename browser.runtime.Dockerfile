FROM mcr.microsoft.com/playwright:v1.58.2-noble@sha256:6446946a1d9fd62d9ae501312a2d76a43ee688542b21622056a372959b65d63d
RUN apt-get update -qq && apt-get install -y --no-install-recommends libnss3-tools=2:3.98-1ubuntu0.3 && rm -rf /var/lib/apt/lists/*
WORKDIR /acceptance
COPY tests/browser/package.json tests/browser/package-lock.json ./
RUN npm ci --ignore-scripts && npm audit --audit-level=high
COPY tests/browser/ ./
USER 1001:1001
ENV HOME=/tmp/browser-home
ENTRYPOINT ["sh", "-c", "mkdir -p \"$HOME/.pki/nssdb\" && certutil -N -d sql:$HOME/.pki/nssdb --empty-password && certutil -A -d sql:$HOME/.pki/nssdb -n runtime-ephemeral-ca -t C,, -i /run/tls/ca.crt && exec node acceptance.cjs"]
