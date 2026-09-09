-- ============================================================
-- M11 · 权限与审计 DDL（草案基线，正式迁移在部署时统一评审执行）
-- 角色矩阵：admin / manage / 教研员 / teacher_self
-- 红线数据（complaint/discipline）仅 admin 可看明细。
-- ============================================================

-- 用户（去标识交付；真实用户表由部署方 SSO/AD 对接）
CREATE TABLE IF NOT EXISTS system_user (
    user_id    TEXT PRIMARY KEY,          -- 登录标识（内部 ID，不存明文姓名）
    role       TEXT NOT NULL CHECK (role IN ('admin','manage','教研员','teacher_self')),
    dept_id    TEXT,                      -- 教研员/教师所属教研组（数据范围依据）
    teacher_id TEXT,                      -- teacher_self 绑定的教师主数据 ID
    name_hash  TEXT,                      -- 姓名哈希（可选，抽检用）
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 审计日志：谁 / 何时 / 对哪个对象 / 做了什么 / 调用了哪些模型
CREATE TABLE IF NOT EXISTS audit_log (
    log_id        BIGSERIAL PRIMARY KEY,
    user_id       TEXT REFERENCES system_user(user_id),
    action        TEXT NOT NULL,          -- view / evaluate / export / model_call / manual_review
    target_scope  JSONB,                  -- 涉及教师/范围，如 {"teacher_ids":["T001","T003"]}
    model_calls   JSONB,                  -- 调用的模型与消耗，如 [{"provider":"deepseek","model":"deepseek-chat","tokens":1200}]
    result_id     TEXT,                   -- 关联的评估结果（原型内存 result_id）
    detail        JSONB,                  -- 附加说明（导出原因、申诉终裁等）
    created_at    TIMESTAMPTZ DEFAULT now()
);

-- 访问日志（明细级：谁看了哪个教师的报告）
CREATE TABLE IF NOT EXISTS access_log (
    log_id      BIGSERIAL PRIMARY KEY,
    user_id     TEXT REFERENCES system_user(user_id),
    teacher_id  TEXT,                     -- 被查看的教师
    scope       TEXT,                     -- 查看范围：self / dept / all
    result_id   TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_audit_user   ON audit_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_result ON audit_log(result_id);
CREATE INDEX IF NOT EXISTS idx_access_user  ON access_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_access_teacher ON access_log(teacher_id);