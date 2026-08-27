"""Persist successful provider windows, including empty/sparse results."""
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op

revision = "0018_acquisition_windows"
down_revision = "0017_session_policy_v2"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "historical_acquisition_windows",
        sa.Column("venue_instrument_id", sa.UUID(), sa.ForeignKey("venue_instruments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("resolution", sa.String(3), nullable=False),
        sa.Column("components", sa.String(20), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("request_identity", sa.String(64), nullable=False),
        sa.Column("returned_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("venue_instrument_id", "resolution", "components", "start_time", "end_time"),
        sa.CheckConstraint("resolution IN ('M1','M15')", name="acquisition_resolution"),
        sa.CheckConstraint("outcome IN ('SUCCESS_EMPTY_OR_SPARSE','PROVIDER_FAILURE','UNKNOWN_OUTCOME')", name="acquisition_outcome"),
        sa.CheckConstraint("end_time > start_time", name="acquisition_range"),
    )

def downgrade() -> None:
    op.drop_table("historical_acquisition_windows")
