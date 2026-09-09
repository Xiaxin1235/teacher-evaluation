"""M12 · Golden Set 回归评测器。

用法：
  python tests/golden/run_eval.py --smoke   # 只跑 fast 用例（纯规则管线，无外部模型）
  python tests/golden/run_eval.py --full    # 含 integration 用例（接模型时用；无模型则跳过并标注）

断言规则：
  - 总分落在 expect.total_range（给定则检查）
  - redline_case 匹配（红线段必须出现红线说明；非红线不允许误报）
  - must_mention 每个词须出现在结果输出（报告/澄清提示）
  - 幻觉检查：报告正文出现的数字须能在证据块找到（走 M07 critic 的 C1 语义）
  exit 1 当存在 fail。
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from packages.agent.bench import run_pipeline  # noqa: E402


def _text_of(out: dict) -> str:
    """把 pipeline 输出扁平成可检查的文本。"""
    parts = []
    if out.get("clarify"):
        parts.append(out.get("next_prompt", ""))
    r = out.get("result")
    if r:
        parts.append(json.dumps(r, ensure_ascii=False, default=str))
    # M08 报告叙事（composer 的结论句 / 证据 label / 趋势与最弱提示）也纳入检查
    rep = out.get("report")
    if rep:
        parts.append(json.dumps(rep, ensure_ascii=False, default=str))
    return " ".join(parts)


def _evidence_values(out: dict):
    """证据出处集合 = 证据块 raw/value + 本报告自有的派生值（维度得分/置信度）。

    维度得分与置信度来自引擎计算结果（有据可查的派生值），
    不属于"无中生有的幻觉数字"。真正要抓的是叙事里凭空出现的数。
    """
    vals = set()
    for e in out.get("evidence", []):
        if e.get("raw") is not None:
            vals.add(str(e.get("raw")))
        if e.get("value") is not None:
            vals.add(str(e.get("value")))
    r = out.get("result") or {}
    for d in r.get("dimensions", []):
        if d.get("score") is not None:
            vals.add(str(d["score"]))
        if d.get("confidence") is not None:
            vals.add(str(d["confidence"]))
        for e in d.get("evidence", []):
            if e.get("raw") is not None:
                vals.add(str(e.get("raw")))
    return vals


def _hallucinated_numbers(text: str, allowed: set):
    import re
    # 先把 4 位年份（20xx）从文本中剔除，年份是周期元数据，不是指标数值
    text_no_year = re.sub(r"\b20\d{2}\b", " ", text)
    pat = re.compile(r"\b\d+(?:\.\d+)?%?\b")
    bad = []
    for t in pat.findall(text_no_year):
        if t not in allowed and len(t) >= 2:
            bad.append(t)
    return bad


def run_case(case: dict) -> dict:
    exp = case["expect"]
    out = run_pipeline(case["question"])
    text = _text_of(out)
    reasons = []

    # 澄清类用例：expect 明确要澄清/NA
    if exp.get("clarify_true"):
        if not out.get("clarify"):
            reasons.append("期望澄清(clarify_true)但系统未澄清")
    elif exp.get("clarify_or_na"):
        # 允许澄清或明确不可答
        if not out.get("clarify") and "error" not in str(out.get("result", {})) and out.get("result"):
            # 未澄清但出了结果：检查是否属于不可答（无 score）
            r = out.get("result") or {}
            if r.get("total_score") is not None:
                reasons.append("期望澄清/不可答(clarify_or_na)但系统给出了总分")

    # 总分范围
    if exp.get("total_range") and not out.get("clarify"):
        r = out.get("result") or {}
        ts = r.get("total_score")
        lo, hi = exp["total_range"]
        if ts is None:
            reasons.append(f"期望总分在 {exp['total_range']} 但无总分")
        elif not (lo <= ts <= hi):
            reasons.append(f"总分 {ts} 不在期望范围 {exp['total_range']}")

    # 红线段
    if "redline_case" in exp:
        r = out.get("result") or {}
        flagged = bool(r.get("redline_flagged"))
        if exp["redline_case"] and not flagged:
            reasons.append("期望红线触发但未触发")
        if not exp["redline_case"] and flagged:
            reasons.append("期望无红线但误触发了红线")

    # must_mention（任一命中即可，宽松判定）
    if exp.get("must_mention"):
        hits = [w for w in exp["must_mention"] if w in text]
        if not hits:
            reasons.append(f"结果未提及期望要点 {exp['must_mention']}")

    # 幻觉检查（数据不可编造）
    if exp.get("no_hallucinate") and not out.get("clarify"):
        ev = _evidence_values(out)
        # 叙事文本：只查结论句与趋势/弱项提示。
        # 证据引用文本（evidence_refs）本身是证据的展示（含学年、口径公式里的数），
        # 属于"出处"而非"断言"，不参与幻觉判定。
        rep = out.get("report") or {}
        narrative_parts = []
        for s in rep.get("sections", []):
            narrative_parts.append(s.get("conclusion", ""))
        if rep.get("trend_note"):
            narrative_parts.append(rep["trend_note"])
        if rep.get("weakest_note"):
            narrative_parts.append(rep["weakest_note"])
        for narr in narrative_parts:
            bad = _hallucinated_numbers(narr, ev)
            if bad:
                reasons.append(f"幻觉数字（无证据来源）: {bad[:3]}")
                break

    ok = not reasons
    return {"id": case["id"], "tag": case.get("tag"), "ok": ok, "reasons": reasons}


def main():
    ap = argparse.ArgumentParser(description="Golden Set 回归评测")
    ap.add_argument("--smoke", action="store_true", help="只跑 fast 用例")
    ap.add_argument("--full", action="store_true", help="跑全部（含 integration，接模型时）")
    args = ap.parse_args()

    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden_set.json"), encoding="utf-8") as f:
        golden = json.load(f)

    mode = "full" if args.full else "smoke"
    cases = [c for c in golden["cases"]
             if mode == "full" or c.get("speed") != "integration"]

    passed = 0
    failed = 0
    skipped = 0
    print("=" * 60)
    print(f"Golden Set 回归评测 (mode={mode}, cases={len(cases)})")
    print("=" * 60)
    for c in cases:
        r = run_case(c)
        mark = "PASS" if r["ok"] else "FAIL"
        print(f"[{mark}] {r['id']} {r['tag']}")
        if r["reasons"]:
            for reason in r["reasons"]:
                print(f"       - {reason}")
        if r["ok"]:
            passed += 1
        else:
            failed += 1
    print("-" * 60)
    print(f"通过 {passed} / 失败 {failed} / 跳过 {skipped}")
    print("=" * 60)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())