# 抖音作品归档

用于个人授权内容的抖音作品归档与追更。服务连接到用户自行登录的本机 Chrome 会话，读取公开作者页已加载的作品数据，将视频和图文保存到本地目录。

> 仅应归档你拥有版权、已获得许可或依法允许保存的公开内容。请遵守抖音服务条款、著作权、隐私和所在地法律。本项目不包含验证码绕过、DRM 破解、付费内容下载或访问限制规避功能。

## 功能

- 通过作者主页链接或 `sec_uid` 一键归档作品。
- 订阅作者并按 Cron 周期自动追更。
- 视频和图文按 `作者/视频|图文/YYYY-MM-DD/` 分类。
- 已完成作品使用 ID 去重，重复同步不会重复下载。
- 本地控制台展示 Chrome 会话、队列、订阅、任务状态和失败原因。
- 轻量镜像：浏览器适配器直接保存作者页公开返回的媒体地址，不依赖内置 ffmpeg。

## 前置条件

- Docker Desktop（Windows/macOS）或 Docker Engine + Compose（Linux）。
- Google Chrome，用于用户自行登录抖音并提供浏览器会话。
- 仅可访问公开内容的网络环境。

## 快速开始

```powershell
git clone <你的仓库地址> douyin-archive
cd douyin-archive
docker compose up -d
```

`.env` 是可选的本机覆盖文件。需要修改同步周期或 Chrome 地址时，再复制 `.env.example` 为 `.env`。

使用 Docker Hub 镜像时无需本地构建。开发者如需从源码构建，使用：

```powershell
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

启动一个独立的 Chrome 配置目录并自行登录抖音：

```powershell
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="$env:LOCALAPPDATA\DouyinArchiveChrome"
```

打开 `http://localhost:8000`。控制台显示“Chrome 会话在线”后，即可一键归档或添加追更订阅。

## 配置

复制 `.env.example` 为 `.env` 后按需调整：

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `SYNC_CRON` | `15 */6 * * *` | 订阅同步周期，五段 Cron 表达式。 |
| `BROWSER_CDP_URL` | `http://host.docker.internal:9222` | 用户 Chrome 的调试地址。 |
| `PROFILE_SCROLL_ROUNDS` | `18` | 读取作者页时的最大滚动次数。 |
| `DOWNLOAD_ROOT` | `/app/downloads` | 容器内归档目录。 |
| `PYTHON_IMAGE` | `python:3.12-slim` | 可选基础镜像覆盖；仅在 Docker Hub 不可达时使用可信镜像。 |

## 数据目录

Docker Compose 会将以下目录保存在宿主机项目目录内，均不会被提交到 Git：

- `downloads/`：下载的媒体文件与 `.browser-archive.txt` 去重记录。
- `data/app.db`：订阅与任务记录。
- `.env`：本机配置，不应公开。

## 常用命令

```powershell
docker compose logs -f
docker compose ps
docker compose up -d --build
docker compose down
```

## 发布提示

远程部署时，归档容器必须能连接到一个用户自行管理、已登录的 Chrome DevTools 地址。不要把浏览器用户目录、Cookie、账号密码或 `.env` 上传到 Git 仓库。

## 许可证

[MIT](LICENSE)
