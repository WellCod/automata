FROM node:22-alpine AS deps
WORKDIR /app
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY web/package.json ./web/
RUN pnpm install --frozen-lockfile --filter web

FROM node:22-alpine AS dev
WORKDIR /app
RUN corepack enable
COPY --from=deps /app/package.json /app/pnpm-lock.yaml /app/pnpm-workspace.yaml ./
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/web/node_modules ./web/node_modules

FROM node:22-alpine AS builder
WORKDIR /app
RUN corepack enable
COPY --from=deps /app/package.json /app/pnpm-lock.yaml /app/pnpm-workspace.yaml ./
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/web/node_modules ./web/node_modules
COPY web/ ./web/
RUN pnpm --filter web build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

COPY --from=builder /app/web/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/web/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
