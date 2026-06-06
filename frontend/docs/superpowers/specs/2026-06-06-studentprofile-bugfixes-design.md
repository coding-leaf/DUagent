# StudentProfile 实现 bug 修复设计

> 仅修当前实现中的状态建模错误和枚举值兜底问题，不新增交互能力。

**最后更新：** 2026-06-06

---

## 1. 目标

修复 StudentProfile.jsx 重接真实字段后暴露的 3 个实现 bug：切课脏读、失败态与默认画像混淆、未知枚举值伪装为正常值。

---

## 2. 范围

**在范围（仅改 `src/pages/StudentProfile.jsx`）：**

- 新增 `profileError` state，区分"请求失败"和"成功返回默认画像"
- useEffect 中 activeCourseId 变化时清空旧 `profileData`
- 失败时渲染错误 banner + 重试按钮
- guidance_level.current、knowledge_coordinates.status、cognitive_blindspots.severity 的未知值兜底改为"未知"

**非目标：**
- L1-L3 可点击切换（独立后续任务，`PUT /users/me` 契约已存在）
- Backend/OpenAPI 改动

---

## 3. 状态模型修正

### 当前（有问题）

```
profileData: null | object    ← null 同时表示"未请求"和"失败"
                              ← 失败时不清理，保留旧课程数据
```

### 修正后

```
profileData: null | object    ← null=无数据/已清空，object=成功返回（含默认画像）
profileError: null | string   ← null=无错误，string=错误信息
```

**新增 state：** `const [profileError, setProfileError] = useState(null);`

---

## 4. useEffect 修正

```
activeCourseId 变化时：
  1. setProfileData(null)        ← 防止跨课程脏读
  2. setProfileError(null)
  3. setLoading(true)
  4. await GET /profile
     → 成功（res.code === 200）：setProfileData(res.data)
     → 失败（catch）：setProfileError("加载失败，请重试")；setProfileData(null)
  5. setLoading(false)
```

---

## 5. 渲染分支修正

新增错误态渲染，在 loading 检查之后、卡片渲染之前：

```
!activeCourseId     → 空态页面（已有）
loading             → spinner（已有）
profileError        → 错误 banner + "重试" 按钮（新增）
profileData         → 5 张卡片（已有）
```

### 错误态 UI

- 居中展示错误图标 + "加载失败，请重试" 文字
- 单个"重试"按钮，点击触发重新 fetch（抽取 fetchProfile 为独立函数供 useEffect 和按钮共用）

---

## 6. 枚举值兜底修正

### guidance_level.current

```
L1 → 进度条 33%，高亮 L1
L2 → 进度条 66%，高亮 L2
L3 → 进度条 100%，高亮 L3
其他 → 进度条 50%，所有刻度点不亮，标签显示"未知"
```

### knowledge_coordinates[].status

```
mastered → 绿色标签 "已掌握"
learning → 琥珀标签 "学习中"
其他     → 灰色标签 "未知"
```

### cognitive_blindspots[].severity

```
high   → 红色标签 "高"
medium → 琥珀标签 "中"
low    → 灰色标签 "低"
其他   → 灰色标签，展示原始 severity 值
```

---

## 7. 验证

| 方式 | 内容 |
|------|------|
| `npm run lint` | 零错误 |
| `npm run build` | 通过 |

---

## 自审

1. **无占位符：** ✓
2. **范围：** ✓ 仅改 StudentProfile.jsx，不改 Backend/API
3. **不新增能力：** ✓ L1-L3 交互排除在外
