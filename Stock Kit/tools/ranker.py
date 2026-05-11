"""纯数学四层加权排名计算 — 不需要 LLM

实现 InvestSkill v3.0 定义的四层加权排名公式:
  L1: EBIT/EV (40%) — 从高到低排名
  L2: ROIC (25%) — 从高到低排名
  L3: F-Score (25%) — 从高到低排名
  L4: PEG (10%) — 从低到高排名

综合分 = L1排名×0.40 + L2×0.25 + L3×0.25 + L4×0.10 (越小越好)
"""

from typing import TypedDict
from dataclasses import dataclass, field

LAYER_WEIGHTS = {"L1": "40%", "L2": "25%", "L3": "25%", "L4": "10%"}


@dataclass
class RankingRow:
    layer: str
    dimension: str
    metric: str
    value: str
    weight: str
    rank: str
    verdict: str = ""


@dataclass
class RankingResult:
    rows: list[RankingRow]
    composite_score: float
    composite_rank: str
    summary: str
    score_10: float = 0.0  # 1-10 十分制, 越大越好


def composite_to_score10(composite: float, max_possible: float) -> float:
    """将复合分转换为 1-10 十分制（越大越好）

    composite: 加权排名分 (越小越好), 理论范围 [1.0, max_possible]
    max_possible: 各层最大排名×权重的加权和
    """
    if max_possible <= 1.0:
        return 10.0
    raw = round(11.0 - composite * 10.0 / max_possible, 1)
    return max(1.0, min(10.0, raw))


def compute_greenblatt(
    ticker: str,
    ebit_ev: float | None,
    roic: float | None,
    f_score: int | None,
    peg: float | None,
    all_ebit_ev: dict[str, float],
    all_roic: dict[str, float],
    all_f_score: dict[str, int],
    all_peg: dict[str, float],
) -> RankingResult:
    """计算四层加权排名

    Args:
        ticker: 股票代码
        ebit_ev, roic, f_score, peg: 本标的数据
        all_*: 所有 8 家标的的数据 {ticker: value}
    """

    def rank_higher_better(values: dict[str, float], ticker: str, total: int) -> str:
        sorted_items = sorted(values.items(), key=lambda x: x[1] or 0, reverse=True)
        for i, (t, _) in enumerate(sorted_items, 1):
            if t == ticker:
                return f"#{i}/{len(sorted_items)}"
        return f"#{len(sorted_items)+1}/{len(sorted_items)+1}"

    def rank_lower_better(values: dict[str, float], ticker: str, total: int) -> str:
        sorted_items = sorted(values.items(), key=lambda x: x[1] or float('inf'))
        for i, (t, _) in enumerate(sorted_items, 1):
            if t == ticker:
                return f"#{i}/{len(sorted_items)}"
        return f"#{len(sorted_items)+1}/{len(sorted_items)+1}"

    total = len(all_ebit_ev)
    n = ebit_ev or 0.0
    l1_rank = rank_higher_better(all_ebit_ev, ticker, total)
    l1_rank_num = int(l1_rank.split('/')[0].replace('#', '')) if ticker in all_ebit_ev else total

    l2_rank = rank_higher_better(all_roic, ticker, total)
    l2_rank_num = int(l2_rank.split('/')[0].replace('#', '')) if ticker in all_roic else total

    l3_rank = rank_higher_better({k: float(v) for k, v in all_f_score.items()}, ticker, total)
    l3_rank_num = int(l3_rank.split('/')[0].replace('#', '')) if ticker in all_f_score else total

    l4_rank = rank_lower_better(all_peg, ticker, total)
    l4_rank_num = int(l4_rank.split('/')[0].replace('#', '')) if ticker in all_peg else total

    composite_score = (
        l1_rank_num * 0.40 +
        l2_rank_num * 0.25 +
        l3_rank_num * 0.25 +
        l4_rank_num * 0.10
    )

    all_scores = {}
    for t in all_ebit_ev:
        l1r_str = rank_higher_better(all_ebit_ev, t, total)
        l2r_str = rank_higher_better(all_roic, t, total)
        l3r_str = rank_higher_better({k: float(v) for k, v in all_f_score.items()}, t, total)
        l4r_str = rank_lower_better(all_peg, t, total)
        l1r = int(l1r_str.split('/')[0].replace('#', '')) if '#' in l1r_str else total
        l2r = int(l2r_str.split('/')[0].replace('#', '')) if '#' in l2r_str else total
        l3r = int(l3r_str.split('/')[0].replace('#', '')) if '#' in l3r_str else total
        l4r = int(l4r_str.split('/')[0].replace('#', '')) if '#' in l4r_str else total
        all_scores[t] = l1r * 0.40 + l2r * 0.25 + l3r * 0.25 + l4r * 0.10

    ranked = sorted(all_scores.items(), key=lambda x: x[1])
    composite_rank = f"#?/{total}"
    for i, (t, _) in enumerate(ranked, 1):
        if t == ticker:
            composite_rank = f"#{i}/{total}"
            break

    rows = [
        RankingRow(layer="L1", dimension="💰 便不便宜", metric="EBIT/EV",
                   value=f"{ebit_ev:.2f}%" if ebit_ev else "N/A",
                   weight="40%", rank=l1_rank,
                   verdict="深度价值核心" if l1_rank_num <= 3 else "偏贵"),
        RankingRow(layer="L2", dimension="🏭 赚不赚钱", metric="ROIC",
                   value=f"{roic:.1f}%" if roic else "N/A",
                   weight="25%", rank=l2_rank,
                   verdict="资本效率优秀" if l2_rank_num <= 3 else "资本效率一般"),
        RankingRow(layer="L3", dimension="🛡️ 会不会崩", metric="F-Score",
                   value=f"{f_score}/9" if f_score is not None else "N/A",
                   weight="25%", rank=l3_rank,
                   verdict="财务安全" if (f_score or 0) >= 6 else "财务有风险"),
        RankingRow(layer="L4", dimension="📈 增长值不值", metric="PEG",
                   value=f"{peg:.2f}x" if peg else "N/A",
                   weight="10%", rank=l4_rank,
                   verdict="增长划算" if (peg or 99) < 1 else "增长已定价"),
    ]

    summary = (
        f"加权综合 = {l1_rank_num}×40% + {l2_rank_num}×25% "
        f"+ {l3_rank_num}×25% + {l4_rank_num}×10% = {composite_score:.2f}"
    )

    max_possible = (
        len(all_ebit_ev) * 0.40 +
        len(all_roic) * 0.25 +
        len(all_f_score) * 0.25 +
        len(all_peg) * 0.10
    )
    score_10 = composite_to_score10(composite_score, max_possible)

    return RankingResult(
        rows=rows,
        composite_score=composite_score,
        composite_rank=composite_rank,
        summary=summary,
        score_10=score_10,
    )


def compute_crypto_ranking(
    mvrv_z: float,
    hash_rate_eh: float,
    f_score_adapted: int,
    days_since_halving: int,
    all_mvrv: dict[str, float],
    all_hash_rate: dict[str, float],
    all_f_score: dict[str, int],
    all_halving_days: dict[str, int],
) -> RankingResult:
    """BTC 专用四层排名 (加密适配)

    L1: MVRV Z-Score (越低越便宜, historical top >7, bottom <0)
    L2: 网络强度 (算力 EH/s, 越高越强)
    L3: 改编 F-Score (链上指标 0-9)
    L4: 减半周期位置 (距下一次减半天数, 越近越好)
    """

    def rank_lower(values: dict[str, float], ticker: str) -> str:
        sorted_items = sorted(values.items(), key=lambda x: x[1] or float('inf'))
        for i, (t, _) in enumerate(sorted_items, 1):
            if t == ticker:
                return f"#{i}/{len(sorted_items)}"
        return f"#?/{len(sorted_items)}"

    def rank_higher(values: dict[str, float], ticker: str) -> str:
        sorted_items = sorted(values.items(), key=lambda x: x[1] or 0, reverse=True)
        for i, (t, _) in enumerate(sorted_items, 1):
            if t == ticker:
                return f"#{i}/{len(sorted_items)}"
        return f"#?/{len(sorted_items)}"

    total = len(all_mvrv)

    l1_rank = rank_lower(all_mvrv, 'BTC')
    l2_rank = rank_higher(all_hash_rate, 'BTC')
    l3_rank = rank_higher({k: float(v) for k, v in all_f_score.items()}, 'BTC')
    l4_rank = rank_lower(all_halving_days, 'BTC')

    l1r = int(l1_rank.split('/')[0].replace('#', ''))
    l2r = int(l2_rank.split('/')[0].replace('#', ''))
    l3r = int(l3_rank.split('/')[0].replace('#', ''))
    l4r = int(l4_rank.split('/')[0].replace('#', ''))

    composite_score = l1r * 0.40 + l2r * 0.25 + l3r * 0.25 + l4r * 0.10

    rows = [
        RankingRow(layer="L1", dimension="💰 便不便宜", metric="MVRV Z-Score",
                   value=f"{mvrv_z:.2f}", weight="40%", rank=l1_rank,
                   verdict="深度低估" if mvrv_z < 1 else ("严重高估" if mvrv_z > 5 else "估值适中")),
        RankingRow(layer="L2", dimension="🏭 网络强度", metric="Hash Rate",
                   value=f"{hash_rate_eh:.0f} EH/s", weight="25%", rank=l2_rank,
                   verdict="网络极强" if hash_rate_eh > 800 else "网络安全"),
        RankingRow(layer="L3", dimension="🛡️ 会不会崩", metric="F-Score(链上)",
                   value=f"{f_score_adapted}/9", weight="25%", rank=l3_rank,
                   verdict="链上健康" if f_score_adapted >= 6 else "链上有风险"),
        RankingRow(layer="L4", dimension="📈 减半周期", metric="距下次减半天数",
                   value=f"{days_since_halving}天", weight="10%", rank=l4_rank,
                   verdict="周期有利" if days_since_halving < 600 else "周期中性"),
    ]

    summary = (
        f"加权综合 = {l1r}×40% + {l2r}×25% "
        f"+ {l3r}×25% + {l4r}×10% = {composite_score:.2f}"
    )

    max_possible = (
        len(all_mvrv) * 0.40 +
        len(all_hash_rate) * 0.25 +
        len(all_f_score) * 0.25 +
        len(all_halving_days) * 0.10
    )
    score_10 = composite_to_score10(composite_score, max_possible)

    return RankingResult(
        rows=rows,
        composite_score=composite_score,
        composite_rank="",
        summary=summary,
        score_10=score_10,
    )
