# 构建阶段
FROM node:20-slim AS build
WORKDIR /web
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY . .
RUN npm run build

# 运行阶段
FROM nginx:alpine
COPY --from=build /web/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
