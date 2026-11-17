FROM node:26-alpine AS base
WORKDIR /app
# o node 26 não traz mais o corepack: o pnpm vem do npm, na versão do packageManager
COPY package.json ./
RUN npm install -g "$(node -p "require('./package.json').packageManager")"

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY web/package.json ./web/
RUN pnpm install --frozen-lockfile --filter web

FROM base AS dev
COPY --from=deps /app/package.json /app/pnpm-lock.yaml /app/pnpm-workspace.yaml ./
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/web/node_modules ./web/node_modules

FROM base AS builder
COPY --from=deps /app/package.json /app/pnpm-lock.yaml /app/pnpm-workspace.yaml ./
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/web/node_modules ./web/node_modules
COPY web/ ./web/
RUN pnpm --filter web build

FROM node:26-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

# Em monorepo pnpm o standalone espelha o workspace: o server.js fica em web/.
COPY --from=builder --chown=nextjs:nodejs /app/web/.next/standalone ./
COPY --from=builder /app/web/public ./web/public
COPY --from=builder --chown=nextjs:nodejs /app/web/.next/static ./web/.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
# versão publicada (tag) e revisão do git, mostradas no /health (OPS-04)
ARG AUTOMATA_VERSION=dev
ARG AUTOMATA_REVISION=
ENV AUTOMATA_VERSION=$AUTOMATA_VERSION AUTOMATA_REVISION=$AUTOMATA_REVISION
CMD ["node", "web/server.js"]
