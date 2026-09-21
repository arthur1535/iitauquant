from decimal import Decimal

from automation.demo import replay_paper_orders, synthetic_history


def test_causal_backtest_fills_reconcile_through_signed_webhooks(tmp_path):
    report = replay_paper_orders(synthetic_history(180), tmp_path)
    assert report["orders_accepted"] >= 4
    assert report["duplicates_rejected"] == report["orders_accepted"]
    assert report["unsigned_http"] == 401
    assert report["account"]["fill_count"] == report["orders_accepted"]
    assert Decimal(report["account"]["fees_paid_brl"]) > 0
    assert report["reconciliation_error_brl"] < 0.0001
    assert report["broker_connected"] is False
