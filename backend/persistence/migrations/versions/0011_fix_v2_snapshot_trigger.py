"""Fix V2 membership trigger dispatch for table-specific NEW fields."""

# fmt: off
# ruff: noqa: E501
from alembic import op

revision = "0011_fix_v2_snapshot_trigger"
down_revision = "0010_experiment_gap_decisions"
branch_labels = None
depends_on = None


def _create_guard() -> None:
    op.execute("""CREATE FUNCTION snapshot_v2_append_only_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'dataset snapshot memberships are immutable'; END IF; IF NOT EXISTS (SELECT 1 FROM dataset_snapshots WHERE id = NEW.dataset_snapshot_id AND snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2') THEN RAISE EXCEPTION 'V2 membership requires a V2 snapshot'; END IF; IF TG_TABLE_NAME = 'dataset_snapshot_execution_observations' THEN IF NOT EXISTS (SELECT 1 FROM market_bars WHERE id = NEW.market_bar_id AND resolution = 'M1' AND price_component = NEW.price_component AND complete IS TRUE) THEN RAISE EXCEPTION 'execution membership must reference a completed matching M1 observation'; END IF; END IF; RETURN NEW; END; $$""")


def upgrade() -> None:
    for table in ("dataset_snapshot_analytical_bars", "dataset_snapshot_execution_observations", "dataset_snapshot_gaps"):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.execute("DROP FUNCTION snapshot_v2_append_only_guard()")
    _create_guard()
    for table in ("dataset_snapshot_analytical_bars", "dataset_snapshot_execution_observations", "dataset_snapshot_gaps"):
        op.execute(f"CREATE TRIGGER {table}_append_only BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION snapshot_v2_append_only_guard()")


def downgrade() -> None:
    for table in ("dataset_snapshot_analytical_bars", "dataset_snapshot_execution_observations", "dataset_snapshot_gaps"):
        op.execute(f"DROP TRIGGER {table}_append_only ON {table}")
    op.execute("DROP FUNCTION snapshot_v2_append_only_guard()")
    op.execute("""CREATE FUNCTION snapshot_v2_append_only_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'dataset snapshot memberships are immutable'; END IF; IF NOT EXISTS (SELECT 1 FROM dataset_snapshots WHERE id = NEW.dataset_snapshot_id AND snapshot_schema = 'ATLAS_HISTORICAL_SIMULATION_SNAPSHOT_V2') THEN RAISE EXCEPTION 'V2 membership requires a V2 snapshot'; END IF; IF TG_TABLE_NAME = 'dataset_snapshot_execution_observations' AND NOT EXISTS (SELECT 1 FROM market_bars WHERE id = NEW.market_bar_id AND resolution = 'M1' AND price_component = NEW.price_component AND complete IS TRUE) THEN RAISE EXCEPTION 'execution membership must reference a completed matching M1 observation'; END IF; RETURN NEW; END; $$""")
    for table in ("dataset_snapshot_analytical_bars", "dataset_snapshot_execution_observations", "dataset_snapshot_gaps"):
        op.execute(f"CREATE TRIGGER {table}_append_only BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION snapshot_v2_append_only_guard()")
