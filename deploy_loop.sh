#!/bin/bash
# 部署循环发布功能 + 启动 worker 服务
set -e
cd ~/workspace/rebuild

echo "=== 1. 打包后端 ==="
tar -czf /tmp/loop-deploy.tar.gz -C backend app

echo "=== 2. 备份数据库 ==="
# (在服务器上执行)

echo "=== 3. 上传并部署 ==="
# (通过代理上传到服务器，解压，重启 API，安装 worker 服务)

echo "部署脚本待执行"
