"""Fix transition-table validation for tables without execution columns."""

# ruff: noqa: E501

from alembic import op

revision = "0020_fix_snapshot_guard"
down_revision = "0019_snapshot_insert_guard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE OR REPLACE FUNCTION snapshot_v2_insert_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF EXISTS (
            SELECT 1 FROM new_rows n
            LEFT JOIN dataset_snapshots s ON s.id = n.dataset_snapshot_id
              AND s.snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2'
            WHERE s.id IS NULL
          ) THEN
            RAISE EXCEPTION 'V2 membership requires a V2 snapshot';
          END IF;
          IF TG_TABLE_NAME = 'dataset_snapshot_execution_observations'
             AND EXISTS (
               SELECT 1 FROM new_rows n
               LEFT JOIN market_bars m ON m.id = (to_jsonb(n)->>'market_bar_id')::uuid
                 AND m.resolution = 'M1'
                 AND m.price_component = to_jsonb(n)->>'price_component'
                 AND m.complete IS TRUE
               WHERE m.id IS NULL
             ) THEN
            RAISE EXCEPTION 'execution membership must reference a completed matching M1 observation';
          END IF;
          RETURN NULL;
        END; $$"""
    )


def downgrade() -> None:
    # 0019's function is restored by its downgrade path.
    pass
