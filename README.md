# AI-Driven Plan Engine

基于 YAML DSL + OR-Tools CP-SAT 的户型生成引擎。  
核心流程：`DSL (YAML) -> Solver -> Validator -> Renderer (SVG/PNG)`。

## 1. 环境准备

前置要求：
- Python 3.13+
- `uv`（依赖安装与运行）

安装依赖：

```bash
make sync
```

## 2. 快速开始

仓库内默认提供一个可跑通的 2 层带楼梯示例：
- 规格文件：`tmp/spec.yaml`
- 默认输出：`tmp/plan_output`

一条命令生成：

```bash
make run-default
```

成功后会生成：
- `tmp/plan_output/solution.json`
- `tmp/plan_output/report.txt`
- `tmp/plan_output/F1.svg`, `tmp/plan_output/F1.png`
- `tmp/plan_output/F2.svg`, `tmp/plan_output/F2.png`

## 3. 常用命令

查看所有命令：

```bash
make help
```

自定义 spec / 输出目录 / 求解超时：

```bash
make run SPEC=tmp/spec.yaml OUTDIR=tmp/plan_output TIMEOUT=120
```

语法检查：

```bash
make check-syntax
```

一键验证（语法检查 + 默认示例生成）：

```bash
make verify
```

清理输出：

```bash
make clean-output OUTDIR=tmp/plan_output
make clean-tmp
```

## 4. 手动运行（不走 Makefile）

```bash
uv run python main.py --spec tmp/spec.yaml --outdir tmp/plan_output --solver-timeout 90
```

## 5. 常见问题

- `dsl_parse_failed`：检查 `spec.yaml` 字段名、缩进、网格对齐（455mm）。
- `solve_failed`：约束过紧或相互冲突，先减少房间数量/邻接关系后再逐步增加。
- `Plan rejected by validation`：查看 `report.txt` 中 `Errors` 和 `Warnings`。

## 6. 目录说明

- `main.py`：CLI 入口，串联解析/求解/验证/渲染。
- `plan_engine/`：核心模块（dsl、solver、validator、renderer 等）。
- `tmp/`：示例 spec 与运行产物目录。
- `local-dev/`：需求文档、反馈与重构计划。
