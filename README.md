# himalayanart-hires

一个 [ZCode](https://zcode.ai) 技能：把 [www.himalayanart.org](https://www.himalayanart.org)（HAR，喜马拉雅艺术资源库）上的**缩放查看器图片以原生最高分辨率整图下载**下来——自动抓取瓦片金字塔并无缝拼合成一张高清大图。

A ZCode skill that downloads any zoomable image from Himalayan Art Resources at its full native resolution by fetching the site's tile pyramid and stitching it into a single high-resolution JPEG.

## 为什么需要它

HAR 的图片页（如 `https://www.himalayanart.org/items/36419/images/primary`）是 Leaflet 瓦片查看器，网页上"Open in tab"给出的只有 2000px 缩略版，而瓦片金字塔的最高层往往是更大的原生分辨率（例：36419 实际为 2550×3405；65088 为 6075×8850）。本技能把最高层全部瓦片抓下来无损拼合，得到网页上看不到的完整高清原图。

## 安装 Install

克隆到用户级技能目录即可被 ZCode 发现：

```bash
git clone https://github.com/booker1978/himalayanart-hires.git \
  ~/.agents/skills/himalayanart-hires
```

Windows 下即 `C:\Users\<你>\.agents\skills\himalayanart-hires`。
也可以放进项目的 `.zcode/skills/` 或 `.agents/skills/`（仅当前项目可用）。

依赖 Dependencies：Python 3 + [Pillow](https://python-pillow.org)（仅拼合用），其余全部为标准库。

```bash
python -m pip install pillow
```

## 使用 Usage

技能触发后（或手动调用）等价于执行：

```bash
python -I scripts/fetch_har_image.py "https://www.himalayanart.org/items/36419/images/primary#257,-1562,2091,-645"
```

- 目标可以是**任意 HAR 链接**（带 `#` 锚点也行）或**纯物品编号**（如 `65088`）
- 输出默认 `har_<编号>_full.jpg`（JPEG quality 95）
- 可选参数：

| 参数 | 说明 |
|---|---|
| `-o 路径.jpg` | 指定输出文件 |
| `--proxy http://127.0.0.1:7890` | 指定代理（默认自动探测：环境变量 → 7890/7897/1080/10808/8888 等常见本地端口） |
| `--keep-tiles` | 保留下载的瓦片 |
| `--quality 95` | JPEG 质量 |

## 工作原理 How it works

1. 访问物品页 `…/items/<id>`（预热 Cookie），再抓查看器页 `…/items/<id>/images/primary`；
2. 从页面里提取瓦片源 `https://har-assets.s3.amazonaws.com/tiles/<d1>/<d2>/<d3>/<id>/`（`<d1><d2><d3>` 为编号前三位，如 36419 → `3/6/4/36419`）；查看器页 403 时自动降级为按编号规律构造该地址（S3 端无反爬限制，稳定可用）；
3. 读取 `metadata.json` 的 `width/height/maxZoom`。**注意查看器取 `mapMaxZoom = maxZoom - 1`，所以瓦片层级是 0 到 maxZoom-1，最高层即原生分辨率**；
4. 顶层瓦片 URL 规律 `{base}/{z}/{x}_{y}.jpg`（x 列 y 行，256px，下划线分隔），并发下载（带重试）；
5. Pillow 建 `(cols×256, rows×256)` 画布贴瓦片，裁剪到 `(width, height)`，存 JPEG。

> 部分瓦片是 417 字节的空白灰阶——那是原图边缘的留白，不是下载失败。

## 网络说明

HAR 与 GitHub 在部分网络环境下存在 DNS 污染（解析到假 IP，直连超时）。脚本先试直连、失败后自动升级到本机代理；中国大陆用户常见的 Clash 等代理（7890 端口）会被自动识别，也可以用 `--proxy` 显式指定。

## 版权声明 / Copyright

HAR 站点图片版权归原收藏机构与 [Himalayan Art Resources Inc.](https://www.himalayanart.org) 所有（"Images Provided Courtesy of Private Collections"）。本工具仅供个人研究、学习使用，请勿商用或再分发下载的图片，使用前请阅读 HAR 的 [Copyright 说明](https://www.himalayanart.org/introduction/#copyright)。

## License

[MIT](LICENSE)
