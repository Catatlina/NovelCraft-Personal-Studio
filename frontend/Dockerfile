FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=80
ENV API_UPSTREAM=http://api:8000
COPY --from=build /app/dist/ ./dist/
COPY server.mjs ./server.mjs
EXPOSE 80
CMD ["node", "server.mjs"]
