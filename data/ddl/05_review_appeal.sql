-- ============================================================
-- M05 · 人工复核与申诉闭环（考核性 R2/R3）
-- 仅 DDL 草案基线，正式迁移在 M11 之后统一评审执行。
-- 对齐《系统设计文档-v0.1.md》§0 R2/R3 与 §2 数据模型。
-- ============================================================

-- R2 人工复核清单：过程性维度（课堂教学、教学设计等）强制教研组长人工确认
CREATE TABLE IF NOT EXISTS human_review_checklist (
    id           BIGSERIAL PRIMARY KEY,
    result_id    BIGINT NOT NULL REFERENCES evaluation_result(result_id) ON DELETE CASCADE,
    dimension    TEXT NOT NULL,          -- 维度名，如：课堂教学
    item         TEXT NOT NULL,          -- 需人工确认的项目，如：听课评分均值是否认可
    value        TEXT,                   -- 原始证据值（如：86.5 / 6 次听课）
    score        NUMERIC,                -- 计算分
    confidence   NUMERIC,                -- 置信度 0~1
    reviewed_by  TEXT,                   -- 教研组长等人工确认人
    reviewed_at  TIMESTAMPTZ,
    status       TEXT DEFAULT 'pending' CHECK (status IN ('pending','confirmed','rejected'))
);

-- R3 申诉与复核：教师对评估结果有异议时提交申诉；
-- 系统只出具"哪些数据参与、口径、各步取值依据"的追溯说明（trace_json），
-- 不改分，由评审委员会终裁。
CREATE TABLE IF NOT EXISTS appeal_record (
    appeal_id      BIGSERIAL PRIMARY KEY,
    result_id      BIGINT NOT NULL REFERENCES evaluation_result(result_id) ON DELETE CASCADE,
    teacher_id     TEXT NOT NULL,        -- 申诉教师（对应 teacher.teacher_id）
    appeal_reason  TEXT NOT NULL,        -- 教师申诉理由
    trace_json     JSONB NOT NULL,       -- 系统追溯说明：
                                         --   {
                                         --     "inputs": [
                                         --       {"table": "exam_score", "filter": "school_year='2024-2025'", "used_range": "2024-2025"},
                                         --       ...
                                         --     ],
                                         --     "results": [
                                         --       {"metric": "pass_rate_improvement", "value": 0.043, "formula": "class_pass_rate - cohort_baseline_pass_rate"},
                                         --       ...
                                         --     ],
                                         --     "caveats": [ ... ]   -- 数据缺口/置信度受限说明
                                         --   }
    committee_result TEXT,               -- 委员会终裁：upheld（支持异议）/ dismissed（驳回）/ partially（部分支持）
    adjustment     JSONB,                -- 改分记录（如有）：{original_score, new_score, reason}
    status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_review','closed')),
    created_at     TIMESTAMPTZ DEFAULT now(),
    resolved_at    TIMESTAMPTZ
);

-- 索引：按教师/结果/状态快速检索申诉与未确认复核项
CREATE INDEX IF NOT EXISTS idx_appeal_teacher ON appeal_record(teacher_id);
CREATE INDEX IF NOT EXISTS idx_appeal_status  ON appeal_record(status);
CREATE INDEX IF NOT EXISTS idx_checklist_result ON human_review_checklist(result_id);
CREATE INDEX IF NOT EXISTS idx_checklist_status  ON human_review_checklist(status);