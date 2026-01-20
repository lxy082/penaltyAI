# model.py
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Dict, List, Tuple
import pandas as pd

from config import DIRS


def _ctx_tuple(seq: List[str], k: int) -> Tuple[str, ...]:
    if k <= 0:
        return tuple()
    if len(seq) < k:
        return tuple(seq)
    return tuple(seq[-k:])


def _dirichlet_smooth(counts: Counter, alpha: float) -> Dict[str, float]:
    total = 0.0
    out = {}
    for d in DIRS:
        c = float(counts.get(d, 0))
        out[d] = c + alpha
        total += out[d]
    if total <= 0:
        return {d: 1 / len(DIRS) for d in DIRS}
    return {d: out[d] / total for d in DIRS}


class NgramStageModel:
    """
    用历史数据库训练一个“分阶段 + K阶序列”的方向分布模型：
      P(next_dir | who, round_stage, ctx)
    其中 ctx 是最近 K 次该射门者的方向序列（只看同一射门者的过去）
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._counts = None  # lazy
        self._built = False

    def build(self, max_k: int = 2):
        # counts[(who, stage, k, ctx_tuple)] -> Counter(next_dir)
        counts = defaultdict(Counter)

        # 分 match_id 逐场构造序列
        for mid, g in self.df.groupby("match_id"):
            g = g.sort_values("kick_index")
            # 为 ME/OPP 各自维护历史射门方向
            hist = {"ME": [], "OPP": []}
            for _, r in g.iterrows():
                who = str(r.get("who_kicked", ""))
                if who not in ("ME", "OPP"):
                    continue
                stage = str(r.get("round_stage", ""))
                if stage not in ("EARLY", "MID", "LATE"):
                    stage = "MID"
                next_dir = str(r.get("kicker_dir", ""))
                if next_dir not in DIRS:
                    continue

                for k in range(max_k, -1, -1):
                    ctx = _ctx_tuple(hist[who], k)
                    counts[(who, stage, k, ctx)][next_dir] += 1

                hist[who].append(next_dir)

        self._counts = counts
        self._built = True

    def predict_next_dir(
        self,
        who: str,
        stage: str,
        recent_dirs_for_who: List[str],
        k: int,
        alpha: float,
    ) -> Dict[str, float]:
        if not self._built:
            self.build(max_k=max(0, k))

        who = "ME" if who == "ME" else "OPP"
        stage = stage if stage in ("EARLY", "MID", "LATE") else "MID"
        k = max(0, int(k))

        # backoff: k -> k-1 -> ... -> 0
        for kk in range(k, -1, -1):
            ctx = _ctx_tuple(recent_dirs_for_who, kk)
            key = (who, stage, kk, ctx)
            if key in self._counts and sum(self._counts[key].values()) > 0:
                return _dirichlet_smooth(self._counts[key], alpha)

        # 没数据：均匀
        return {d: 1 / len(DIRS) for d in DIRS}


def blend_probs(p_hist: Dict[str, float], p_match: Dict[str, float], match_weight: float) -> Dict[str, float]:
    w = float(match_weight)
    out = {}
    for d in DIRS:
        out[d] = (p_hist.get(d, 0.0) + w * p_match.get(d, 0.0)) / (1.0 + w)
    s = sum(out.values())
    if s <= 0:
        return {d: 1 / len(DIRS) for d in DIRS}
    return {d: out[d] / s for d in DIRS}
