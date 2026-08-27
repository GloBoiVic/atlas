"""Allow the source-pinned OANDA 2025 holiday session policy."""
# ruff: noqa: E501

from alembic import op

revision = "0017_session_policy_v2"
down_revision = "0016_load_progress"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("session_policy_v1", "dataset_snapshots", type_="check")
    op.drop_constraint("valid_integrity_summary", "dataset_snapshots", type_="check")
    op.create_check_constraint(
        "session_policy_v1",
        "dataset_snapshots",
        "session_policy IN ('OANDA_FX_NY_V1', 'OANDA_FX_NY_V2')",
    )
    op.create_check_constraint(
        "valid_integrity_summary",
        "dataset_snapshots",
        "jsonb_typeof(integrity_summary) = 'object' AND integrity_summary->>'status' = 'VALID' AND ((snapshot_schema = 'ATLAS_HISTORICAL_SNAPSHOT_V1' AND integrity_summary ?& ARRAY['expected_open_minutes','expected_closure_minutes','member_minutes','bar_count','unexpected_gap_count','unexpected_observation_count','session_policy'] AND integrity_summary->>'session_policy' IN ('OANDA_FX_NY_V1', 'OANDA_FX_NY_V2')) OR (snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2' AND integrity_summary->>'policy_version' = 'ATLAS_HISTORICAL_GAP_POLICY_V1'))",
    )


def downgrade() -> None:
    # Refuse only when a durable snapshot would become invalid under the V1
    # policy.  Migration-cycle fixtures can safely clear their disposable
    # snapshot state before downgrade; immutable snapshot DML guards remain
    # installed throughout that teardown.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM dataset_snapshots
                WHERE session_policy = 'OANDA_FX_NY_V2'
            ) THEN
                RAISE EXCEPTION
                    'cannot downgrade while V2-policy snapshots exist';
            END IF;
        END $$
        """
    )
