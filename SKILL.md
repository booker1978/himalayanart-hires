---
name: himalayanart-hires
description: Download any zoomable image from www.himalayanart.org (HAR) at its full native resolution by fetching the tile pyramid and stitching it into one high-resolution image. Use whenever the user shares a himalayanart.org link (e.g. /items/36419/images/primary#...), gives a HAR item number, or asks to download / save / export / get a high-res copy of a HAR thangka, sculpture or tsa-tsa image, or to " stitch the zoom tiles".
---

# Himalayan Art Resources 高清图下载

HAR 的图片页是 Leaflet 瓦片查看器。瓦片源在 S3：
`https://har-assets.s3.amazonaws.com/tiles/<d1>/<d2>/<d3>/<item_id>/`，
其中 `<d1>/<d2>/<d3>` 是物品编号的前三位（如 36419 → `3/6/4/36419`）。
该目录下 `metadata.json` 给出 `width/height/maxZoom`；**瓦片层级是 0 到
maxZoom-1（查看器取 mapMaxZoom = maxZoom - 1），最高层即原图原生分辨率**。
瓦片 URL 规律：`{base}/{z}/{x}_{y}.jpg`（x 列，y 行，256px 一块，下划线分隔）。

## 步骤

1. 运行打包脚本，传物品编号或任意 HAR URL（带 `#` 锚点也行）：

   ```bash
   python -I "<skill_dir>/scripts/fetch_har_image.py" "https://www.himalayanart.org/items/36419/images/primary#257,-1562,2091,-645"
   ```

   常用参数：`-o 输出路径.jpg`、`--proxy http://127.0.0.1:7890`、
   `--keep-tiles`（保留瓦片）、`--quality 95`。

2. 脚本自动完成：解析编号 → 抓 primary 页提取瓦片源（失败则按编号规律构造）
   → 读 metadata → 并发下载顶层全部瓦片（带重试）→ Pillow 拼合并裁剪到原生
   尺寸 → 存 JPEG（quality 95）。默认输出 `har_<编号>_full.jpg`。

3. **看一眼成品图**确认完整无错位，再把文件路径（markdown 链接形式）给用户。

## 网络注意事项（重要）

- 本环境直连 himalayanart.org 常被 DNS 污染（解析到假 IP，超时）。
  脚本会先试直连、失败后**自动探测本机代理**（环境变量 → 7890/7897/1080/
  10808/8888 等常见端口）。若用户的代理在别的端口，用 `--proxy` 指定。
- primary 页面对脚本请求经常直接 403（站点对非浏览器指纹敏感，预热
  Cookie 也不保证过）——**这不是故障**：脚本会自动降级到编号规律构造的
  S3 瓦片地址（`tiles/<d1>/<d2>/<d3>/<id>`），S3 端无此限制，实测稳定。
- 部分瓦片是空白留白（417 字节灰阶）属正常，是原图边缘的留白，不是下载失败。
- 判定标准：最终打印 `downloaded 140/140 tiles` 一类全量成功即可靠；
  若有 FAILED 瓦片，成品会有白块——先重跑一次再考虑换代理。

## 依赖

Python3 + Pillow。缺 Pillow 时：`python -m pip install pillow -i https://pypi.tuna.tsinghua.edu.cn/simple`。

## 脚本失败时的手工路径（备用）

```bash
curl -s -x http://127.0.0.1:7890 -A "Mozilla/5.0" \
  "https://www.himalayanart.org/items/<id>" | grep -o 'resized/535px/[^"]*'
# primary 页找 metadata: /items/<id>/images/primary 里 grep har-assets
# 瓦片: har-assets.s3.amazonaws.com/tiles/<d>/<d>/<d>/<id>/<top>/<x>_<y>.jpg
# 拼合: Pillow 建 (cols*256, rows*256) 白底画布贴瓦片, crop 到 (width, height)
```
