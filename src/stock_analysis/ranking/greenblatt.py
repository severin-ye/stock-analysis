"""纯数学四层加权排名计算 — 不需要 LLM

实现 InvestSkill v3.0 定义的四层加权排名公式:
  L1: EBIT/EV (40%) — 从高到低排名
  L2: ROIC (25%) — 从高到低排名
  L3: F-Score (25%) — 从高到低排名
  L4: PEG (10%) — 从低到高排名

综合分 = L1排名×0.40 + L2×0.25 + L3×0.25 + L4×0.10 (越小越好)
"""

from dataclasses import dataclass

from stock_analysis.data.fetcher import PriceSnapshot

LAYER_WEIGHTS = {"L1": "40%", "L2": "25%", "L3": "25%", "L4": "10%"}
NUMERIC_LAYER_WEIGHTS = {"L1": 0.40, "L2": 0.25, "L3": 0.25, "L4": 0.10}
NEUTRAL_SCORE_10 = 5.5


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
        return NEUTRAL_SCORE_10
    raw = round(11.0 - composite * 10.0 / max_possible, 1)
    return max(1.0, min(10.0, raw))


def _score_from_anchors(value: float | None, anchors: list[tuple[float, float]]) -> float:
    if value is None:
        return NEUTRAL_SCORE_10

    ordered = sorted(anchors, key=lambda item: item[0])
    if value <= ordered[0][0]:
        return ordered[0][1]
    if value >= ordered[-1][0]:
        return ordered[-1][1]

    for (x1, y1), (x2, y2) in zip(ordered, ordered[1:]):
        if value <= x2:
            if x2 == x1:
                return y2
            ratio = (value - x1) / (x2 - x1)
            return round(y1 + (y2 - y1) * ratio, 1)

    return ordered[-1][1]


def _score_linear(value: int, max_value: int) -> float:
    bounded = max(0, min(max_value, value))
    return round(1.0 + 9.0 * bounded / max_value, 1)


def _equity_layer_scores(info: PriceSnapshot) -> dict[str, float]:
    return {
        "L1": _score_from_anchors(info.ebit_ev_num, [
            (0.0, 1.0), (0.5, 2.0), (1.5, 3.5), (3.0, 5.5), (5.0, 7.5), (8.0, 10.0),
        ]),
        "L2": _score_from_anchors(info.roic_num, [
            (0.0, 1.0), (5.0, 3.0), (10.0, 5.0), (20.0, 7.5), (30.0, 9.0), (50.0, 10.0),
        ]),
        "L3": _score_linear(info.f_score, 9),
        "L4": NEUTRAL_SCORE_10 if (info.peg_num is not None and info.peg_num < 0) else _score_from_anchors(info.peg_num, [
            (0.0, 10.0), (0.5, 9.0), (1.0, 8.0), (2.0, 5.0), (3.0, 3.0), (4.0, 1.0),
        ]),
    }


def _btc_layer_scores(info: PriceSnapshot) -> dict[str, float]:
    return {
        "L1": _score_from_anchors(info.mvrv_z_score, [
            (0.0, 10.0), (0.5, 9.0), (1.0, 8.0), (2.0, 6.0), (3.0, 4.0), (5.0, 1.0),
        ]),
        "L2": _score_from_anchors(info.hash_rate_eh, [
            (200.0, 2.0), (400.0, 4.0), (600.0, 6.0), (800.0, 8.0), (1000.0, 10.0),
        ]),
        "L3": _score_linear(info.f_score, 9),
        "L4": _score_from_anchors(info.days_since_halving, [
            (0.0, 10.0), (180.0, 9.0), (360.0, 8.0), (540.0, 6.5), (720.0, 5.0), (900.0, 3.5), (1200.0, 1.0),
        ]),
    }


def _pos_crypto_layer_scores(info: PriceSnapshot) -> dict[str, float]:
    return {
        "L1": _score_from_anchors(info.mcap_tvl_ratio, [
            (1.0, 10.0), (2.0, 9.0), (4.0, 7.5), (6.0, 6.0), (8.0, 5.0), (12.0, 3.0), (16.0, 1.0),
        ]),
        "L2": _score_from_anchors(info.staking_ratio, [
            (10.0, 1.0), (20.0, 3.0), (35.0, 6.0), (50.0, 8.0), (70.0, 10.0),
        ]),
        "L3": _score_linear(info.f_score, 6),
        "L4": _score_from_anchors(info.supply_inflation, [
            (-2.0, 10.0), (0.0, 9.0), (1.0, 8.0), (3.0, 6.0), (6.0, 3.0), (10.0, 1.0),
        ]),
    }


def build_cross_asset_layer_scores(info: PriceSnapshot) -> dict[str, float]:
    if info.ticker == 'BTC':
        return _btc_layer_scores(info)
    if info.ticker in {'ETH', 'SOL', 'BNB'}:
        return _pos_crypto_layer_scores(info)
    return _equity_layer_scores(info)


def score_snapshot_on_10(info: PriceSnapshot) -> float:
    layer_scores = build_cross_asset_layer_scores(info)
    score = sum(layer_scores[layer] * weight for layer, weight in NUMERIC_LAYER_WEIGHTS.items())
    return round(max(1.0, min(10.0, score)), 1)


def apply_cross_asset_scores(
    prices: dict[str, PriceSnapshot],
    rankings: dict[str, RankingResult],
) -> dict[str, RankingResult]:
    scored: list[tuple[str, float]] = []

    for ticker, rank in rankings.items():
        info = prices.get(ticker)
        if not info:
            continue
        score_10 = score_snapshot_on_10(info)
        rank.score_10 = score_10
        base_summary = rank.summary.split(" | 统一十分制 ")[0]
        rank.summary = f"{base_summary} | 统一十分制 {score_10:.1f}/10"
        scored.append((ticker, score_10))

    total = len(scored)
    for i, (ticker, _) in enumerate(sorted(scored, key=lambda item: (-item[1], item[0])), 1):
        rank = rankings[ticker]
        rank.composite_rank = f"#{i}/{total}"
        base_summary = rank.summary.split(" | 总榜 ")[0]
        rank.summary = f"{base_summary} | 总榜 {rank.composite_rank}"

    return rankings


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
        sorted_items = sorted(values.items(), key=lambda x: (-(x[1] or 0), x[0]))
        for i, (t, _) in enumerate(sorted_items, 1):
            if t == ticker:
                return f"#{i}/{len(sorted_items)}"
        return f"#{len(sorted_items)+1}/{len(sorted_items)+1}"

    def rank_lower_better(values: dict[str, float], ticker: str, total: int) -> str:
        sorted_items = sorted(values.items(), key=lambda x: (x[1] or float('inf'), x[0]))
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

    ranked = sorted(all_scores.items(), key=lambda x: (x[1], x[0]))
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
        sorted_items = sorted(values.items(), key=lambda x: (x[1] or float('inf'), x[0]))
        for i, (t, _) in enumerate(sorted_items, 1):
            if t == ticker:
                return f"#{i}/{len(sorted_items)}"
        return f"#?/{len(sorted_items)}"

    def rank_higher(values: dict[str, float], ticker: str) -> str:
        sorted_items = sorted(values.items(), key=lambda x: (-(x[1] or 0), x[0]))
        for i, (t, _) in enumerate(sorted_items, 1):
            if t == ticker:
                return f"#{i}/{len(sorted_items)}"
        return f"#?/{len(sorted_items)}"

    total = len(all_mvrv)

    l1_rank = rank_lower(all_mvrv, 'BTC')
    l2_rank = rank_higher(all_hash_rate, 'BTC')
    l3_rank = rank_higher({k: float(v) for k, v in all_f_score.items()}, 'BTC')
    l4_rank = rank_lower(all_halving_days, 'BTC')

    def _parse_rank(rank_str: str, total: int) -> int:
        try:
            return int(rank_str.split('/')[0].replace('#', ''))
        except ValueError:
            return total

    l1r = _parse_rank(l1_rank, total)
    l2r = _parse_rank(l2_rank, total)
    l3r = _parse_rank(l3_rank, total)
    l4r = _parse_rank(l4_rank, total)

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


def compute_pos_crypto_ranking(
    ticker: str,
    mcap_tvl_ratio: float,
    staking_ratio: float,
    f_score: int,
    supply_inflation: float,
    all_mcap_tvl: dict[str, float],
    all_staking: dict[str, float],
    all_f_score: dict[str, int],
    all_inflation: dict[str, float],
) -> RankingResult:
    """PoS L1 加密四层排名 (ETH, SOL, BNB)

    L1: Market Cap / TVL (越低越便宜)
    L2: Staking 比率 (越高网络越安全)
    L3: Crypto F-Score (0-6, 越高越健康)
    L4: 年通胀率 (越低越好, 通缩>0%低通胀>高通胀)
    """

    def rank_lower(values: dict[str, float], t: str) -> str:
        sorted_items = sorted(values.items(), key=lambda x: (x[1] or float('inf'), x[0]))
        for i, (k, _) in enumerate(sorted_items, 1):
            if k == t:
                return f"#{i}/{len(sorted_items)}"
        return f"#?/{len(sorted_items)}"

    def rank_higher(values: dict[str, float], t: str) -> str:
        sorted_items = sorted(values.items(), key=lambda x: (-(x[1] or 0), x[0]))
        for i, (k, _) in enumerate(sorted_items, 1):
            if k == t:
                return f"#{i}/{len(sorted_items)}"
        return f"#?/{len(sorted_items)}"

    total = len(all_mcap_tvl)

    l1_rank = rank_lower(all_mcap_tvl, ticker)
    l2_rank = rank_higher(all_staking, ticker)
    l3_rank = rank_higher({k: float(v) for k, v in all_f_score.items()}, ticker)
    l4_rank = rank_lower(all_inflation, ticker)

    def _parse_rank(rank_str: str, total: int) -> int:
        try:
            return int(rank_str.split('/')[0].replace('#', ''))
        except ValueError:
            return total

    l1r = _parse_rank(l1_rank, total)
    l2r = _parse_rank(l2_rank, total)
    l3r = _parse_rank(l3_rank, total)
    l4r = _parse_rank(l4_rank, total)

    composite_score = l1r * 0.40 + l2r * 0.25 + l3r * 0.25 + l4r * 0.10

    rows = [
        RankingRow(layer="L1", dimension="💰 便不便宜", metric="MCap/TVL",
                   value=f"{mcap_tvl_ratio:.2f}", weight="40%", rank=l1_rank,
                   verdict="估值偏低" if mcap_tvl_ratio < 3 else ("估值偏高" if mcap_tvl_ratio > 8 else "估值适中")),
        RankingRow(layer="L2", dimension="🏭 网络强度", metric="Staking比率",
                   value=f"{staking_ratio:.1f}%", weight="25%", rank=l2_rank,
                   verdict="高度安全" if staking_ratio > 50 else "网络安全"),
        RankingRow(layer="L3", dimension="🛡️ 链上健康", metric="Crypto F-Score",
                   value=f"{f_score}/6", weight="25%", rank=l3_rank,
                   verdict="链上健康" if f_score >= 4 else "链上有风险"),
        RankingRow(layer="L4", dimension="📈 供给压力", metric="年通胀率",
                   value=f"{supply_inflation:.1f}%", weight="10%", rank=l4_rank,
                   verdict="通缩/低通胀" if supply_inflation < 2 else ("高通胀" if supply_inflation > 8 else "温和通胀")),
    ]

    summary = (
        f"加权综合 = {l1r}×40% + {l2r}×25% "
        f"+ {l3r}×25% + {l4r}×10% = {composite_score:.2f}"
    )

    max_possible = (
        len(all_mcap_tvl) * 0.40 +
        len(all_staking) * 0.25 +
        len(all_f_score) * 0.25 +
        len(all_inflation) * 0.10
    )
    score_10 = composite_to_score10(composite_score, max_possible)

    return RankingResult(
        rows=rows,
        composite_score=composite_score,
        composite_rank="",
        summary=summary,
        score_10=score_10,
    )
