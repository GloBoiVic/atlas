"""Validate V2 membership inserts once per bounded statement, not per row."""

# ruff: noqa: E501

from alembic import op

revision = "0019_snapshot_insert_guard"
down_revision = "0018_acquisition_windows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in (
        "dataset_snapshot_analytical_bars",
        "dataset_snapshot_execution_observations",
        "dataset_snapshot_gaps",
    ):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.execute("DROP FUNCTION snapshot_v2_append_only_guard()")
    op.execute(
        """CREATE FUNCTION snapshot_v2_append_only_guard() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          IF TG_OP = 'INSERT' THEN
            RAISE EXCEPTION 'insert validation must use the statement trigger';
          END IF;
          RAISE EXCEPTION 'dataset snapshot memberships are immutable';
        END; $$"""
    )
    op.execute(
        """CREATE FUNCTION snapshot_v2_insert_guard() RETURNS trigger
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
    for table in (
        "dataset_snapshot_analytical_bars",
        "dataset_snapshot_execution_observations",
        "dataset_snapshot_gaps",
    ):
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION snapshot_v2_append_only_guard()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_insert_guard AFTER INSERT ON {table} "
            "REFERENCING NEW TABLE AS new_rows FOR EACH STATEMENT "
            "EXECUTE FUNCTION snapshot_v2_insert_guard()"
        )


def downgrade() -> None:
    for table in (
        "dataset_snapshot_analytical_bars",
        "dataset_snapshot_execution_observations",
        "dataset_snapshot_gaps",
    ):
        op.execute(f"DROP TRIGGER {table}_insert_guard ON {table}")
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.execute("DROP FUNCTION snapshot_v2_insert_guard()")
    op.execute("DROP FUNCTION snapshot_v2_append_only_guard()")
    op.execute(
        """CREATE FUNCTION snapshot_v2_append_only_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'dataset snapshot memberships are immutable'; END IF;
        IF NOT EXISTS (SELECT 1 FROM dataset_snapshots WHERE id = NEW.dataset_snapshot_id AND snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2') THEN RAISE EXCEPTION 'V2 membership requires a V2 snapshot'; END IF;
        IF TG_TABLE_NAME = 'dataset_snapshot_execution_observations' AND NOT EXISTS (SELECT 1 FROM market_bars WHERE id = NEW.market_bar_id AND resolution = 'M1' AND price_component = NEW.price_component AND complete IS TRUE) THEN RAISE EXCEPTION 'execution membership must reference a completed matching M1 observation'; END IF;
        RETURN NEW; END; $$"""
    )
    for table in (
        "dataset_snapshot_analytical_bars",
        "dataset_snapshot_execution_observations",
        "dataset_snapshot_gaps",
    ):
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION snapshot_v2_append_only_guard()"
        )
