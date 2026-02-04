# STAGE 1: BUILD
FROM node:20-alpine AS build
WORKDIR /app

# Kopírujeme package.json (a lockfile pokud existuje)
COPY package*.json ./

# ZMĚNA: Používáme 'npm install' místo 'npm ci', protože lockfile ještě neexistuje
RUN npm install

COPY . .
RUN npm run build

# STAGE 2: SERVE (Nginx)
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]