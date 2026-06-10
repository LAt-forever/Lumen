# Phase 1.6: 记忆图谱可视化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将记忆图谱从"单中心局部子图"升级为增量探索式网络可视化，支持枢纽起点、双击展开邻居、缩放/平移/拖拽、按类型/强度过滤。

**Architecture:** 后端新增一个"枢纽起点"聚合查询端点，复用现有 graph/relations API。前端用 React Flow 渲染 + d3-force 实时力导向布局，状态层维护"累积全集 + 派生可见性"模型，展开节点时平滑融入。

**Tech Stack:** FastAPI + SQLAlchemy + Pytest（后端）；React + TypeScript + TanStack Query + Vitest（前端）；@xyflow/react、d3-force（新增前端依赖）。

---

## File Structure

### 后端

| File | 改动 | 责任 |
|---|---|---|
| `backend/service/repositories/memories.py` | 修改 | 新增 `top_memories_by_relation_count(limit)` 聚合查询 |
| `backend/service/core/memory.py` | 修改 | 新增 `build_hub_graph(limit)` |
| `backend/service/api/memories.py` | 修改 | 新增 `GET /graph/hubs` 端点（注册在 `/{memory_id}/graph` 之前）|
| `backend/tests/test_graph.py` | 修改 | 新增枢纽图测试 |

### 前端

| File | 改动 | 责任 |
|---|---|---|
| `frontend/package.json` | 修改 | 加 `@xyflow/react`、`d3-force` 依赖 |
| `frontend/src/api/client.ts` | 修改 | 加 `memoryHubGraph()` |
| `frontend/src/api/hooks.ts` | 修改 | 加 `useHubGraph()` |
| `frontend/src/api/types.ts` | 修改 | 复用 `MemoryGraphRead`（无新类型）|
| `frontend/src/graph/mergeGraph.ts` | 新建 | 图合并/收起纯函数 |
| `frontend/src/graph/filterGraph.ts` | 新建 | 过滤派生可见性纯函数 |
| `frontend/src/graph/useGraphLayout.ts` | 新建 | d3-force 布局 hook |
| `frontend/src/components/MemoryNode.tsx` | 新建 | React Flow 自定义节点 |
| `frontend/src/components/GraphFilterPanel.tsx` | 新建 | 过滤面板 |
| `frontend/src/components/GraphToolbar.tsx` | 新建 | 搜索 + 重置工具栏 |
| `frontend/src/components/MemoryGraphCanvas.tsx` | 新建 | React Flow 画布封装 |
| `frontend/src/components/MemoryGraphPanel.tsx` | 重写 | 探索容器 + 状态管理 |
| `frontend/src/components/MemoryGraph.tsx` | 删除 | 被 Canvas 替代 |

---

## Task 1: 后端枢纽图查询与端点

**Files:**
- Modify: `backend/service/repositories/memories.py`
- Modify: `backend/service/core/memory.py`
- Modify: `backend/service/api/memories.py`
- Test: `backend/tests/test_graph.py`

### Step 1: 写枢纽图的失败测试

在 `backend/tests/test_graph.py` 末尾追加（复用文件顶部已有的 `make_service` 辅助函数）：

```python
def test_hub_graph_returns_top_connected_memories():
    service = make_service()
    candidates = [
        service.extract_candidates(f"我喜欢 memory {i}。", source_kind="message", source_ref=str(i))[0]
        for i in range(4)
    ]
    a, b, c, d = [service.confirm(x.id) for x in candidates]
    # a 连 b、c、d（3条）；b 连 c（1条）
    service.create_relation(a.id, b.id, relation_type="related_to")
    service.create_relation(a.id, c.id, relation_type="related_to")
    service.create_relation(a.id, d.id, relation_type="related_to")
    service.create_relation(b.id, c.id, relation_type="related_to")

    graph = service.build_hub_graph(limit=2)
    # top-2 枢纽应为 a(度3) 和 b 或 c(度2)
    assert a.id in {n.id for n in graph.nodes}
    assert len(graph.nodes) == 2
    # 只保留两个枢纽节点之间已存在的边
    for edge in graph.edges:
        assert edge.source_memory_id in {n.id for n in graph.nodes}
        assert edge.target_memory_id in {n.id for n in graph.nodes}


def test_hub_graph_empty_relations_fallback():
    service = make_service()
    candidates = [
        service.extract_candidates(f"孤立记忆 {i}。", source_kind="message", source_ref=str(i))[0]
        for i in range(3)
    ]
    [service.confirm(x.id) for x in candidates]
    # 无任何关系
    graph = service.build_hub_graph(limit=5)
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 0


def test_hub_graph_excludes_forgotten():
    service = make_service()
    candidates = [
        service.extract_candidates(f"记忆 {i}。", source_kind="message", source_ref=str(i))[0]
        for i in range(3)
    ]
    a, b, c = [service.confirm(x.id) for x in candidates]
    service.create_relation(a.id, b.id, relation_type="related_to")
    service.create_relation(a.id, c.id, relation_type="related_to")
    service.forget(a.id)
    graph = service.build_hub_graph(limit=5)
    assert a.id not in {n.id for n in graph.nodes}
```

### Step 2: 运行测试确认失败

Run: `cd backend && uv run pytest tests/test_graph.py::test_hub_graph_returns_top_connected_memories -v`
Expected: FAIL，`AttributeError: 'MemoryService' object has no attribute 'build_hub_graph'`

### Step 3: 加 Repository 聚合查询

在 `backend/service/repositories/memories.py` 的 `MemoryRepository` 类中，`list_active_relations` 方法之后添加。文件顶部确保有 `from sqlalchemy import func, select, or_`（检查现有 import，缺什么加什么）：

```python
    def top_memories_by_relation_count(self, limit: int) -> list[Memory]:
        active_statuses = ("active", "edited")
        # 统计每个 memory_id 作为 source 或 target 出现在 active 关系中的次数
        rel = MemoryRelation
        endpoint_ids = (
            select(rel.source_memory_id.label("mid"))
            .where(rel.status == "active")
            .union_all(
                select(rel.target_memory_id.label("mid")).where(rel.status == "active")
            )
            .subquery()
        )
        counts = (
            select(endpoint_ids.c.mid, func.count().label("deg"))
            .group_by(endpoint_ids.c.mid)
            .subquery()
        )
        stmt = (
            select(Memory)
            .join(counts, counts.c.mid == Memory.id)
            .where(Memory.status.in_(active_statuses))
            .order_by(counts.c.deg.desc(), Memory.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def recent_active_memories(self, limit: int) -> list[Memory]:
        active_statuses = ("active", "edited")
        stmt = (
            select(Memory)
            .where(Memory.status.in_(active_statuses))
            .order_by(Memory.created_at.desc(), Memory.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())
```

确保文件顶部 import 含 `MemoryRelation` 和 `Memory`（检查现有 import）。

### Step 4: 加 Service 方法 build_hub_graph

在 `backend/service/core/memory.py` 的 `MemoryService` 类中，`build_memory_graph` 方法之后添加。复用文件已 import 的 `MemoryGraphNode`、`MemoryGraphEdge`、`MemoryGraphRead`：

```python
    def build_hub_graph(self, limit: int = 5) -> MemoryGraphRead:
        active_statuses = {"active", "edited"}
        hubs = self.memories.top_memories_by_relation_count(limit)

        if not hubs:
            # 回退：返回最近的 active 记忆作为孤立节点
            recent = self.memories.recent_active_memories(limit)
            nodes = [
                MemoryGraphNode(id=m.id, text=m.text, memory_type=m.memory_type, status=m.status)
                for m in recent
            ]
            center_id = nodes[0].id if nodes else 0
            return MemoryGraphRead(center_memory_id=center_id, nodes=nodes, edges=[])

        hub_ids = {m.id for m in hubs}
        nodes = [
            MemoryGraphNode(id=m.id, text=m.text, memory_type=m.memory_type, status=m.status)
            for m in hubs
        ]

        # 补充枢纽节点两两之间的 active 关系作为边
        edges: dict[int, MemoryGraphEdge] = {}
        for hub_id in hub_ids:
            for relation in self.memories.list_relations_for_memory(hub_id):
                if relation.status != "active":
                    continue
                if relation.source_memory_id in hub_ids and relation.target_memory_id in hub_ids:
                    if relation.id not in edges:
                        edges[relation.id] = MemoryGraphEdge(
                            id=relation.id,
                            source_memory_id=relation.source_memory_id,
                            target_memory_id=relation.target_memory_id,
                            relation_type=relation.relation_type,
                            provenance=relation.provenance,
                            strength=relation.strength,
                            status=relation.status,
                        )

        return MemoryGraphRead(
            center_memory_id=hubs[0].id,
            nodes=nodes,
            edges=list(edges.values()),
        )
```

### Step 5: 运行测试确认通过

Run: `cd backend && uv run pytest tests/test_graph.py -v`
Expected: 3 个新测试 PASS，原有测试不破坏

### Step 6: 加 API 端点（注意路由顺序）

在 `backend/service/api/memories.py` 中，**在 `@router.get("/{memory_id}/graph", ...)` 之前**（静态路径必须先于路径参数路由）添加。先确认 import 含 `MemoryGraphRead`：

```python
@router.get("/graph/hubs", response_model=MemoryGraphRead)
def memory_hub_graph(limit: int = 5, db: Session = Depends(get_db)):
    service = MemoryService(MemoryRepository(db))
    return service.build_hub_graph(limit=limit)
```

如果 `@router.get("/{memory_id}/graph")` 已经在文件较后位置，把新端点放在它前面任意位置即可（例如紧接 `@router.get("/duplicate-suggestions", ...)` 之后）。

### Step 7: 写端点集成测试

在 `backend/tests/test_graph.py` 末尾追加。`client` fixture 用空库启动，枢纽端点应返回空图（验证路由可达且空库不报 500）。建关系的完整逻辑已由上面的 service 层测试覆盖：

```python
def test_hub_graph_endpoint_empty(client):
    response = client.get("/api/memories/graph/hubs?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["nodes"] == []
    assert data["edges"] == []
```

### Step 8: 运行全部后端测试

Run: `cd backend && uv run pytest tests/ -q`
Expected: 全部 PASS（含 1 个 skip 的 tesseract 测试）

### Step 9: 提交

```bash
git add backend/service/repositories/memories.py backend/service/core/memory.py backend/service/api/memories.py backend/tests/test_graph.py
git commit -m "feat(memory): add hub graph endpoint for graph exploration entry point"
```

---

## Task 2: 前端依赖与 API 接入

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/hooks.ts`

### Step 1: 安装依赖

Run: `cd frontend && npm install @xyflow/react d3-force && npm install -D @types/d3-force`
Expected: 三个包写入 package.json，安装成功

### Step 2: 加 API client 方法

在 `frontend/src/api/client.ts` 中，紧接现有 `memoryGraph` 方法之后添加：

```typescript
  memoryHubGraph: (limit = 5) =>
    request<MemoryGraphRead>(`/api/memories/graph/hubs?limit=${limit}`),
```

`MemoryGraphRead` 已在文件顶部 import，无需改 import。

### Step 3: 加 useHubGraph hook

在 `frontend/src/api/hooks.ts` 中，紧接现有 `useMemoryGraph` 之后添加：

```typescript
export function useHubGraph(limit = 5) {
  return useQuery<MemoryGraphRead>({
    queryKey: ['memory-hub-graph', limit],
    queryFn: () => api.memoryHubGraph(limit),
  })
}
```

确认 `MemoryGraphRead` 已在 hooks.ts 顶部 import（现有 `useMemoryGraph` 已用到，应已 import）。

### Step 4: 验证编译

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误

### Step 5: 提交

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/api/client.ts frontend/src/api/hooks.ts
git commit -m "feat(graph): add React Flow + d3-force deps and hub graph API client"
```

---

## Task 3: 图合并与收起纯函数

**Files:**
- Create: `frontend/src/graph/mergeGraph.ts`
- Test: `frontend/src/graph/mergeGraph.test.ts`

### Step 1: 写失败测试

Create `frontend/src/graph/mergeGraph.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'

import type { MemoryGraphRead } from '../api/types'
import { collapseNode, mergeGraphs } from './mergeGraph'

const node = (id: number) => ({ id, text: `m${id}`, memory_type: 'fact', status: 'active' })
const edge = (id: number, s: number, t: number) => ({
  id,
  source_memory_id: s,
  target_memory_id: t,
  relation_type: 'related_to' as const,
  provenance: 'user',
  strength: 70,
  status: 'active',
})

const graph = (nodes: number[], edges: [number, number, number][]): MemoryGraphRead => ({
  center_memory_id: nodes[0] ?? 0,
  nodes: nodes.map(node),
  edges: edges.map(([id, s, t]) => edge(id, s, t)),
})

describe('mergeGraphs', () => {
  it('合并去重节点和边', () => {
    const base = graph([1, 2], [[10, 1, 2]])
    const incoming = graph([2, 3], [[10, 1, 2], [11, 2, 3]])
    const result = mergeGraphs(base, incoming)
    expect(result.nodes.map((n) => n.id).sort()).toEqual([1, 2, 3])
    expect(result.edges.map((e) => e.id).sort()).toEqual([10, 11])
  })
})

describe('collapseNode', () => {
  it('移除仅由该节点引入且不连接其他展开节点的邻居', () => {
    // 1(展开) 连 2、3；收起 1 后，2、3 应移除（它们只连 1）
    const current = graph([1, 2, 3], [[10, 1, 2], [11, 1, 3]])
    const expandedIds = new Set([1])
    const result = collapseNode(current, 1, expandedIds)
    expect(result.nodes.map((n) => n.id)).toEqual([1])
    expect(result.edges).toEqual([])
  })

  it('保留仍连接其他展开节点的邻居', () => {
    // 1、4 都展开，2 同时连 1 和 4；收起 1 后 2 应保留（仍连 4）
    const current = graph([1, 2, 4], [[10, 1, 2], [12, 4, 2]])
    const expandedIds = new Set([1, 4])
    const result = collapseNode(current, 1, expandedIds)
    expect(result.nodes.map((n) => n.id).sort()).toEqual([1, 2, 4])
  })
})
```

### Step 2: 运行测试确认失败

Run: `cd frontend && npx vitest run src/graph/mergeGraph.test.ts`
Expected: FAIL，找不到 `./mergeGraph` 模块

### Step 3: 实现合并/收起函数

Create `frontend/src/graph/mergeGraph.ts`:

```typescript
import type { MemoryGraphEdge, MemoryGraphNode, MemoryGraphRead } from '../api/types'

export function mergeGraphs(base: MemoryGraphRead, incoming: MemoryGraphRead): MemoryGraphRead {
  const nodeMap = new Map<number, MemoryGraphNode>()
  for (const n of base.nodes) nodeMap.set(n.id, n)
  for (const n of incoming.nodes) nodeMap.set(n.id, n)

  const edgeMap = new Map<number, MemoryGraphEdge>()
  for (const e of base.edges) edgeMap.set(e.id, e)
  for (const e of incoming.edges) edgeMap.set(e.id, e)

  return {
    center_memory_id: base.center_memory_id,
    nodes: Array.from(nodeMap.values()),
    edges: Array.from(edgeMap.values()),
  }
}

export function collapseNode(
  current: MemoryGraphRead,
  collapseId: number,
  expandedIds: Set<number>,
): MemoryGraphRead {
  const remainingExpanded = new Set(expandedIds)
  remainingExpanded.delete(collapseId)

  // 一个节点保留的条件：它是 collapseId 本身，或是仍被展开的节点，
  // 或它与某个仍被展开的节点（或 collapseId 以外的保留节点）有边相连。
  // 简化规则：保留 collapseId、所有仍展开节点，以及与任一仍展开节点相连的节点。
  const keep = new Set<number>([collapseId, ...remainingExpanded])

  for (const edge of current.edges) {
    const { source_memory_id: s, target_memory_id: t } = edge
    if (remainingExpanded.has(s)) keep.add(t)
    if (remainingExpanded.has(t)) keep.add(s)
  }

  const nodes = current.nodes.filter((n) => keep.has(n.id))
  const keptIds = new Set(nodes.map((n) => n.id))
  const edges = current.edges.filter(
    (e) => keptIds.has(e.source_memory_id) && keptIds.has(e.target_memory_id),
  )

  return { center_memory_id: current.center_memory_id, nodes, edges }
}
```

### Step 4: 运行测试确认通过

Run: `cd frontend && npx vitest run src/graph/mergeGraph.test.ts`
Expected: 所有测试 PASS

### Step 5: 提交

```bash
git add frontend/src/graph/mergeGraph.ts frontend/src/graph/mergeGraph.test.ts
git commit -m "feat(graph): add graph merge and collapse pure functions"
```

---

## Task 4: 过滤派生纯函数

**Files:**
- Create: `frontend/src/graph/filterGraph.ts`
- Test: `frontend/src/graph/filterGraph.test.ts`

### Step 1: 写失败测试

Create `frontend/src/graph/filterGraph.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'

import type { MemoryGraphRead } from '../api/types'
import { applyFilters, type GraphFilters } from './filterGraph'

const fullGraph: MemoryGraphRead = {
  center_memory_id: 1,
  nodes: [
    { id: 1, text: 'a', memory_type: 'fact', status: 'active' },
    { id: 2, text: 'b', memory_type: 'goal', status: 'active' },
    { id: 3, text: 'c', memory_type: 'fact', status: 'active' },
  ],
  edges: [
    { id: 10, source_memory_id: 1, target_memory_id: 2, relation_type: 'related_to', provenance: 'user', strength: 80, status: 'active' },
    { id: 11, source_memory_id: 1, target_memory_id: 3, relation_type: 'supports', provenance: 'user', strength: 40, status: 'active' },
  ],
}

const allTypes = new Set(['fact', 'goal'])
const allRelations = new Set(['related_to', 'supports'])

describe('applyFilters', () => {
  it('默认全选 + 强度0：返回全集', () => {
    const filters: GraphFilters = { memoryTypes: allTypes, relationTypes: allRelations, minStrength: 0 }
    const result = applyFilters(fullGraph, filters)
    expect(result.nodes).toHaveLength(3)
    expect(result.edges).toHaveLength(2)
  })

  it('按记忆类型过滤：隐藏 goal 节点及其边', () => {
    const filters: GraphFilters = { memoryTypes: new Set(['fact']), relationTypes: allRelations, minStrength: 0 }
    const result = applyFilters(fullGraph, filters)
    expect(result.nodes.map((n) => n.id).sort()).toEqual([1, 3])
    expect(result.edges.map((e) => e.id)).toEqual([11])
  })

  it('按关系强度过滤：隐藏 strength<50 的边', () => {
    const filters: GraphFilters = { memoryTypes: allTypes, relationTypes: allRelations, minStrength: 50 }
    const result = applyFilters(fullGraph, filters)
    expect(result.edges.map((e) => e.id)).toEqual([10])
    expect(result.nodes).toHaveLength(3)
  })

  it('按关系类型过滤：只显示 related_to', () => {
    const filters: GraphFilters = { memoryTypes: allTypes, relationTypes: new Set(['related_to']), minStrength: 0 }
    const result = applyFilters(fullGraph, filters)
    expect(result.edges.map((e) => e.id)).toEqual([10])
  })
})
```

### Step 2: 运行测试确认失败

Run: `cd frontend && npx vitest run src/graph/filterGraph.test.ts`
Expected: FAIL，找不到 `./filterGraph`

### Step 3: 实现过滤函数

Create `frontend/src/graph/filterGraph.ts`:

```typescript
import type { MemoryGraphRead } from '../api/types'

export type GraphFilters = {
  memoryTypes: Set<string>
  relationTypes: Set<string>
  minStrength: number
}

export function applyFilters(graph: MemoryGraphRead, filters: GraphFilters): MemoryGraphRead {
  const nodes = graph.nodes.filter((n) => filters.memoryTypes.has(n.memory_type))
  const visibleNodeIds = new Set(nodes.map((n) => n.id))

  const edges = graph.edges.filter(
    (e) =>
      filters.relationTypes.has(e.relation_type) &&
      e.strength >= filters.minStrength &&
      visibleNodeIds.has(e.source_memory_id) &&
      visibleNodeIds.has(e.target_memory_id),
  )

  return { center_memory_id: graph.center_memory_id, nodes, edges }
}
```

### Step 4: 运行测试确认通过

Run: `cd frontend && npx vitest run src/graph/filterGraph.test.ts`
Expected: 所有测试 PASS

### Step 5: 提交

```bash
git add frontend/src/graph/filterGraph.ts frontend/src/graph/filterGraph.test.ts
git commit -m "feat(graph): add client-side filter derivation pure function"
```

---

## Task 5: d3-force 布局计算

**Files:**
- Create: `frontend/src/graph/useGraphLayout.ts`
- Test: `frontend/src/graph/useGraphLayout.test.ts`

### Step 1: 写失败测试

Create `frontend/src/graph/useGraphLayout.test.ts`:

```typescript
import { describe, expect, it } from 'vitest'

import type { MemoryGraphEdge, MemoryGraphNode } from '../api/types'
import { computeLayout } from './useGraphLayout'

const nodes: MemoryGraphNode[] = [
  { id: 1, text: 'a', memory_type: 'fact', status: 'active' },
  { id: 2, text: 'b', memory_type: 'goal', status: 'active' },
  { id: 3, text: 'c', memory_type: 'fact', status: 'active' },
]
const edges: MemoryGraphEdge[] = [
  { id: 10, source_memory_id: 1, target_memory_id: 2, relation_type: 'related_to', provenance: 'user', strength: 70, status: 'active' },
]

describe('computeLayout', () => {
  it('为每个节点产出有限的 x/y 坐标', () => {
    const result = computeLayout(nodes, edges, { width: 800, height: 600, iterations: 100 })
    expect(result).toHaveLength(3)
    for (const n of result) {
      expect(Number.isFinite(n.x)).toBe(true)
      expect(Number.isFinite(n.y)).toBe(true)
    }
  })

  it('保留已有节点的传入坐标作为初始值', () => {
    const seeded = computeLayout(nodes, edges, {
      width: 800,
      height: 600,
      iterations: 0,
      initialPositions: { 1: { x: 123, y: 456 } },
    })
    const n1 = seeded.find((n) => n.id === 1)!
    expect(n1.x).toBe(123)
    expect(n1.y).toBe(456)
  })

  it('空输入返回空数组', () => {
    expect(computeLayout([], [], { width: 800, height: 600, iterations: 10 })).toEqual([])
  })
})
```

### Step 2: 运行测试确认失败

Run: `cd frontend && npx vitest run src/graph/useGraphLayout.test.ts`
Expected: FAIL，找不到 `./useGraphLayout`

### Step 3: 实现布局

Create `frontend/src/graph/useGraphLayout.ts`:

```typescript
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from 'd3-force'

import type { MemoryGraphEdge, MemoryGraphNode } from '../api/types'

export type LayoutNode = MemoryGraphNode & { x: number; y: number }

type SimNode = SimulationNodeDatum & { id: number }
type SimLink = SimulationLinkDatum<SimNode> & { strength: number }

export type ComputeLayoutOptions = {
  width: number
  height: number
  iterations?: number
  initialPositions?: Record<number, { x: number; y: number }>
}

export function computeLayout(
  nodes: MemoryGraphNode[],
  edges: MemoryGraphEdge[],
  options: ComputeLayoutOptions,
): LayoutNode[] {
  if (nodes.length === 0) return []
  const { width, height, iterations = 120, initialPositions = {} } = options

  const simNodes: SimNode[] = nodes.map((n, index) => {
    const seed = initialPositions[n.id]
    return {
      id: n.id,
      x: seed?.x ?? width / 2 + Math.cos((index / nodes.length) * Math.PI * 2) * 80,
      y: seed?.y ?? height / 2 + Math.sin((index / nodes.length) * Math.PI * 2) * 80,
    }
  })

  const nodeById = new Map(simNodes.map((n) => [n.id, n]))
  const simLinks: SimLink[] = edges
    .filter((e) => nodeById.has(e.source_memory_id) && nodeById.has(e.target_memory_id))
    .map((e) => ({ source: e.source_memory_id, target: e.target_memory_id, strength: e.strength }))

  const simulation = forceSimulation(simNodes)
    .force('charge', forceManyBody().strength(-300).theta(0.9))
    .force(
      'link',
      forceLink<SimNode, SimLink>(simLinks)
        .id((d) => d.id)
        .distance((l) => 160 - (l.strength / 100) * 80)
        .strength(0.3),
    )
    .force('center', forceCenter(width / 2, height / 2))
    .force('collide', forceCollide(28))
    .stop()

  for (let i = 0; i < iterations; i++) {
    simulation.tick()
  }

  return nodes.map((n) => {
    const sim = nodeById.get(n.id)!
    const x = Number.isFinite(sim.x) ? (sim.x as number) : width / 2
    const y = Number.isFinite(sim.y) ? (sim.y as number) : height / 2
    return { ...n, x, y }
  })
}
```

> 说明：本期用同步 `computeLayout`（跑固定迭代取最终坐标）作为布局核心，便于单测且足够流畅。"增量平滑过渡"通过 `initialPositions` 传入已有节点当前坐标实现 —— 已有节点从原位起算，新节点从环形种子起算，重算后位置变化小。React Flow 负责拖拽/缩放/平移交互层。

### Step 4: 运行测试确认通过

Run: `cd frontend && npx vitest run src/graph/useGraphLayout.test.ts`
Expected: 所有测试 PASS

### Step 5: 提交

```bash
git add frontend/src/graph/useGraphLayout.ts frontend/src/graph/useGraphLayout.test.ts
git commit -m "feat(graph): add d3-force layout computation"
```

---

## Task 6: UI 组件 — 节点、过滤面板、工具栏

**Files:**
- Create: `frontend/src/components/MemoryNode.tsx`
- Create: `frontend/src/components/GraphFilterPanel.tsx`
- Create: `frontend/src/components/GraphToolbar.tsx`

### Step 1: 创建自定义节点 MemoryNode

Create `frontend/src/components/MemoryNode.tsx`:

```typescript
import { Handle, Position } from '@xyflow/react'

export type MemoryNodeData = {
  label: string
  memoryType: string
  expanded: boolean
  selected: boolean
}

const typeColors: Record<string, string> = {
  preference: '#8b5cf6',
  fact: '#3b82f6',
  project: '#f59e0b',
  relationship: '#ec4899',
  goal: '#10b981',
  event: '#06b6d4',
  note: '#6b7280',
}

export function MemoryNode({ data }: { data: MemoryNodeData }) {
  const color = typeColors[data.memoryType] ?? '#6b7280'
  return (
    <div
      className="memory-node"
      style={{
        background: color,
        border: data.selected ? '3px solid #111' : data.expanded ? '2px solid #fff' : '2px dashed #fff',
        borderRadius: 10,
        padding: '6px 10px',
        color: '#fff',
        fontSize: 12,
        maxWidth: 160,
        cursor: 'pointer',
      }}
      title={data.label}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <span>{data.label.length > 20 ? `${data.label.slice(0, 20)}…` : data.label}</span>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  )
}
```

### Step 2: 创建过滤面板 GraphFilterPanel

Create `frontend/src/components/GraphFilterPanel.tsx`:

```typescript
import type { GraphFilters } from '../graph/filterGraph'

const memoryTypeLabels: Record<string, string> = {
  preference: '偏好',
  fact: '事实',
  project: '项目',
  relationship: '关系',
  goal: '目标',
  event: '事件',
  note: '笔记',
}

const relationTypeLabels: Record<string, string> = {
  related_to: '相关',
  part_of: '属于',
  caused_by: '导致',
  supports: '支持',
  contradicts: '矛盾',
}

type Props = {
  filters: GraphFilters
  onChange: (next: GraphFilters) => void
}

function toggle(set: Set<string>, key: string): Set<string> {
  const next = new Set(set)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  return next
}

export function GraphFilterPanel({ filters, onChange }: Props) {
  return (
    <div className="graph-filter-panel" aria-label="图谱过滤器">
      <fieldset>
        <legend>记忆类型</legend>
        {Object.keys(memoryTypeLabels).map((type) => (
          <label key={type} className="filter-checkbox">
            <input
              type="checkbox"
              checked={filters.memoryTypes.has(type)}
              onChange={() => onChange({ ...filters, memoryTypes: toggle(filters.memoryTypes, type) })}
            />
            {memoryTypeLabels[type]}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>关系类型</legend>
        {Object.keys(relationTypeLabels).map((type) => (
          <label key={type} className="filter-checkbox">
            <input
              type="checkbox"
              checked={filters.relationTypes.has(type)}
              onChange={() => onChange({ ...filters, relationTypes: toggle(filters.relationTypes, type) })}
            />
            {relationTypeLabels[type]}
          </label>
        ))}
      </fieldset>
      <fieldset>
        <legend>最小关系强度: {filters.minStrength}</legend>
        <input
          type="range"
          min={0}
          max={100}
          value={filters.minStrength}
          onChange={(e) => onChange({ ...filters, minStrength: Number(e.target.value) })}
        />
      </fieldset>
    </div>
  )
}

export const ALL_MEMORY_TYPES = Object.keys(memoryTypeLabels)
export const ALL_RELATION_TYPES = Object.keys(relationTypeLabels)
```

### Step 3: 创建工具栏 GraphToolbar

Create `frontend/src/components/GraphToolbar.tsx`:

```typescript
import type { MemoryRead } from '../api/types'

type Props = {
  memories: MemoryRead[]
  onJumpToMemory: (memoryId: number) => void
  onReset: () => void
}

export function GraphToolbar({ memories, onJumpToMemory, onReset }: Props) {
  return (
    <div className="graph-toolbar" aria-label="图谱工具栏">
      <label className="field-label" htmlFor="graph-search">
        跳转到记忆
      </label>
      <select
        id="graph-search"
        defaultValue=""
        onChange={(e) => {
          const id = Number(e.target.value)
          if (id) onJumpToMemory(id)
        }}
      >
        <option value="">选择一条记忆…</option>
        {memories.map((m) => (
          <option key={m.id} value={m.id}>
            #{m.id} {m.text.slice(0, 40)}
          </option>
        ))}
      </select>
      <button type="button" className="secondary" onClick={onReset}>
        重置视图
      </button>
    </div>
  )
}
```

### Step 4: 验证编译

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误

### Step 5: 提交

```bash
git commit -m "feat(graph): add MemoryNode, GraphFilterPanel, GraphToolbar components"
```

---

## Task 7: React Flow 画布 MemoryGraphCanvas

**Files:**
- Create: `frontend/src/components/MemoryGraphCanvas.tsx`

### Step 1: 创建画布组件

Create `frontend/src/components/MemoryGraphCanvas.tsx`:

```typescript
import { useMemo } from 'react'
import {
  Background,
  Controls,
  type Edge,
  MiniMap,
  type Node,
  ReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import type { MemoryGraphRead } from '../api/types'
import { computeLayout } from '../graph/useGraphLayout'
import { MemoryNode } from './MemoryNode'

const nodeTypes = { memory: MemoryNode }

type Props = {
  graph: MemoryGraphRead
  expandedIds: Set<number>
  selectedId: number | null
  prevPositions: Record<number, { x: number; y: number }>
  onNodeClick: (id: number) => void
  onNodeDoubleClick: (id: number) => void
  onPositionsComputed: (positions: Record<number, { x: number; y: number }>) => void
}

const WIDTH = 900
const HEIGHT = 520

export function MemoryGraphCanvas({
  graph,
  expandedIds,
  selectedId,
  prevPositions,
  onNodeClick,
  onNodeDoubleClick,
  onPositionsComputed,
}: Props) {
  const layoutNodes = useMemo(() => {
    const result = computeLayout(graph.nodes, graph.edges, {
      width: WIDTH,
      height: HEIGHT,
      initialPositions: prevPositions,
    })
    const positions: Record<number, { x: number; y: number }> = {}
    for (const n of result) positions[n.id] = { x: n.x, y: n.y }
    onPositionsComputed(positions)
    return result
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph])

  const rfNodes: Node[] = layoutNodes.map((n) => ({
    id: String(n.id),
    type: 'memory',
    position: { x: n.x, y: n.y },
    data: {
      label: n.text,
      memoryType: n.memory_type,
      expanded: expandedIds.has(n.id),
      selected: selectedId === n.id,
    },
  }))

  const rfEdges: Edge[] = graph.edges.map((e) => ({
    id: String(e.id),
    source: String(e.source_memory_id),
    target: String(e.target_memory_id),
    label: e.relation_type,
    animated: false,
  }))

  return (
    <div style={{ width: '100%', height: HEIGHT }}>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onNodeClick(Number(node.id))}
        onNodeDoubleClick={(_, node) => onNodeDoubleClick(Number(node.id))}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  )
}
```

### Step 2: 验证编译

Run: `cd frontend && npx tsc --noEmit`
Expected: 无类型错误

### Step 3: 提交

```bash
git add frontend/src/components/MemoryGraphCanvas.tsx
git commit -m "feat(graph): add React Flow canvas with layout, minimap, controls"
```

---

## Task 8: 探索容器 MemoryGraphPanel 重写与集成

**Files:**
- Rewrite: `frontend/src/components/MemoryGraphPanel.tsx`
- Delete: `frontend/src/components/MemoryGraph.tsx`
- Modify: `frontend/src/components/MemoryGraph.test.tsx`

### Step 1: 重写 MemoryGraphPanel

Replace entire `frontend/src/components/MemoryGraphPanel.tsx`:

```typescript
import { useEffect, useMemo, useState } from 'react'

import { api } from '../api/client'
import { useHubGraph, useMemories } from '../api/hooks'
import type { MemoryGraphRead } from '../api/types'
import { applyFilters, type GraphFilters } from '../graph/filterGraph'
import { collapseNode, mergeGraphs } from '../graph/mergeGraph'
import { ALL_MEMORY_TYPES, ALL_RELATION_TYPES, GraphFilterPanel } from './GraphFilterPanel'
import { GraphToolbar } from './GraphToolbar'
import { MemoryGraphCanvas } from './MemoryGraphCanvas'

const EMPTY_GRAPH: MemoryGraphRead = { center_memory_id: 0, nodes: [], edges: [] }
const MAX_VISIBLE_NODES = 200

export function MemoryGraphPanel() {
  const { data: memories = [] } = useMemories()
  const { data: hubGraph, isLoading, isError, refetch } = useHubGraph(5)

  const [graph, setGraph] = useState<MemoryGraphRead>(EMPTY_GRAPH)
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [positions, setPositions] = useState<Record<number, { x: number; y: number }>>({})
  const [filters, setFilters] = useState<GraphFilters>({
    memoryTypes: new Set(ALL_MEMORY_TYPES),
    relationTypes: new Set(ALL_RELATION_TYPES),
    minStrength: 0,
  })

  useEffect(() => {
    if (hubGraph) {
      setGraph(hubGraph)
    }
  }, [hubGraph])

  const visibleGraph = useMemo(() => applyFilters(graph, filters), [graph, filters])

  const expandNode = async (id: number) => {
    try {
      const neighbors = await api.memoryGraph(id, 1)
      setGraph((prev) => mergeGraphs(prev, neighbors))
      setExpandedIds((prev) => new Set(prev).add(id))
    } catch {
      // 展开失败不破坏已有图
    }
  }

  const handleNodeDoubleClick = (id: number) => {
    if (expandedIds.has(id)) {
      setGraph((prev) => collapseNode(prev, id, expandedIds))
      setExpandedIds((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
    } else {
      void expandNode(id)
    }
  }

  const handleJumpToMemory = (id: number) => {
    void expandNode(id)
    setSelectedId(id)
  }

  const handleReset = () => {
    setGraph(hubGraph ?? EMPTY_GRAPH)
    setExpandedIds(new Set())
    setSelectedId(null)
    setPositions({})
  }

  const selectedMemory = memories.find((m) => m.id === selectedId)

  return (
    <section className="center-panel full-span" aria-label="记忆图谱">
      <div className="panel-header">
        <h2>记忆图谱</h2>
      </div>

      <GraphToolbar memories={memories} onJumpToMemory={handleJumpToMemory} onReset={handleReset} />
      <GraphFilterPanel filters={filters} onChange={setFilters} />

      {isError ? (
        <div className="graph-error">
          <p>加载图谱失败。</p>
          <button type="button" onClick={() => refetch()}>
            重试
          </button>
        </div>
      ) : isLoading ? (
        <p>正在加载图谱…</p>
      ) : graph.nodes.length === 0 ? (
        <p>还没有记忆，去添加一些资料吧。</p>
      ) : (
        <>
          {visibleGraph.nodes.length > MAX_VISIBLE_NODES ? (
            <p className="helper-text">节点过多（{visibleGraph.nodes.length}），建议用过滤器收窄范围。</p>
          ) : null}
          <MemoryGraphCanvas
            graph={visibleGraph}
            expandedIds={expandedIds}
            selectedId={selectedId}
            prevPositions={positions}
            onNodeClick={setSelectedId}
            onNodeDoubleClick={handleNodeDoubleClick}
            onPositionsComputed={setPositions}
          />
        </>
      )}

      {selectedMemory ? (
        <div className="graph-node-detail">
          <h3>记忆详情</h3>
          <p>{selectedMemory.text}</p>
          <p className="helper-text">类型：{selectedMemory.memory_type}　双击节点可展开/收起关系</p>
        </div>
      ) : null}
    </section>
  )
}
```

### Step 2: 删除旧 MemoryGraph 组件

Run: `cd frontend && rm src/components/MemoryGraph.tsx`

### Step 3: 处理旧测试文件

Replace entire `frontend/src/components/MemoryGraph.test.tsx`:

```typescript
import { describe, expect, it } from 'vitest'

import { applyFilters, type GraphFilters } from '../graph/filterGraph'
import type { MemoryGraphRead } from '../api/types'

// MemoryGraph 组件已被 MemoryGraphCanvas 替代。画布渲染依赖真实 DOM 尺寸，
// 单测聚焦在已拆分的纯函数 (mergeGraph/filterGraph/useGraphLayout)。
// 这里保留一个 smoke 测试确认过滤集成。

describe('graph filtering integration', () => {
  it('全选过滤器返回全部节点', () => {
    const graph: MemoryGraphRead = {
      center_memory_id: 1,
      nodes: [{ id: 1, text: 'a', memory_type: 'fact', status: 'active' }],
      edges: [],
    }
    const filters: GraphFilters = {
      memoryTypes: new Set(['fact']),
      relationTypes: new Set(['related_to']),
      minStrength: 0,
    }
    expect(applyFilters(graph, filters).nodes).toHaveLength(1)
  })
})
```

### Step 4: 检查残留引用

Run: `cd frontend && grep -rn "from './MemoryGraph'" src/ ; grep -rn "from '../components/MemoryGraph'" src/`
Expected: 无对旧 `MemoryGraph`（非 Panel/Canvas）的 import。若有残留，删除或改为不引用。

### Step 5: Mock React Flow（如测试环境需要）

如果 `npx vitest run` 因 React Flow 在 jsdom 报错，在受影响的测试文件（如 `src/test/workbench.test.tsx`）顶部添加：

```typescript
import { vi } from 'vitest'

vi.mock('@xyflow/react', () => ({
  ReactFlow: () => null,
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
  Handle: () => null,
  Position: { Top: 'top', Bottom: 'bottom' },
}))
```

> 注：MemoryGraphPanel 不写组件级测试（逻辑已由纯函数测试覆盖）。仅需保证现有 `workbench.test.tsx` 不因 import 链引入未 mock 的 React Flow 而崩溃。

### Step 6: 运行前端测试

Run: `cd frontend && npx vitest run`
Expected: 全部 PASS

### Step 7: 生产构建

Run: `cd frontend && npm run build`
Expected: 构建成功，无类型错误

### Step 8: 提交

```bash
git add frontend/src/components/MemoryGraphPanel.tsx frontend/src/components/MemoryGraph.test.tsx
git rm frontend/src/components/MemoryGraph.tsx
git commit -m "feat(graph): rewrite MemoryGraphPanel as incremental exploration container"
```

---

## Task 9: 端到端验证与样式收尾

**Files:**
- Modify: 项目主样式文件（用 `grep -rl "center-panel" frontend/src --include="*.css"` 定位）
- Modify: `README.md`

### Step 1: 加最小样式

在主样式文件中追加：

```css
.graph-toolbar {
  display: flex;
  align-items: flex-end;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.graph-filter-panel {
  display: flex;
  gap: 1.5rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--border, #e5e7eb);
  border-radius: 8px;
}

.graph-filter-panel fieldset {
  border: none;
  padding: 0;
  margin: 0;
}

.filter-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin-right: 0.5rem;
  font-size: 0.85rem;
}

.graph-node-detail {
  margin-top: 0.75rem;
  padding: 0.75rem;
  border-top: 1px solid var(--border, #e5e7eb);
}

.graph-error {
  padding: 1rem;
  color: #b91c1c;
}
```

### Step 2: 手动冒烟验证

启动两个服务：
```bash
cd backend && uv run uvicorn service.main:app --reload --port 8000
cd frontend && npm run dev
```

浏览器进入「图谱」视图，确认：
- 枢纽记忆作为起点显示（或空库提示）
- 双击节点展开邻居，节点累积；再次双击收起
- 缩放/平移/拖拽/minimap 工作
- 过滤器（类型/关系/强度）即时生效
- 工具栏搜索跳转、重置视图工作
- 单击节点显示详情

### Step 3: 全套测试 + 构建

Run:
```bash
cd backend && uv run pytest tests/ -q
cd frontend && npx vitest run && npm run build
```
Expected: 后端全 PASS（1 skip），前端全 PASS，构建成功

### Step 4: 更新 README

在 `README.md` 的 Phase 列表中（Phase 1.7 之后）追加：

```markdown
## Phase 1.6: 记忆图谱可视化

- 增量探索式记忆网络：从关系密集的枢纽记忆出发，双击展开邻居逐步探索
- React Flow + d3-force 力导向布局，支持缩放、平移、拖拽、minimap
- 按记忆类型、关系类型、关系强度即时过滤
- 搜索跳转到任意记忆作为探索起点
```

### Step 5: 提交

```bash
git add README.md
git add -A
git commit -m "feat(graph): add graph exploration styles and update README for Phase 1.6"
```

---

## Self-Review

### 规格覆盖检查

| Spec 要求 | 对应 Task | 状态 |
|---|---|---|
| 枢纽起点端点 | Task 1 | ✅ |
| 复用 graph/relations API 展开 | Task 8（expandNode 用 memoryGraph depth=1）| ✅ |
| React Flow 渲染 | Task 7 | ✅ |
| d3-force 力导向布局 | Task 5 | ✅ |
| 增量累积（合并去重）| Task 3 mergeGraphs | ✅ |
| 收起节点 | Task 3 collapseNode | ✅ |
| 过滤 A+B+C（客户端派生）| Task 4 applyFilters | ✅ |
| 缩放/平移/拖拽/minimap | Task 7 | ✅ |
| 单击选中、双击展开 | Task 8 | ✅ |
| 搜索跳转、重置 | Task 6 + Task 8 | ✅ |
| 节点详情展示 | Task 8 | ✅ |
| 空库/失败/节点过多提示 | Task 8 | ✅ |
| 节点样式按类型配色 | Task 6 MemoryNode | ✅ |
| 删除旧 MemoryGraph | Task 8 | ✅ |
| 后端测试 | Task 1 | ✅ |
| 前端纯函数测试 | Task 3/4/5 | ✅ |
| 构建通过 | Task 9 | ✅ |
| README | Task 9 | ✅ |

### 占位符扫描
无 TBD/TODO/模糊步骤，所有代码步骤含完整代码。

### 类型一致性
- `MemoryGraphRead/Node/Edge` 全程复用 types.ts 现有定义
- `GraphFilters` 在 filterGraph.ts(Task 4) 定义，Task 6/8 一致引用
- `computeLayout` 签名在 Task 5 定义，Task 7 一致调用
- `mergeGraphs`/`collapseNode` 在 Task 3 定义，Task 8 一致调用
- `ALL_MEMORY_TYPES`/`ALL_RELATION_TYPES` 从 GraphFilterPanel(Task 6) 导出，Task 8 引用
- `MemoryNodeData` 字段（label/memoryType/expanded/selected）在 Task 6 定义，Task 7 构造 data 时一致

### 任务依赖顺序
Task 4(filterGraph) 在 Task 6(用 GraphFilters) 之前 ✅；Task 5(computeLayout) 在 Task 7(画布) 之前 ✅；Task 3/4/5/6/7 都在 Task 8(集成) 之前 ✅。

---

## 回退方案

- React Flow 测试环境报错 → Task 8 Step 5 的 mock 方案
- 路由顺序（`/graph/hubs` 被当 `{memory_id}`）→ Task 1 Step 6 已明确注册顺序
- 布局性能（节点过多）→ Task 8 的 MAX_VISIBLE_NODES 提示
- d3-force NaN 坐标 → Task 5 computeLayout 已兜底



