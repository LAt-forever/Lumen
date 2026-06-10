# Lumen Phase 1.6: 记忆图谱可视化设计

> 状态：设计已确认，待实现
> 日期：2026-06-10
> 前置：Phase 1.5（标签/收藏/全局搜索）、Phase 1.7（多格式接入）已合并入 main

## 概述

将现有"以单条记忆为中心的局部子图"升级为**增量探索式的记忆网络可视化**。用户从关系密集的枢纽记忆出发，点击展开邻居逐步探索网络，支持缩放/平移/拖拽、按记忆类型/关系类型/关系强度过滤、搜索跳转到任意记忆。

对照原始设计的 "Later Lumen Target"，本期实现 memory graph 从"Lightweight graph model"到"Full graph visualization"的演进。

## 范围

### 本期实现（Phase 1.6）

- 增量探索：枢纽起点 → 双击节点展开邻居 → 节点集合累积
- React Flow 渲染 + d3-force 实时力导向布局
- 交互：缩放、平移、拖拽节点、minimap、节点选中、双击展开/收起
- 基础过滤（纯客户端）：按记忆类型(A)、关系类型(B)、关系强度(C)
- 搜索框跳转到任意记忆作为新探索起点

### 不在本期范围（留后续）

- 画布上拖拽连线建关系（关系管理增强 → Phase 1.6.1）
- 标签过滤（→ 后续，需后端记忆-标签关联）
- 视图状态持久化（记住上次探索的节点集合）

## 现状盘点（起点）

**后端已有：**
- `GET /api/memories/{id}/graph?depth=N` — BFS 构建以某记忆为中心的子图（max_nodes=50）
- 节点 `MemoryGraphNode`：id/text/memory_type/status
- 边 `MemoryGraphEdge`：id/source_memory_id/target_memory_id/relation_type/provenance/strength/status
- `MemoryGraphRead`：center_memory_id/nodes/edges
- 完整关系 CRUD：list/create/forget relations，去重建议提升为关系

**前端已有：**
- `MemoryGraph.tsx`（170行）：手写 O(n²) 力导向布局 + 原生 SVG，圆形节点、箭头边、hover tooltip
- `MemoryGraphPanel.tsx`：中心记忆下拉选择 + 深度选择 + 关系编辑器（下拉框建关系）

**升级动机：** 手写布局 O(n²) 在累积节点后卡顿；缺少缩放/平移/拖拽等探索必需交互；"切换中心即重置"不符合增量探索心智。

## 新增依赖

- `@xyflow/react`（React Flow，MIT）— 图渲染、缩放/平移/拖拽、minimap
- `d3-force`（BSD）— 力导向布局坐标计算

## 架构

### 单元边界

**后端**（改动轻量）：
- `service/api/memories.py` — 新增枢纽起点端点
- `service/core/memory.py` — 新增 `build_hub_graph`
- `service/repositories/memories.py` — 新增 `top_memories_by_relation_count`
- 现有 graph/relations API 完全不动

**前端**（图谱模块重写）：
- `MemoryGraphPanel.tsx` — 重写为探索容器（状态管理）
- `MemoryGraphCanvas.tsx` — 新增，React Flow 画布
- `MemoryNode.tsx` — 新增，自定义节点组件
- `GraphFilterPanel.tsx` — 新增，过滤面板
- `GraphToolbar.tsx` — 新增，搜索 + 重置
- `useGraphLayout.ts` — 新增 hook，封装 d3-force
- `MemoryGraph.tsx` — 删除（被 Canvas 替代）

## 后端设计

### 新增端点

```
GET /api/memories/graph/hubs?limit=5
→ MemoryGraphRead
```

返回关系数最多的 top-N 条 active 记忆及它们之间的关系，作为初始探索图。复用现有 `MemoryGraphRead` 结构，无需新 schema。

> 路由注册注意：`/graph/hubs` 是静态路径，必须注册在 `/{memory_id}/graph` 等含路径参数的路由**之前**，否则 FastAPI 可能把 `graph` 当作 `memory_id` 匹配。实现时确认路由顺序。

### MemoryService.build_hub_graph(limit=5)

1. 调用 `top_memories_by_relation_count(limit)` 取关系数 top-N 的 active 记忆
2. 这些记忆作为节点（构造 `MemoryGraphNode`）
3. 补充这些节点**两两之间**已存在的 active 关系作为边
4. 回退：若库中无任何关系，返回最近创建的 N 条 active 记忆作为孤立节点（无边），保证首屏不空
5. `center_memory_id` 填 top-1 枢纽记忆 id（仅兼容 schema，前端不依赖它高亮）

active 状态定义沿用现有：`{"active", "edited"}`。

### MemoryRepository.top_memories_by_relation_count(limit)

一条 SQL 聚合查询：统计每条 active 记忆作为 source 或 target 的 active 关系数，按计数降序取 top-N，返回记忆 id 列表（或记忆对象）。

### 展开节点复用现有端点

点击展开邻居时，前端调用现有 `GET /memories/{id}/graph?depth=1` 取直接邻居，无需新端点。

## 前端设计

### 组件层次

```
MemoryGraphPanel (探索容器，状态管理)
├── GraphToolbar      (搜索框 + 重置按钮)
├── GraphFilterPanel  (类型/关系/强度过滤器)
└── MemoryGraphCanvas (React Flow 画布)
    └── MemoryNode    (自定义节点：文本+类型色)
```

### 核心状态（MemoryGraphPanel）

- `expandedGraph` — 累积的节点 + 边全集（探索状态的真相源），用 Map 按 id 存储
- `expandedNodeIds` — 已展开过邻居的节点 id 集合（用于节点视觉标记和收起判断）
- `filters` — `{ memoryTypes: Set<string>, relationTypes: Set<string>, minStrength: number }`
- `selectedNodeId` — 当前选中节点（高亮 + 详情展示）

### 数据流

1. **初始化**：进页面 → `useHubGraph()` 拉枢纽图 → 写入 `expandedGraph`
2. **展开节点**：双击节点 → `useMemoryGraph(nodeId, depth=1)` 拉邻居 → 按 id 去重合并进 `expandedGraph` → 将该节点加入 `expandedNodeIds`
3. **收起节点**：双击已展开节点 → 移除"仅由该节点引入且不连接其他展开节点"的邻居 → 从 `expandedNodeIds` 移除
4. **过滤**：`filters` 变化 → 纯客户端派生 `visibleNodes/visibleEdges`（不请求后端）
5. **布局**：`visibleNodes/visibleEdges` → `useGraphLayout`(d3-force) → 带 x/y 的节点 → React Flow 渲染
6. **搜索跳转**：搜索框选记忆 → 以该记忆为新起点 `useMemoryGraph(id, depth=1)` 展开（合并进现有图）

### 关键设计点

- `expandedGraph` 存全集，过滤只影响可见性（visible 为派生值），取消过滤无需重新请求
- 合并用 Map 按 id 去重，重复展开不产生重复节点/边

## d3-force 布局 Hook（技术核心）

`useGraphLayout` 把 React Flow 渲染和 d3 布局解耦。

### 接口

```typescript
useGraphLayout(nodes, edges, options) → {
  layoutNodes: Array<{ id, x, y, ...data }>,
  onNodeDragStart, onNodeDrag, onNodeDragStop,
}
```

### 力配置

- `forceManyBody`（斥力，Barnes-Hut θ≈0.9，O(n log n)）— 节点互相推开
- `forceLink`（边吸引，距离按 strength 反比，强关系更近）— 连接节点靠拢
- `forceCenter` — 整体居中
- `forceCollide` — 防节点重叠

### 生命周期管理（关键）

- 模拟实例存 `useRef`，不随渲染重建
- nodes/edges 变化时：**保留已有节点当前坐标**（不重置），仅为新增节点设初始位置（放在引入它的父节点附近），重启模拟用低 alpha 让其平滑融入 → 实现"增量展开平滑过渡"
- `simulation.on('tick')` 更新坐标，throttle 到 React 状态（避免每帧 setState）
- 组件卸载 / alpha 衰减到阈值 → `simulation.stop()` 释放
- 拖拽：drag 时设 `fx/fy` 固定节点，dragStop 释放（或保持固定）
- NaN 坐标兜底：检测到异常坐标重置为画布中心附近

### 为何独立成 hook

布局算法与渲染完全隔离 —— 换布局引擎或调力参数只改此 hook，画布组件不动。便于单测（给定 nodes/edges，跑固定 tick 数断言坐标收敛）。

## 过滤、交互与样式

### 过滤面板（A+B+C，纯客户端）

- **记忆类型**（A）：7 种多选 checkbox（preference/fact/project/relationship/goal/event/note），默认全选，每种类型对应一个颜色
- **关系类型**（B）：5 种多选 checkbox（related_to/part_of/caused_by/supports/contradicts），默认全选
- **关系强度**（C）：滑块 0-100，只显示 strength ≥ 阈值的边，默认 0
- **过滤语义**：隐藏不匹配类型的节点；隐藏不匹配类型或低于强度阈值的边；边的任一端节点被隐藏时该边也隐藏

### 节点样式（MemoryNode）

- 圆角节点，填充色按 memory_type 区分
- 显示截断文本（前 20 字）
- 已展开节点加视觉标记（实心边框）；未展开节点加"可展开"提示（虚线边框或 + 号）
- 选中节点高亮（描边加粗）

### 边样式

- 颜色/线型按 relation_type 区分，复用现有中文映射 `relationLabels`
- 箭头表方向（有向关系如 part_of/caused_by）
- hover 显示 tooltip：关系类型 + 强度

### 交互汇总

- **单击节点** → 选中 + 显示详情（该记忆完整文本/类型/关系列表，只读）
- **双击节点** → 展开/收起邻居
- **拖拽节点** → 移动并固定位置
- **滚轮缩放、拖拽平移、minimap 导航** — React Flow 内置
- **工具栏**：搜索框跳转到任意记忆、"重置视图"回到枢纽起点

### 详情展示

选中节点时复用现有关系列表 UI，显示该记忆的关系（本期只读，画布拖拽建关系留 1.6.1）。

## 错误处理

- 枢纽图请求失败 → 错误提示 + 重试按钮
- 展开节点请求失败 → toast 提示，不破坏已有图
- 空记忆库 → 友好空状态"还没有记忆，去添加一些资料吧"
- 可见节点过多（>200）→ 提示用过滤器收窄，避免布局卡顿
- d3-force 异常坐标（NaN）→ 兜底重置为画布中心附近

## 测试策略

### 后端测试

- `test_build_hub_graph` — 有关系的记忆集，断言返回关系数 top-N 节点 + 它们之间的边
- `test_hub_graph_empty_relations_fallback` — 无关系时回退返回最近 N 条孤立节点
- `test_hub_graph_excludes_forgotten` — forgotten/merged 记忆不出现
- `test_top_memories_by_relation_count` — Repository 聚合查询正确性

### 前端测试

- `useGraphLayout` — 固定 nodes/edges 跑确定 tick 数，断言坐标收敛、无 NaN、新增节点位置在父节点附近
- 合并逻辑 — 重复展开同一节点不产生重复 nodes/edges
- 过滤逻辑 — 给定 filters 和全集，断言 visibleNodes/visibleEdges 正确（类型过滤、强度阈值、孤立边隐藏）
- 收起逻辑 — 收起节点时保留仍连着其他展开节点的邻居
- 组件渲染 — 枢纽图加载、空状态、节点过多提示

### Mock 策略

React Flow 在 jsdom 下需 mock（依赖真实 DOM 尺寸），测试聚焦数据逻辑（布局/合并/过滤）而非画布像素渲染。

### 验证

后端 `pytest`、前端 `vitest`、前端 `npm run build` 全部通过。

## 验收标准

Phase 1.6 完成的标志：

- 进入图谱页展示关系密集的枢纽记忆作为探索起点
- 双击节点能展开其邻居并平滑融入现有图，节点集合累积不重置
- 双击已展开节点能收起邻居（保留仍连接其他展开节点的）
- 支持缩放、平移、拖拽节点、minimap 导航
- 按记忆类型/关系类型/关系强度过滤，纯客户端即时生效，取消过滤无需重新请求
- 搜索框可跳转到任意记忆作为探索起点
- 单击节点显示其详情和关系列表（只读）
- 空记忆库、请求失败、节点过多有友好提示
- 后端测试通过、前端测试通过、前端生产构建成功

## 后续扩展（非本期）

- Phase 1.6.1：画布上拖拽连线建关系、批量编辑、可视化修复重复/矛盾记忆
- 标签过滤（需后端记忆-标签关联查询）
- 视图状态持久化
- 图查询（"X 和 Y 之间的最短关系路径"等）
