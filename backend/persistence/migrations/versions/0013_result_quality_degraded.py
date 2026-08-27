"""Allow the V2 result quality taxonomy to distinguish degraded outcomes."""

# ruff: noqa: E501, I001

from alembic import op
from sqlalchemy.sql.elements import conv


revision = "0013_result_quality_degraded"
down_revision = "0012_required_historical_context"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(conv("ck_experiment_results_result_quality_values"), "experiment_results", type_="check")
    op.create_check_constraint(
        "result_quality_values",
        "experiment_results",
        "jsonb_typeof(result_quality) = 'object' AND result_quality->>'schema' = 'ATLAS_RESULT_QUALITY_V1' AND result_quality->>'value' IN ('DETERMINED','DEGRADED','DETERMINED_WITH_GAPS','CONSERVATIVE_AMBIGUITY_RESOLVED')",
    )


def downgrade() -> None:
    op.drop_constraint(conv("ck_experiment_results_result_quality_values"), "experiment_results", type_="check")
    op.create_check_constraint(
        "result_quality_values",
        "experiment_results",
        "jsonb_typeof(result_quality) = 'object' AND result_quality->>'schema' = 'ATLAS_RESULT_QUALITY_V1' AND result_quality->>'value' IN ('DETERMINED','DETERMINED_WITH_GAPS','CONSERVATIVE_AMBIGUITY_RESOLVED')",
    )
