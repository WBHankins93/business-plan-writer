FROM node:20-slim AS deps
WORKDIR /app
COPY package.json ./
RUN npm install

FROM node:20-slim AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_API_KEY
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_API_KEY=$NEXT_PUBLIC_API_KEY
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public && npm run build

FROM node:20-slim AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000
CMD ["npm", "run", "start"]
