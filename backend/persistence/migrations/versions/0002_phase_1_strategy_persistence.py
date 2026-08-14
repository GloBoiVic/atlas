"""Phase 1 Strategy and immutable StrategyVersion persistence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_phase_1_strategy"
down_revision = "0001_phase_0_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategies",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("strategy_key", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_strategies"),
        sa.UniqueConstraint("strategy_key", name="uq_strategies_strategy_key"),
    )
    op.create_table(
        "strategy_versions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("strategy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("source_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("implementation_key", sa.String(length=200), nullable=False),
        sa.Column(
            "parameter_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "context_timeframes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "source_manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "exact_source_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("primary_timeframe", sa.String(length=20), nullable=False),
        sa.Column("warm_up_bars", sa.Integer(), nullable=False),
        sa.Column("state_schema_version", sa.Integer(), nullable=False),
        sa.Column("git_sha", sa.String(length=40), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("version_number > 0", name="positive_version_number"),
        sa.CheckConstraint(
            "source_fingerprint ~ '^[0-9a-f]{64}$'",
            name="sha256_fingerprint",
        ),
        sa.ForeignKeyConstraint(
            ["strategy_id"],
            ["strategies.id"],
            name="fk_strategy_versions_strategy_id_strategies",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_strategy_versions"),
        sa.UniqueConstraint(
            "strategy_id", "version_number", name="uq_strategy_versions_strategy_id"
        ),
        sa.UniqueConstraint(
            "strategy_id",
            "source_fingerprint",
            name="uq_strategy_versions_strategy_id_source_fingerprint",
        ),
    )
    op.execute("""
        CREATE FUNCTION prevent_strategy_version_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'strategy_versions are immutable';
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER strategy_versions_append_only
        BEFORE UPDATE OR DELETE ON strategy_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_strategy_version_mutation()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER strategy_versions_append_only ON strategy_versions")
    op.execute("DROP FUNCTION prevent_strategy_version_mutation()")
    op.drop_table("strategy_versions")
    op.drop_table("strategies")
