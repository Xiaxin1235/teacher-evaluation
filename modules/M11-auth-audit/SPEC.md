# M11 · 权限与审计

> 状态：`todo`　依赖：M09　验收：DDL 存在 + `import packages.core.authz` 无报错

## 目标
为考核数据建闸：角色权限矩阵（管理员/教务/教研员/教师本人）、数据范围控制（教师本人只见自己；教研员见本组；教务见全校）、审计留痕（谁/何时/看哪个教师/调了哪些模型/导出）。

## 任务清单
1. `data/ddl/11_auth_audit.sql`：
   - `system_user`（user_id, role, name_hash）；
   - `access_log` / `audit_log`（user_id, action, target_scope jsonb, model_calls jsonb, result_id, created_at）；
   - `appeal` 相关复审权限字段可预留。
2. `packages/core/` 包（含 `__init__.py`）中 `authz.py`：
   - `Role` 枚举（admin/manage/教研员/teacher_self）；
   - `can_view(user, teacher_id, scope)`：教师本人只能看自己；教研员按 dept；admin 全校；
   - `can_export(user, scope)`：导出需二次授权（红旗标记）。
   - 桩实现即可（真实用户表由部署方提供；本模块提供契约与逻辑）。
3. `apps/api` 的 `get_current_user` 占位升级为调用 `authz.can_view`（M09 留下的 TODO）。

## 验收
```bash
python -c "from packages.core.authz import can_view; print(can_view('teacher_self','T001','T001')==True)"
python scripts/doc_smoke.py   # 不破坏冒烟
```

## 依赖与边界
- 不做部署级身份认证（SSO/AD 对接是运维）；只做授权逻辑与审计表结构。
- 红线数据（complaint/discipline）访问需最严格权限：默认仅 admin 可看明细。