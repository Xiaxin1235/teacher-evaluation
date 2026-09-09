"""评分校准（M04）单元测试。

验收：python -m pytest tests/test_calibration.py -q  期望全部通过
（本机无 pytest 时：python tests/test_calibration.py 也会跑内联自检）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packages.indicator_engine.calibration import calibrate, attach_calibration


def _score_rows(values, group="数学组"):
    return [{"dept_id": group, "score": v} for v in values]


def test_zscore_matches_statistics():
    """大样本组：z-score 应满足 组内标准化（均值≈0、标准差≈1）。"""
    rows = _score_rows([60, 70, 80, 90, 100, 70, 80, 90])
    out = calibrate(rows, group_col="dept_id", value_col="score")
    zs = [r["z_score"] for r in out]
    import statistics
    assert abs(statistics.fmean(zs)) < 1e-6
    assert abs(statistics.stdev(zs) - 1.0) < 1e-6
    # 各记录都拿到三件套
    for r in out:
        assert "pct_rank" in r and "z_score" in r and "small_sample" in r


def test_small_group_falls_back_to_school():
    """小样本组（<5）：z_score 回退全校口径且 small_sample=True。"""
    big = _score_rows([60, 70, 80, 90, 100, 70, 80, 90], group="大组")
    small = _score_rows([100, 100, 100], group="小组")  # 组内 std=0
    out = calibrate(big + small, group_col="dept_id", value_col="score")
    for r in out:
        if r["dept_id"] == "小组":
            assert r["small_sample"] is True
            # 全校均值约 83，小组全部 100 → z_score > 0
            assert r["z_score"] > 0
    for r in out:
        if r["dept_id"] == "大组":
            assert r["small_sample"] is False


def test_single_sample_group_no_crash():
    """单样本组不崩溃，pct_rank=100。"""
    rows = _score_rows([75], group="独苗组")
    out = calibrate(rows, group_col="dept_id", value_col="score")
    assert out[0]["pct_rank"] == 100
    assert out[0]["small_sample"] is True


def test_empty_input():
    """空输入返回空列表。"""
    assert calibrate([]) == []


def test_pct_rank_monotonic():
    """百分位与数值单调：更高的分 → pct_rank 不更低。"""
    rows = _score_rows([50, 70, 90])
    out = calibrate(rows, group_col="dept_id", value_col="score")
    by_score = {r["score"]: r["pct_rank"] for r in out}
    assert by_score[50] < by_score[70] < by_score[90]


def test_attach_calibration_block():
    """attach_calibration 给报告附上 calibration 区块。"""
    result = {
        "dimensions": [
            {"dimension": "教学", "score": 80.0, "is_redline": False},
            {"dimension": "课堂", "score": 60.0, "is_redline": False},
            {"dimension": "红线", "score": None, "is_redline": True},
        ]
    }
    r = attach_calibration(result)
    assert "calibration" in r
    assert r["calibration"]["per_dimension"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)