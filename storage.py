# storage.py
from __future__ import annotations

import pandas as pd
from config import DB_PATH

# IMPORTANT: only UI should call delete/clear, but we also add function-level admin guard.
# This makes it harder to accidentally expose destructive ops later.
from auth import require_admin

REQUIRED_COLS = [
    "match_id",
    "kick_index",
    "who_kicked",   # 'ME' or 'OPP'
    "kicker_dir",   # L/C/R
    "keeper_dir",   # L/C/R
    "is_goal",      # 0/1
    "order_mode",   # ME_FIRST / OPP_FIRST
    "phase",        # REG / SD
    "round_stage",  # EARLY / MID / LATE
]


def load_db() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame(columns=REQUIRED_COLS)

    try:
        df = pd.read_csv(DB_PATH, dtype=str, encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(DB_PATH, dtype=str)

    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = ""

    df["kick_index"] = pd.to_numeric(df["kick_index"], errors="coerce").fillna(0).astype(int)
    df["is_goal"] = pd.to_numeric(df["is_goal"], errors="coerce").fillna(0).astype(int)

    return df[REQUIRED_COLS]


def append_rows(df_new: pd.DataFrame):
    df = load_db()

    for c in REQUIRED_COLS:
        if c not in df_new.columns:
            df_new[c] = ""

    df_new["kick_index"] = pd.to_numeric(df_new["kick_index"], errors="coerce").fillna(0).astype(int)
    df_new["is_goal"] = pd.to_numeric(df_new["is_goal"], errors="coerce").fillna(0).astype(int)

    out = pd.concat([df, df_new[REQUIRED_COLS]], ignore_index=True)
    out.to_csv(DB_PATH, index=False, encoding="utf-8-sig")


# ---- destructive ops (admin only) ----
def clear_db():
    require_admin()
    if DB_PATH.exists():
        DB_PATH.unlink(missing_ok=True)


def delete_match(match_id: str):
    require_admin()
    df = load_db()
    df = df[df["match_id"] != str(match_id)]
    df.to_csv(DB_PATH, index=False, encoding="utf-8-sig")


def delete_last_n(n: int):
    require_admin()
    df = load_db()
    if n <= 0:
        return
    if len(df) <= n:
        if DB_PATH.exists():
            DB_PATH.unlink(missing_ok=True)
        return
    df = df.iloc[:-n].copy()
    df.to_csv(DB_PATH, index=False, encoding="utf-8-sig")


def export_csv_bytes(admin_only: bool = True) -> bytes:
    if admin_only:
        require_admin()
    df = load_db()
    return df.to_csv(index=False).encode("utf-8-sig")
