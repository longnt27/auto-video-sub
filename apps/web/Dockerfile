# syntax=docker/dockerfile:1.12
FROM node:22.22.2-bookworm-slim AS dependencies
ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile

FROM dependencies AS builder
COPY apps/web apps/web
RUN pnpm --filter @auto-video-sub/web build

FROM node:22.22.2-bookworm-slim AS runtime
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app app
WORKDIR /app
COPY --from=builder --chown=10001:10001 /app/apps/web/.next/standalone ./
COPY --from=builder --chown=10001:10001 /app/apps/web/.next/static ./apps/web/.next/static
USER 10001:10001
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
