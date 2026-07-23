# New API 使用统计 Dashboard

[English](README_EN.md) | 中文

一个适用于 New API 的纯静态使用日志看板。服务器定时从日志导出接口下载 CSV，按自然月归档；浏览器读取月度 CSV，并在本地完成筛选、汇总和图表渲染。

支持的视图包括：

- 自然月、自然年切换
- 成员和模型筛选
- 花费、请求数、Token 和活跃成员统计
- 成员花费排行与模型花费构成
- 按请求次数、花费或 Token 切换的每日热力图
- 成员使用趋势和明细表

## 架构

```text
New API 日志导出接口
  -> server/update_dashboard.py
  -> /var/www/newapi-dashboard/data/months/YYYY/YYYY-MM.csv
  -> /var/www/newapi-dashboard/data/index.json
  -> Nginx
  -> 浏览器中的 index.html + ECharts + Papa Parse
```

页面本身不包含后端代码，也不会接触访问令牌。API 凭证只保存在服务器当前用户的受保护配置目录中。

## 仓库结构

```text
.
|-- index.html
|-- server/
|   `-- update_dashboard.py
|-- deploy/
|   |-- deploy-dashboard.ps1
|   `-- nginx-newapi-dashboard.conf
|-- vendor/
|   |-- echarts.min.js
|   `-- papaparse.min.js
|-- .gitignore
|-- README.md
`-- THIRD_PARTY_NOTICES.md
```

运行期间生成的 CSV、日志、状态文件、密码和访问令牌均由 `.gitignore` 排除。

## 环境要求

服务器建议使用 Ubuntu，并安装：

- Python 3.6 或更高版本
- Nginx
- `cron` 和 `flock`
- `apache2-utils`，仅用于生成 Nginx Basic Auth 密码文件

安装软件：

```bash
sudo apt update
sudo apt install -y nginx python3 cron util-linux apache2-utils
```

以下命令假设使用当前 Linux 用户运行更新器。无需专门创建新用户，但不要使用 `root` 运行定时下载任务。

## 1. 下载项目

将地址替换为自己的 GitHub 仓库：

```bash
git clone https://github.com/YOUR_NAME/newapi-dashboard.git ~/newapi-dashboard
cd ~/newapi-dashboard
```

## 2. 创建目录并部署静态文件

让当前用户拥有站点目录的写权限，Nginx 只需要读取权限：

```bash
sudo install -d -o "$USER" -g "$USER" -m 755 /var/www/newapi-dashboard /var/www/newapi-dashboard/data /var/www/newapi-dashboard/vendor
install -m 644 index.html /var/www/newapi-dashboard/index.html
install -m 644 vendor/echarts.min.js vendor/papaparse.min.js /var/www/newapi-dashboard/vendor/
install -d -m 755 "$HOME/newapi-dashboard-runtime/logs" "$HOME/newapi-dashboard-runtime/state"
install -m 750 server/update_dashboard.py "$HOME/newapi-dashboard-runtime/update_dashboard.py"
```

## 3. 配置 API 认证信息

更新器需要三项连接信息：

- 完整日志导出 URL，例如 `https://new-api.example.com/api/log/self/export`
- `New-Api-User` 对应的用户 ID
- 用户访问令牌

创建只允许当前用户读取的配置目录：

```bash
install -d -m 700 "$HOME/.config/newapi-dashboard"
```

写入完整的日志导出 URL：

```bash
read -rp "Export URL: " NEW_API_EXPORT_URL; printf '%s\n' "$NEW_API_EXPORT_URL" > "$HOME/.config/newapi-dashboard/export_url"; chmod 600 "$HOME/.config/newapi-dashboard/export_url"; unset NEW_API_EXPORT_URL
```

交互式写入用户 ID，输入内容不会进入 Git 仓库：

```bash
read -rp "New-Api-User: " NEW_API_USER_ID; printf '%s\n' "$NEW_API_USER_ID" > "$HOME/.config/newapi-dashboard/user_id"; chmod 600 "$HOME/.config/newapi-dashboard/user_id"; unset NEW_API_USER_ID
```

交互式写入访问令牌，终端不会显示令牌：

```bash
read -rsp "Access token: " NEW_API_TOKEN; printf '\n'; printf '%s\n' "$NEW_API_TOKEN" > "$HOME/.config/newapi-dashboard/access_token"; chmod 600 "$HOME/.config/newapi-dashboard/access_token"; unset NEW_API_TOKEN
```

不要把这两个文件放进仓库，也不要把令牌写在 Python、README、crontab 或命令历史中。

## 4. 首次下载数据

运行一次更新器：

```bash
python3 "$HOME/newapi-dashboard-runtime/update_dashboard.py"
```

正常情况下会：

1. 下载当前自然月。
2. 首次运行时下载并封存上一个自然月。
3. 写入 `/var/www/newapi-dashboard/data/months/YYYY/YYYY-MM.csv`。
4. 生成 `/var/www/newapi-dashboard/data/index.json`。

强制重新下载上个月：

```bash
python3 "$HOME/newapi-dashboard-runtime/update_dashboard.py" --refresh-previous
```

更新器固定按照 UTC+8 计算自然月，不依赖服务器默认时区。

### 可选环境变量

默认路径通常不需要修改。需要自定义时可使用：

| 变量 | 默认值 |
|---|---|
| `NEW_API_EXPORT_URL` | 读取配置目录中的 `export_url` |
| `NEW_API_CONFIG_DIR` | `~/.config/newapi-dashboard` |
| `NEW_API_USER_ID` | 读取配置目录中的 `user_id` |
| `NEW_API_ACCESS_TOKEN` | 读取配置目录中的 `access_token` |
| `NEW_API_DATA_DIR` | `/var/www/newapi-dashboard/data` |
| `NEW_API_STATE_DIR` | `~/newapi-dashboard-runtime/state` |

环境变量中的凭证可能被进程管理工具记录，因此生产环境更推荐权限为 `600` 的配置文件。

## 5. 配置 Nginx 和登录密码

配置文件默认启用 HTTP Basic Auth。创建用户名时，将 `dashboard` 替换为你希望使用的登录名：

```bash
sudo htpasswd -c /etc/nginx/.htpasswd dashboard
```

安装站点配置并禁用 Ubuntu 默认站点：

```bash
sudo install -m 644 deploy/nginx-newapi-dashboard.conf /etc/nginx/sites-available/newapi-dashboard
sudo ln -sfn /etc/nginx/sites-available/newapi-dashboard /etc/nginx/sites-enabled/newapi-dashboard
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

浏览器访问：

```text
http://SERVER_IP/
```

如果不需要密码保护，删除 Nginx 配置中的以下两行后重新加载：

```nginx
auth_basic "New API Dashboard";
auth_basic_user_file /etc/nginx/.htpasswd;
```

Basic Auth 在普通 HTTP 下不会加密传输密码。仅建议在可信局域网使用；通过公网访问时必须配置 HTTPS，并使用强密码和防火墙访问控制。

## 6. 配置自动更新

确认服务器时区：

```bash
sudo timedatectl set-timezone Asia/Shanghai
date
```

编辑当前用户的定时任务：

```bash
crontab -e
```

每天 08:00 至 21:00 每个整点更新一次。将 `/home/YOUR_USER` 替换为 `echo "$HOME"` 显示的实际路径：

```cron
TZ=Asia/Shanghai
0 8-21 * * * flock -n /home/YOUR_USER/newapi-dashboard-runtime/update.lock /usr/bin/python3 /home/YOUR_USER/newapi-dashboard-runtime/update_dashboard.py >> /home/YOUR_USER/newapi-dashboard-runtime/logs/update.log 2>&1
```

检查执行日志：

```bash
tail -n 50 "$HOME/newapi-dashboard-runtime/logs/update.log"
```

## 7. 后续更新部署

### 在服务器通过 Git 更新

```bash
cd ~/newapi-dashboard
git pull --ff-only
install -m 644 index.html /var/www/newapi-dashboard/index.html
install -m 644 vendor/echarts.min.js vendor/papaparse.min.js /var/www/newapi-dashboard/vendor/
install -m 750 server/update_dashboard.py "$HOME/newapi-dashboard-runtime/update_dashboard.py"
```

### 从 Windows 上传静态页面

PowerShell 中执行，替换服务器地址：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\deploy\deploy-dashboard.ps1" -Server "user@SERVER_IP"
```

部署脚本只上传 `index.html` 和 `vendor/`，不会上传 CSV 或凭证。首次部署前仍需按照前面的步骤创建远程目录和权限。

## 8. 验证与排错

检查 Nginx：

```bash
sudo nginx -t
systemctl is-active nginx
curl -I -u 'YOUR_LOGIN:YOUR_PASSWORD' http://127.0.0.1/
```

检查数据：

```bash
cat /var/www/newapi-dashboard/data/index.json
find /var/www/newapi-dashboard/data/months -type f -name '*.csv' -ls
```

手动运行更新器并观察错误：

```bash
python3 "$HOME/newapi-dashboard-runtime/update_dashboard.py"
```

常见问题：

- `401` 或 `403`：用户 ID 或访问令牌无效、过期。
- `Permission denied`：当前用户不能写入 `/var/www/newapi-dashboard`，重新检查目录所有者。
- 页面显示依赖加载失败：确认 `/var/www/newapi-dashboard/vendor/` 中两个 JavaScript 文件存在且可读。
- 页面没有月份：确认 `data/index.json` 存在，并且至少一个月的 `rows` 大于 `0`。
- 定时任务不运行：检查 `crontab -l`、服务器时区和更新日志。

## 数据与安全

- CSV 中可能包含成员姓名、令牌名称、请求 ID 和使用记录，禁止提交到 GitHub。
- 不要提交访问令牌、用户 ID 文件、Nginx 密码文件、SSH 私钥和运行日志。
- 当前 `index.html` 中可能包含用于合并历史名称的成员别名。公开仓库前请检查这些名称是否可以公开。
- 如果凭证曾经被提交，即使后来删除，仍会存在于 Git 历史中。应立即撤销旧凭证并重写仓库历史。

## 第三方组件

前端包含 Apache ECharts 5.5.1 和 Papa Parse 5.4.1。详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
