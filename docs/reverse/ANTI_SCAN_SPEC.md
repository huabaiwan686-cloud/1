# 原站防扫图配置完整规范（代码级逆向）

> 来源：`anti-scan-material-modal-Bt-4YtwE.js`（2026-10-07）
> 这是原站「防扫图处理」面板的完整表单默认值，可直接作为我方后端配置表 / 前端表单的字段设计依据。

## 配置字段全表（默认值）

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `globalEnabled` | `false` | 全局总开关 |
| `allowSingleOverrideEnabled` | `false` | 允许单条覆盖 |
| `forceBeforeSendEnabled` | `false` | 发送前强制处理 |
| `existingBatchEnabled` | `false` | 已有批次启用 |
| **基础保护** | | |
| `metadataStripEnabled` | `false` | 移除 EXIF（删除拍摄设备、定位、拍摄时间等元信息） |
| `compressionEnabled` | `false` | 压缩重编码（`compressionQuality: 82`） |
| `resizeEnabled` | `false` | 尺寸微调（`resizeScale: 96`，按比例重采样） |
| `cropEnabled` | `false` | 轻微裁剪（`cropPercent: 2`，裁掉边缘少量像素） |
| `jpegQualityControlEnabled` | `false` | JPEG 质量控制 |
| **图像扰动** | | |
| `noiseEnabled` | `false` | 噪点扰动（`noiseStrength: 18`） |
| `colorJitterEnabled` | `false` | 色彩扰动（`colorJitterStrength: 12`，色温/亮度/饱和度） |
| `sharpenBlurEnabled` | `false` | 锐化/模糊微扰（`sharpenBlurMode: 'blur'`, `sharpenBlurStrength: 8`；可选 `sharpen`） |
| **背景水印** | | |
| `backgroundReplaceEnabled` | `false` | 人像背景替换（⚠️ VIP 门控：`backgroundReplaceVipEnabled`） |
| `backgroundBlurEnabled` | `false` | 背景虚化 |
| `portraitBackgroundEnabled` | `false` | 人像背景 |
| `portraitSoftEdgeEnabled` | `false` | 人像柔边（`portraitSoftEdgeWidth: 12`） |
| `originalOverlayEnabled` | `false` | 原图叠加（`originalOverlayOpacity: 92`, `originalOverlayWidth: 72`） |
| `backgroundTextureEnabled` | `false` | 背景纹理（`backgroundTexturePreset: 'rabbit'`, `backgroundTextureImage: ''`） |
| `watermarkEnabled` | `false` | 轻水印（`watermarkText: 'xiaohuiji'`, `watermarkFontSize: 20`, `watermarkOpacity: 20`） |
| `profileNoWatermarkEnabled` | `false` | 资料无水印 |
| **遮罩/二维码/贴图** | | |
| `maskEnabled` | `false` | 遮罩（`maskMode: 'qr'`, `maskCount: 1`, `maskOpacity: 42`, `maskItemsJson: '[]'`） |
| `qrText` | `''` | 二维码文本 |
| `stickerImage` | `''` | 贴图图片 |
| `stickerText` | `''` | 贴图文本 |

## 面板分组（UI Tab）

1. **基础保护**：移除 EXIF / 压缩重编码 / 尺寸微调 / 轻微裁剪
2. **图像扰动**：噪点扰动 / 色彩扰动 / 锐化/模糊微扰
3. **背景水印**：人像背景替换 / 轻水印

开启背景替换时联动：`backgroundReplaceEnabled=true` →
`backgroundTextureEnabled=true`, `watermarkEnabled=false`, `profileNoWatermarkEnabled=false`；
关闭时 → `backgroundReplaceEnabled=false`, `backgroundTextureEnabled=false`,
`originalOverlayEnabled=false`, `portraitSoftEdgeEnabled=false`。

## 内置背景纹理预设（4 个，inline SVG）

| value | label |
|-------|-------|
| `rabbit` | 粉色贴图（默认） |
| `heart` | 爱心纹理 |
| `dot` | 点阵纹理 |
| `grid` | 网格纹理 |

SVG 源码已提取存于 `/tmp/xhj/` 的 `anti-scan-material-modal-Bt-4YtwE.js` 中
（`var R={dot:...,grid:...,heart:...,rabbit:...}`），可直接复用。
引用方式：`builtin:<name>` → `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`。

## 素材库

- 类型：`qr`（二维码）/ `sticker`（贴图）/ `background`（背景贴图）
- 接口见 API_INVENTORY.md「防扫图素材」一节
- localStorage 记录上次选择的背景：`youban:anti-scan:last-background-material`
