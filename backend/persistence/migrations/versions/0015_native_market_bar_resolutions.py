"""Allow canonical provider-native M1 and M15 observations."""

from alembic import op

revision = "0015_native_resolutions"
down_revision = "0014_result_metric_state_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("m1_only", "market_bars", type_="check")
    op.drop_constraint("exact_one_minute", "market_bars", type_="check")
    op.drop_constraint("minute_aligned_start", "market_bars", type_="check")
    op.create_check_constraint(
        "supported_resolution", "market_bars", "resolution IN ('M1', 'M15')"
    )
    op.create_check_constraint(
        "native_aligned_start",
        "market_bars",
        "start_time = date_trunc('minute', start_time) AND "
        "(resolution = 'M1' OR extract(minute from start_time)::integer % 15 = 0)",
    )
    op.create_check_constraint(
        "exact_native_interval",
        "market_bars",
        "(resolution = 'M1' AND end_time = start_time + interval '1 minute') "
        "OR (resolution = 'M15' AND end_time = start_time + interval '15 minutes')",
    )


def downgrade() -> None:
    op.drop_constraint("exact_native_interval", "market_bars", type_="check")
    op.drop_constraint("native_aligned_start", "market_bars", type_="check")
    op.drop_constraint("supported_resolution", "market_bars", type_="check")
    op.create_check_constraint("m1_only", "market_bars", "resolution = 'M1'")
    op.create_check_constraint(
        "exact_one_minute", "market_bars", "end_time = start_time + interval '1 minute'"
    )
    op.create_check_constraint(
        "minute_aligned_start",
        "market_bars",
        "start_time = date_trunc('minute', start_time)",
    )
