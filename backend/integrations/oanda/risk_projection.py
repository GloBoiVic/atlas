"""Pure projections from normalized OANDA observations into Risk inputs."""

from backend.risk import AccountState

from .account import OandaPracticeAccountSummarySnapshot


def project_oanda_practice_account_state(
    summary: OandaPracticeAccountSummarySnapshot,
) -> AccountState:
    """Project the account facts required by Risk without performing I/O."""
    return AccountState(
        base_currency=summary.identity.base_currency,
        equity=summary.nav,
    )
