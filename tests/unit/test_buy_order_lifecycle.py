"""
Regressietests voor de levenscyclus van buy-orders.

De bug van september 2026: DOT handelde 26% boven zijn buy-level. De runner zag
alleen "prijs is weggelopen van de order", cancelde en plaatste dezelfde
onbereikbare order terug. Elke run opnieuw, terwijl die order cash en een van de
twee koopslots bezet hield zonder realistische kans op een fill.
"""

from __future__ import annotations

from rangebot.config.settings import (
    KRAKEN_MAX_BUY_DISTANCE_PCT,
    ORDER_MAX_AGE_HOURS,
    ORDER_STALE_PRICE_THRESHOLD,
    ORDER_UPDATE_THRESHOLD,
)
from rangebot.strategy.range_strategy import (
    BUY_ORDER_ABANDON,
    BUY_ORDER_KEEP,
    BUY_ORDER_PLACE,
    BUY_ORDER_REPLACE_AGED,
    BUY_ORDER_REPLACE_STALE_PRICE,
    BUY_ORDER_UPDATE_LEVEL,
    buy_level_distance_frac,
    decide_buy_order_action,
    is_buy_level_reachable,
    select_top_symbols_from_scores,
)


def _decide(**kwargs) -> str:
    params = {
        "buy_level": 10.0,
        "current_price": 10.2,
        "existing_order_price": 10.0,
        "order_age_hours": 1.0,
        "max_buy_distance_frac": KRAKEN_MAX_BUY_DISTANCE_PCT,
    }
    params.update(kwargs)
    return decide_buy_order_action(**params)


def test_zonder_order_wordt_er_geplaatst() -> None:
    assert _decide(existing_order_price=None) == BUY_ORDER_PLACE


def test_order_binnen_marges_blijft_staan() -> None:
    assert _decide(current_price=10.05, existing_order_price=10.0) == BUY_ORDER_KEEP


def test_weggelopen_koers_vervangt_de_order() -> None:
    prijs = 10.0 * (1 + ORDER_STALE_PRICE_THRESHOLD) + 0.01
    assert _decide(current_price=prijs, existing_order_price=10.0) == (
        BUY_ORDER_REPLACE_STALE_PRICE
    )


def test_oude_order_wordt_vervangen() -> None:
    assert _decide(order_age_hours=ORDER_MAX_AGE_HOURS) == BUY_ORDER_REPLACE_AGED


def test_verschoven_level_werkt_de_order_bij() -> None:
    nieuw_level = 10.0 * (1 + ORDER_UPDATE_THRESHOLD * 2)
    assert _decide(buy_level=nieuw_level, current_price=10.1) == (
        BUY_ORDER_UPDATE_LEVEL
    )


def test_onbereikbaar_level_wordt_opgegeven() -> None:
    prijs = 10.0 * (1 + KRAKEN_MAX_BUY_DISTANCE_PCT) + 0.01
    assert _decide(buy_level=10.0, current_price=prijs) == BUY_ORDER_ABANDON


def test_opgeven_gaat_voor_vervangen() -> None:
    """
    De kern van de bug: beide condities zijn waar. Vervangen zet dezelfde
    onbereikbare order terug, opgeven maakt cash en het slot vrij.
    """
    assert (
        _decide(
            buy_level=0.9770275,
            current_price=1.2299,
            existing_order_price=0.9770275,
            order_age_hours=2.0,
        )
        == BUY_ORDER_ABANDON
    )


def test_dot_situatie_8_september() -> None:
    """Run-audit 18:25 UTC: DOT buy-level $0.9770, koers $1.2299 (+25,9%)."""
    assert buy_level_distance_frac(1.2299, 0.9770275) > 0.25
    assert not is_buy_level_reachable(1.2299, 0.9770275, KRAKEN_MAX_BUY_DISTANCE_PCT)


def test_uni_situatie_blijft_binnen_bereik() -> None:
    """Zelfde run: UNI stond 1,3% boven zijn buy-level en mag gewoon door."""
    assert is_buy_level_reachable(6.9143, 6.824151, KRAKEN_MAX_BUY_DISTANCE_PCT)


def test_zonder_koers_geen_opgave() -> None:
    """Een ontbrekende quote mag geen order opruimen."""
    assert _decide(current_price=None, existing_order_price=10.0) == BUY_ORDER_KEEP
    assert _decide(current_price=None, existing_order_price=None) == BUY_ORDER_PLACE
    assert buy_level_distance_frac(None, 10.0) is None
    assert is_buy_level_reachable(None, 10.0, 0.10)


def test_selectie_slaat_onbereikbare_kandidaat_over() -> None:
    scored = {
        "DOT/USD": (0.9770275, 1.09194867, 0.99),
        "UNI/USD": (6.824151, 7.18078667, 0.10),
    }
    prices = {"DOT/USD": 1.2299, "UNI/USD": 6.9143}
    selected, levels = select_top_symbols_from_scores(
        scored,
        set(),
        1,
        current_prices=prices,
        max_buy_distance_frac=KRAKEN_MAX_BUY_DISTANCE_PCT,
    )
    # DOT scoort hoger maar is onbereikbaar; het slot gaat naar UNI.
    assert selected == ["UNI/USD"]
    assert "DOT/USD" not in levels


def test_positie_houdt_slot_ook_buiten_bereik() -> None:
    scored = {"DOT/USD": (0.9770275, 1.09194867, 0.99)}
    selected, levels = select_top_symbols_from_scores(
        scored,
        {"DOT/USD"},
        1,
        current_prices={"DOT/USD": 1.2299},
        max_buy_distance_frac=KRAKEN_MAX_BUY_DISTANCE_PCT,
    )
    assert selected == ["DOT/USD"]
    assert "DOT/USD" in levels


def test_selectie_zonder_afstandsfilter_ongewijzigd() -> None:
    scored = {
        "DOT/USD": (0.9770275, 1.09194867, 0.99),
        "UNI/USD": (6.824151, 7.18078667, 0.10),
    }
    selected, _ = select_top_symbols_from_scores(scored, set(), 1)
    assert selected == ["DOT/USD"]
