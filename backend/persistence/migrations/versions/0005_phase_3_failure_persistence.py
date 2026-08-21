"""Persist categorized, sanitized terminal Experiment failures."""

# fmt: off
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op

revision = "0005_phase_3_failure_persistence"
down_revision = "0004_phase_3_first_trade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("experiments", sa.Column("failure_category", sa.String(20), nullable=True))
    op.add_column("experiments", sa.Column("failure_code", sa.String(80), nullable=True))
    op.add_column("experiments", sa.Column("failure_detail", sa.String(500), nullable=True))
    op.create_check_constraint(
        "valid_failure_category", "experiments",
        "failure_category IS NULL OR failure_category IN ('VALIDATION', 'MARKET_DATA', 'STRATEGY', 'RISK', 'EXECUTION', 'PERSISTENCE')",
    )
    op.create_check_constraint("sanitized_failure_code", "experiments", "failure_code IS NULL OR failure_code ~ '^[A-Z0-9_]+$'")
    op.create_check_constraint("sanitized_failure_detail", "experiments", "failure_detail IS NULL OR (length(failure_detail) BETWEEN 1 AND 500 AND failure_detail !~ '[[:cntrl:]]')")
    op.create_check_constraint(
        "failure_consistency", "experiments",
        "(status = 'FAILED' AND failure_category IS NOT NULL AND failure_code IS NOT NULL AND failure_detail IS NOT NULL) OR (status <> 'FAILED' AND failure_category IS NULL AND failure_code IS NULL AND failure_detail IS NULL)",
    )
    op.execute("DROP TRIGGER experiments_immutable_config ON experiments")
    op.execute("DROP FUNCTION prevent_experiment_config_mutation()")
    op.execute("""CREATE FUNCTION prevent_experiment_config_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'experiments are immutable'; END IF; IF (to_jsonb(OLD) - ARRAY['status','completed_at','failure_category','failure_code','failure_detail']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at','failure_category','failure_code','failure_detail']) THEN RAISE EXCEPTION 'experiment configuration is immutable'; END IF; IF OLD.status IN ('COMPLETED','FAILED') AND (to_jsonb(OLD) - ARRAY['status','completed_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at']) THEN RAISE EXCEPTION 'terminal experiment is immutable'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER experiments_immutable_config BEFORE UPDATE OR DELETE ON experiments FOR EACH ROW EXECUTE FUNCTION prevent_experiment_config_mutation()")


def downgrade() -> None:
    op.execute("DROP TRIGGER experiments_immutable_config ON experiments")
    op.execute("DROP FUNCTION prevent_experiment_config_mutation()")
    op.drop_constraint("failure_consistency", "experiments", type_="check")
    op.drop_constraint("sanitized_failure_detail", "experiments", type_="check")
    op.drop_constraint("sanitized_failure_code", "experiments", type_="check")
    op.drop_constraint("valid_failure_category", "experiments", type_="check")
    op.drop_column("experiments", "failure_detail")
    op.drop_column("experiments", "failure_code")
    op.drop_column("experiments", "failure_category")
    op.execute("""CREATE FUNCTION prevent_experiment_config_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'experiments are immutable'; END IF; IF (to_jsonb(OLD) - ARRAY['status','completed_at']) IS DISTINCT FROM (to_jsonb(NEW) - ARRAY['status','completed_at']) THEN RAISE EXCEPTION 'experiment configuration is immutable'; END IF; IF OLD.status IN ('COMPLETED','FAILED') AND (OLD.status, OLD.completed_at) IS DISTINCT FROM (NEW.status, NEW.completed_at) THEN RAISE EXCEPTION 'terminal experiment is immutable'; END IF; RETURN NEW; END; $$""")
    op.execute("CREATE TRIGGER experiments_immutable_config BEFORE UPDATE OR DELETE ON experiments FOR EACH ROW EXECUTE FUNCTION prevent_experiment_config_mutation()")
