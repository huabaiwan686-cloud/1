# 构建阶段
FROM node:20-slim AS build
WORKDIR /web
COPY package.json ./
RUN npm install --no-audit --no-fund
# 只拷贝源码，排除 node_modules、.env、.git 等敏感/无用文件
# （之前 bug：COPY . . 会把本地 .env 密钥和 node_modules 打进镜像）
COPY src ./src
COPY public ./public
COPY index.html vite.config.* tsconfig*.json ./
RUN npm run build

# 运行阶段
FROM nginx:alpine
COPY --from=build /web/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
