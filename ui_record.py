# ui_record.py
from __future__ import annotations
import uuid
import pandas as pd
import streamlit as st

from storage import append_rows
from utils import (
    safe_rerun,
    dir_pick_3buttons,
    kicker_for_kick_index,
    stage_from_kick_index,
    round_stage_from_kick_index,
    round_number_from_kick_index,
)

DIRS = ["L", "C", "R"]


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
    Return: (is_over, winner) winner in {'ME','OPP',None}
    Rules:
      - First 5 kicks each: can end early if trailing team cannot catch up
      - After both have taken 5: if scores differ => end
      - Sudden death: after each pair (same kicks taken) if scores differ => end
    """
    score_me, score_opp, kicks_me, kicks_opp = _score_and_counts(seq)

    # early termination during first 5 each
    if kicks_me <= 5 and kicks_opp <= 5:
        rem_me = 5 - kicks_me
        rem_opp = 5 - kicks_opp
        if score_me > score_opp + rem_opp:
            return True, "ME"
        if score_opp > score_me + rem_me:
            return True, "OPP"

        # finished 5 each
        if kicks_me == 5 and kicks_opp == 5 and score_me != score_opp:
            return True, "ME" if score_me > score_opp else "OPP"

    # sudden death: decide only after both have taken same number (>5)
    if kicks_me == kicks_opp and kicks_me > 5 and score_me != score_opp:
        return True, "ME" if score_me > score_opp else "OPP"

    return False, None


def record_page(me_name: str, opp_name: str):
    st.subheader("录入数据（按一整场，自动轮次推进 + 计分/判定结束）")
    st.caption("每脚用大箭头录入射门/扑救方向；系统自动计分，并在满足点球大战规则时判定比赛结束。")

    if "rec_order_mode" not in st.session_state:
        st.session_state.rec_order_mode = "ME_FIRST"
    if "rec_match_rows" not in st.session_state:
        st.session_state.rec_match_rows = []
    if "rec_kick_index" not in st.session_state:
        st.session_state.rec_kick_index = 1

    order_mode = st.radio(
        "主罚顺序",
        ["ME_FIRST", "OPP_FIRST"],
        key="rec_order_mode",
        format_func=lambda x: "我先发" if x == "ME_FIRST" else "我后发",
        horizontal=True,
    )

    # scoreboard + end check
    seq = st.session_state.rec_match_rows
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

    # controls top
    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        if st.button("撤销上一脚", key="rec_undo"):
            if st.session_state.rec_match_rows:
                st.session_state.rec_match_rows.pop()
                st.session_state.rec_kick_index = max(1, int(st.session_state.rec_kick_index) - 1)
                safe_rerun()
    with c2:
        if st.button("重置本场", key="rec_reset"):
            st.session_state.rec_match_rows = []
            st.session_state.rec_kick_index = 1
            st.session_state["rec_shot__val"] = None
            st.session_state["rec_dive__val"] = None
            safe_rerun()
    with c3:
        st.caption("提示：比赛结束后仍可保存本场到数据库。")

    st.divider()

    # if over, just show table and save section
    if is_over:
        st.write("本场已录入（比赛已结束）：")
        if len(seq):
            st.dataframe(pd.DataFrame(seq), use_container_width=True)
        else:
            st.info("本场为空。")

        st.divider()
        if st.button("保存本场到数据库", type="primary", key="rec_save_over", disabled=(len(seq) == 0)):
            match_id = str(uuid.uuid4())[:8]
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
            st.success(f"已保存 match_id={match_id}，共 {len(seq)} 脚。")
        return

    # current kick info
    kick_index = int(st.session_state.rec_kick_index)
    round_no = round_number_from_kick_index(kick_index)
    phase = stage_from_kick_index(kick_index)
    rstage = round_stage_from_kick_index(kick_index)
    who = kicker_for_kick_index(order_mode, kick_index)

    kicker_name = me_name if who == "ME" else opp_name
    keeper_name = opp_name if who == "ME" else me_name

    st.markdown(f"### 第 {round_no} 轮")
    st.caption(f"当前第 {kick_index} 脚 | 阶段：{phase} | 轮次阶段：{rstage}")
    st.markdown(f"**本脚射门：{kicker_name}** 　|　 **守门：{keeper_name}**")

    st.divider()

    # input via big arrows
    shot = dir_pick_3buttons("射门方向（点击箭头选择）", key="rec_shot", default=None)
    dive = dir_pick_3buttons("扑救方向（点击箭头选择）", key="rec_dive", default=None)

    if shot and dive:
        is_goal = 1 if shot != dive else 0
        st.metric("结果", "进球 ✅" if is_goal else "被扑 ❌")

    if st.button("确认录入这一脚（自动跳到下一脚）", type="primary", key="rec_confirm"):
        if shot not in DIRS or dive not in DIRS:
            st.error("请先选择射门方向和扑救方向。")
        else:
            ig = 1 if shot != dive else 0
            st.session_state.rec_match_rows.append(
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
            st.session_state.rec_kick_index = kick_index + 1
            st.session_state["rec_shot__val"] = None
            st.session_state["rec_dive__val"] = None
            safe_rerun()

    st.divider()
    st.write("本场已录入：")
    if len(seq) == 0:
        st.info("本场还没开始。")
    else:
        st.dataframe(pd.DataFrame(seq), use_container_width=True)

    st.divider()
    if st.button("保存本场到数据库", type="primary", key="rec_save_any", disabled=(len(seq) == 0)):
        match_id = str(uuid.uuid4())[:8]
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
        st.success(f"已保存 match_id={match_id}，共 {len(seq)} 脚。")
