# ui_live.py
from __future__ import annotations

from collections import Counter
import pandas as pd
import streamlit as st

from storage import load_db, append_rows
from model import NgramStageModel, blend_probs
from utils import (
    safe_rerun,
    dir_pick_3buttons,
    kicker_for_kick_index,
    stage_from_kick_index,
    round_stage_from_kick_index,
    round_number_from_kick_index,
)

DIRS = ["L", "C", "R"]


def _recent_dirs(seq, who: str):
    return [x["kicker_dir"] for x in seq if x.get("who_kicked") == who and x.get("kicker_dir") in DIRS]


def _score_and_counts(seq):
    score_me = 0
    score_opp = 0
    kicks_me = 0
    kicks_opp = 0

    for x in seq:
        who = x.get("who_kicked")
        ig = int(x.get("is_goal", 0))
        if who == "ME":
            kicks_me += 1
            score_me += ig
        elif who == "OPP":
            kicks_opp += 1
            score_opp += ig

    return score_me, score_opp, kicks_me, kicks_opp


def _shootout_result(seq):
    """
    Return: (is_over, winner)  winner in {'ME','OPP',None}
    Standard rule:
      - First 5 kicks each (max 10 total), can end early if trailing team cannot catch up
      - Sudden death after both have taken 5: after each pair (same number of kicks taken),
        if scores differ => match ends
    """
    score_me, score_opp, kicks_me, kicks_opp = _score_and_counts(seq)

    # early termination in first 5 each
    if kicks_me <= 5 and kicks_opp <= 5:
        rem_me = 5 - kicks_me
        rem_opp = 5 - kicks_opp
        if score_me > score_opp + rem_opp:
            return True, "ME"
        if score_opp > score_me + rem_me:
            return True, "OPP"

        # exactly finished 5 each
        if kicks_me == 5 and kicks_opp == 5 and (score_me != score_opp):
            return True, "ME" if score_me > score_opp else "OPP"

    # sudden death: only decide after both have taken same number and > 5
    if kicks_me == kicks_opp and kicks_me > 5 and score_me != score_opp:
        return True, "ME" if score_me > score_opp else "OPP"

    return False, None


def live_page(me_name: str, opp_name: str, alpha: float, k: int, match_weight: float, order_mode: str):
    st.subheader("实时模式（自动轮次推进 + 大箭头点选 + 自动计分/判定结束）")

    if "live_seq" not in st.session_state:
        st.session_state.live_seq = []
    if "live_kick_index" not in st.session_state:
        st.session_state.live_kick_index = 1
    if "live_match_id" not in st.session_state:
        st.session_state.live_match_id = ""

    seq = st.session_state.live_seq

    # scoreboard + end check
    score_me, score_opp, kicks_me, kicks_opp = _score_and_counts(seq)
    is_over, winner = _shootout_result(seq)

    sb1, sb2, sb3, sb4 = st.columns([1.2, 1.2, 1.2, 2.4])
    sb1.metric(f"{me_name} 进球", score_me)
    sb2.metric(f"{opp_name} 进球", score_opp)
    sb3.metric("已踢(我/对手)", f"{kicks_me}/{kicks_opp}")
    if is_over:
        if winner == "ME":
            sb4.success(f"比赛结束：{me_name} 胜 ✅")
        elif winner == "OPP":
            sb4.error(f"比赛结束：{opp_name} 胜 ❌")
        else:
            sb4.warning("比赛结束")
    else:
        sb4.info("比赛进行中…")

    # controls
    c_reset, c_save, c_id = st.columns([1, 1, 3])
    with c_reset:
        if st.button("重置本场", key="live_reset"):
            st.session_state.live_seq = []
            st.session_state.live_kick_index = 1
            st.session_state["live_shot__val"] = None
            st.session_state["live_dive__val"] = None
            safe_rerun()

    with c_save:
        if st.button("保存本场到数据库", key="live_save_db", disabled=(len(seq) == 0)):
            import uuid
            match_id = st.session_state.live_match_id.strip() or str(uuid.uuid4())[:8]
            st.session_state.live_match_id = match_id

            df_new = pd.DataFrame(seq).copy()
            df_new["match_id"] = match_id
            append_rows(df_new[[
                "match_id",
                "kick_index",
                "who_kicked",
                "kicker_dir",
                "keeper_dir",
                "is_goal",
                "order_mode",
                "phase",
                "round_stage",
            ]])
            st.success(f"已保存：match_id={match_id}（{len(seq)} 脚）")

    with c_id:
        st.session_state.live_match_id = st.text_input("match_id（可选，不填则保存时自动生成）", value=st.session_state.live_match_id, key="live_mid")

    st.divider()

    # if over: only show log + allow reset/save
    if is_over:
        st.write("本场记录：")
        st.dataframe(pd.DataFrame(seq), use_container_width=True)
        return

    # current kick info
    kick_index = int(st.session_state.live_kick_index)
    round_no = round_number_from_kick_index(kick_index)
    phase = stage_from_kick_index(kick_index)          # REG/SD
    rstage = round_stage_from_kick_index(kick_index)   # EARLY/MID/LATE
    who = kicker_for_kick_index(order_mode, kick_index)

    kicker_name = me_name if who == "ME" else opp_name
    keeper_name = opp_name if who == "ME" else me_name

    st.markdown(f"### 第 {round_no} 轮")
    st.caption(f"当前第 {kick_index} 脚 | 阶段：{phase} | 轮次阶段：{rstage}")
    st.markdown(f"**本脚射门：{kicker_name}** 　|　 **守门：{keeper_name}**")

    # model
    df = load_db()
    model = NgramStageModel(df)
    model.build(max_k=max(0, int(k)))

    recent = _recent_dirs(seq, who)
    p_hist = model.predict_next_dir(
        who=who, stage=rstage, recent_dirs_for_who=recent, k=int(k), alpha=float(alpha)
    )

    # match-only (same stage + same ctx) count
    kk = max(0, int(k))
    ctx = tuple(recent[-kk:]) if kk > 0 else tuple()
    live_counts = Counter()

    hist_tmp = {"ME": [], "OPP": []}
    for idx, shot in enumerate(seq, start=1):
        s_rstage = round_stage_from_kick_index(idx)
        w = shot["who_kicked"]
        cur_ctx = tuple(hist_tmp[w][-kk:]) if kk > 0 else tuple()
        if w == who and s_rstage == rstage and cur_ctx == ctx:
            nd = shot.get("kicker_dir")
            if nd in DIRS:
                live_counts[nd] += 1
        hist_tmp[w].append(shot.get("kicker_dir"))

    total = sum(live_counts.get(d, 0) + float(alpha) for d in DIRS)
    p_match = {d: (live_counts.get(d, 0) + float(alpha)) / total for d in DIRS} if total > 0 else {d: 1 / 3 for d in DIRS}

    p = blend_probs(p_hist, p_match, match_weight=float(match_weight))
    rec = max(p, key=lambda x: p[x])

    cols = st.columns(3)
    cols[0].metric("L", f"{p['L']*100:.1f}%")
    cols[1].metric("C", f"{p['C']*100:.1f}%")
    cols[2].metric("R", f"{p['R']*100:.1f}%")
    st.info(f"推荐（概率最大）：**{rec}**")

    st.divider()

    # input via big arrows
    shot = dir_pick_3buttons("射门方向（点击箭头选择）", key="live_shot", default=None)
    dive = dir_pick_3buttons("扑救方向（点击箭头选择）", key="live_dive", default=None)

    if shot and dive:
        is_goal = 1 if shot != dive else 0
        st.metric("结果", "进球 ✅" if is_goal else "被扑 ❌")

    if st.button("确认这一脚（自动进入下一脚）", type="primary", key="live_confirm"):
        if shot not in DIRS or dive not in DIRS:
            st.error("请先选择射门方向和扑救方向。")
        else:
            ig = 1 if shot != dive else 0
            st.session_state.live_seq.append(
                {
                    "kick_index": kick_index,
                    "who_kicked": who,
                    "kicker_dir": shot,
                    "keeper_dir": dive,
                    "is_goal": int(ig),
                    "order_mode": order_mode,
                    "phase": phase,
                    "round_stage": rstage,
                }
            )
            st.session_state.live_kick_index = kick_index + 1
            st.session_state["live_shot__val"] = None
            st.session_state["live_dive__val"] = None
            safe_rerun()

    st.divider()
    st.write("本场记录：")
    if len(seq) == 0:
        st.info("本场还没开始。")
    else:
        st.dataframe(pd.DataFrame(seq), use_container_width=True)
