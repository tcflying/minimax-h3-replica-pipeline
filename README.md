# MiniMax H3 长视频复刻管线（RTX 3090 · ComfyUI 0.44 · Director EG 管道）

> 从一条对标带货原片，在单张 RTX 3090（24GB）上产出 35 秒 / 840 帧 / 960×544 竖版 / 原生中英音轨的商品替换成片。全程本地、无云端 API。
> 本仓 = 成片 + 可复用工作流模板 + 启动/提交脚本 + 全部实测台账（加速倍数、分辨率矩阵、坑与判决）。

## 成片

| 文件 | 说明 |
|---|---|
| `outputs/final-540p-35s.mp4` | 终版：840 帧 / 35.000s / 960×544 / 24fps / 立体声。商品=粉色针织童袜鞋（三排白图案+灰拉环），人物/厨房/动作跟源片，英文女声旁白 8 段逐词 ASR 干净。 |
| `outputs/draft-480p-35s-showcase.mp4` | 早期 480p 草稿（prior-driven，仅留档对比）。 |
| `review/final-13frames.jpg` | 终版 13 帧总览（验收图）。 |
| `review/seams-worst3.jpg` | 最差 3 接缝前后帧对。 |

## 一、硬件与软件要求

- GPU：RTX 3090 24GB（Ampere SM86；实测峰值 16.0GB @540p、17.6GB @768p——不爆显存）
- 内存：≥64GB（本机 128GB）
- Python 3.12 + ComfyUI **≥ 0.44.0**（H3 视频条件打包路径 `_embed_and_pack` / `MiniMaxH3LatentUpscaleWithModel` / Sol-H3-VAE 支持都在 0.44）
- 依赖：`pip install opencv-python-headless`、`pip install -U comfy-aimdo`（0.44 需要 `pageout_callback` 签名）
- 自定义节点：`ComfyUI_MiniMaxH3_Director`（commit ≥ 4c6245e）、`ComfyUI-VideoHelperSuite`（≥1.7.9）

## 二、模型文件（放入 `ComfyUI/models/`）

| 类型 | 文件 | 说明 |
|---|---|---|
| UNET | `minimax_h3_ref2va_pruned_int8_convrot.safetensors` (19.5G) | **必须 ref2va**；fl2va 不会触发源视频编辑 |
| 文本编码器 | `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` (25.3G) | 3090 用 int8；先编码后卸载（ComfyUI 自动 offload） |
| 视频 VAE | `minimax_h3_video_vae_fp16.safetensors` | |
| 音频 VAE | `minimax_h3_audio_vae_fp32.safetensors` | **必装**，否则无声 |
| LoRA（画面档） | `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | 4 步草稿主力 |
| LoRA（音频档） | `pika_h3_flex_ref2va_comfy_bf16.safetensors` | 6 步质量档；<6 步音频会衰减，台词关键段用它 |
| 放大（可选） | `minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors` (659M) | Refine 二采/2K |

## 三、性能栈（实测）

| 项 | 实测 | 说明 |
|---|---|---|
| **comfy kitchen attention**（原生 `ModelAttentionBackend`） | **120s/段 vs 2760s = 23×** | 3090 上 pytorch cross-attention 是瓶颈；INT8 量化注意力是正解。输出与基线 cosine 0.997（零回归） |
| Turbo 4 步 LoRA | vs 25 步 6× | 与 kitchen 叠加 |
| Veda 稀疏注意力 | 120s→120s（无增益） | 4 步档已非注意力瓶颈，不叠 |
| Sage2/KJNodes | 备用 | 与 kitchen 同思路，原生已有等价物 |
| ⚠️ VSA gate | 不可用 | 依赖 sol_attn，需 SM89+，3090 排除 |

**分辨率矩阵（段6 同 seed 实测）**

| 档 | 分辨率 | 耗时/段 | 峰值显存 | 源片相似度 | 结论 |
|---|---|---|---|---|---|
| A | 480×864 | 120s | 15.9G | 0.4964 | 快稿档 |
| **B** | **540×960** | **150s** | **16.0G** | **0.5623 最高** | **性价比主线（本仓成片即此档）** |
| C | 640×1152 | 240s | 15.9G | 0.4818 | 两头不占，淘汰 |
| D | 768×1344 | 360s | 17.6G | 0.4811 | 最高质量档（H3 调校 sweet spot=短边768） |

## 四、关键判决：Director 两种管道（重要！）

- ❌ **单节点 timeline 管道**（`MiniMaxH3Director` 直接吃 `timeline_data.video.fileName`）：源视频条件**不进 DiT**。归零实验（指令"原样复现"，零参考）输出仍是先验手持特写；运动量 4.95 vs 源片 11.60——**死路**。
- ✅ **external-groups（EG）管道**（`VHS_LoadVideo → MiniMaxH3DirectorGroupReferenceToVideo → GroupsCombine → Director.r2v_groups`）：视频条件真实生效。归零测试运动量 11.21≈源片，颜色 cosine 0.58。
- 证据链见 `records/critical-finding-rv2v-vs-eg.json`。

## 五、使用步骤（10 段拆分复刻法）

1. **切源片**：1080×1920 源 → `ffmpeg -vf "crop=1064:1920:8:0,scale=480:864:flags=lanczos,fps=24"`（宽高 32 倍数）→ 按动作边界切 10 窗（重编码切，`-c copy` 会关键帧错乱）。
2. **参考图**：商品原图 + 图案裁切 + 拉环裁切（原像素，不带环境/人物）放 input/。
3. **起服务**：改 `scripts/launch_comfyui_8193.py` 的路径常量后运行。
4. **单段生成**：改 `scripts/generate_segment.py` 的输入/台词/帧数后运行（帧数取 ≥目标的 17k+5 网格档：124/141/158…，生成后裁到目标帧）。
5. **拼装**：逐段 `-t <目标帧>/24` 裁剪重编码 → concat 视频+音频 → 840 帧 35.000s 成片。
6. **验收**（本仓实际用的四件套）：
   - 视觉：多模态模型抽 13 帧+9 接缝逐帧判（商品三排图案/拉环/无旧品/无崩坏）
   - 客观：全片运动量 vs 源片（帧差均值同量级=源跟随）
   - ASR：whisper.cpp 16k 单声道逐词核台词（4 步档台词易重复/含糊→关键段用 Pika 6 步重生）
   - 接缝：段界前后帧像素差排序 + 视觉评级（GOOD/MINOR/BAD）
7. **修复循环**：BAD 接缝→按 N06 首态法改写该段提示词（"Continuing from..."承接前段末态）+换 seed 重生该段；音频瑕疵→该段切 M-Pika 6 步。

## 六、坑清单（每条都实测踩过）

1. `-c copy` 切窗关键帧错乱 → 必须重编码
2. `-t` 不支持分数（`112/24` 报错）→ 用小数
3. `SaveVideo` API 需 `format/format.codec/codec` 三参
4. Director API 提交需 `bd_grp_*` 空串占位；`MiniMaxH3DirectorGroupReferenceToVideo` 需 `ref_image_size:"match"`
5. 输出宽高默认 `long_edge` 模式（横版）→ 必须 `timeline_data.output.mode="fixed"`
6. 3090≠40 系；INT8 正确理由是"Ampere 无 FP8/NVFP4"
7. 编码器 25.3G>24G 卡 → 依赖自动 offload（先编码后卸载），内存 ≥64G
8. 0.44 与旧 comfy-aimdo 断裂（`pageout_callback`）→ `pip install -U comfy-aimdo`
9. 缺 opencv → `pip install opencv-python-headless`
10. H3 帧数网格 17k+5（124/141/158/107/90/73/56），宽高 32 倍数
11. 音频参考只传音色、台词写进提示词；不写负面词（"no box"会被读成要盒子）——用正面措辞："plain hands only, no box" 放句中描述而非否定开头
12. Pika adapter 官方文件名是 `pika_h3_flex_ref2va_comfy_bf16.safetensors`（模板里的 `v1_bf16` 与归档不同名）
13. 台词 <6 步音频衰减（重复/含糊）→ 正式台词段用 6 步

## 七、台账索引

- `records/resolution-matrix.json` —— 四档分辨率实测数据
- `records/b540-batch-receipt.json` —— 终版 10 段生成回执（耗时/显存/prompt_id）
- `records/batch-runlog.md` —— 全部批次运行日志
- `records/critical-finding-rv2v-vs-eg.json` —— 管道判决证据链

## License / 素材说明

- 代码与工作流：MIT
- `outputs/` 成片由本项目管线生成，商品图与源片为业务素材，不包含在本仓
