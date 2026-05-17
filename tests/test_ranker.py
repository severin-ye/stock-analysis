from stock_analysis.data.fetcher import PriceSnapshot
from stock_analysis.ranking.greenblatt import (
    apply_cross_asset_scores,
    composite_to_score10,
    compute_crypto_ranking,
    compute_greenblatt,
    compute_pos_crypto_ranking,
)


def test_singleton_composite_score_maps_to_neutral_not_perfect():
    assert composite_to_score10(1.0, 1.0) == 5.5


def test_apply_cross_asset_scores_replaces_singleton_scores_with_global_ranks():
    prices = {
        'NVDA': PriceSnapshot(ticker='NVDA', ebit_ev='3.50%', roic='30.0%', peg_ratio='0.80x', f_score=7),
        'BTC': PriceSnapshot(ticker='BTC', mvrv_z_score=0.97, hash_rate_eh=1034.0, days_since_halving=752, f_score=2),
        'ETH': PriceSnapshot(ticker='ETH', mcap_tvl_ratio=6.15, staking_ratio=28.2, supply_inflation=0.5, f_score=6),
    }

    rankings = {
        'NVDA': compute_greenblatt(
            'NVDA',
            prices['NVDA'].ebit_ev_num,
            prices['NVDA'].roic_num,
            prices['NVDA'].f_score,
            prices['NVDA'].peg_num,
            {'NVDA': prices['NVDA'].ebit_ev_num},
            {'NVDA': prices['NVDA'].roic_num},
            {'NVDA': prices['NVDA'].f_score},
            {'NVDA': prices['NVDA'].peg_num},
        ),
        'BTC': compute_crypto_ranking(
            prices['BTC'].mvrv_z_score,
            prices['BTC'].hash_rate_eh,
            prices['BTC'].f_score,
            prices['BTC'].days_since_halving,
            {'BTC': prices['BTC'].mvrv_z_score},
            {'BTC': prices['BTC'].hash_rate_eh},
            {'BTC': prices['BTC'].f_score},
            {'BTC': prices['BTC'].days_since_halving},
        ),
        'ETH': compute_pos_crypto_ranking(
            'ETH',
            prices['ETH'].mcap_tvl_ratio,
            prices['ETH'].staking_ratio,
            prices['ETH'].f_score,
            prices['ETH'].supply_inflation,
            {'ETH': prices['ETH'].mcap_tvl_ratio},
            {'ETH': prices['ETH'].staking_ratio},
            {'ETH': prices['ETH'].f_score},
            {'ETH': prices['ETH'].supply_inflation},
        ),
    }

    apply_cross_asset_scores(prices, rankings)

    assert rankings['BTC'].score_10 < 10.0
    assert rankings['BTC'].score_10 < 10.0
    assert rankings['ETH'].score_10 < 10.0
    assert all(rankings[t].composite_rank.endswith('/3') for t in rankings)
    assert len({rankings[t].composite_rank for t in rankings}) == 3
