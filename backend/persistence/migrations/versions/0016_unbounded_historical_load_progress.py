"""Remove the obsolete request-window ceiling from durable load progress."""
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op

revision = "0016_load_progress"
down_revision = "0015_native_resolutions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Progress remains JSON for this narrow command, but its size is governed
    # by actual bounded windows, not an arbitrary research-range count.
    op.drop_constraint(
        sa.sql.naming.conv("ck_historical_data_load_requests_load_maximum"),
        "historical_data_load_requests",
        type_="check",
    )
    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION atlas_historical_ranges_valid(value jsonb)
        RETURNS boolean LANGUAGE plpgsql IMMUTABLE AS $function$
        DECLARE item jsonb; current_start timestamptz; current_end timestamptz;
                previous_end timestamptz := NULL;
        BEGIN
            IF jsonb_typeof(value) <> 'array' THEN RETURN false; END IF;
            FOR item IN SELECT jsonb_array_elements(value) LOOP
                IF jsonb_typeof(item) <> 'object' OR NOT (item ? 'start')
                   OR NOT (item ? 'end') OR (item - 'start' - 'end') <> '{}'::jsonb
                   OR (item->>'start') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]{1,6})?Z$'
                   OR (item->>'end') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]{1,6})?Z$' THEN RETURN false; END IF;
                current_start := item->>'start'; current_end := item->>'end';
                IF current_end <= current_start OR (previous_end IS NOT NULL AND current_start < previous_end) THEN RETURN false; END IF;
                previous_end := current_end;
            END LOOP;
            RETURN true;
        EXCEPTION WHEN others THEN RETURN false;
        END; $function$;
    """))


def downgrade() -> None:
    # The previous function's 40-item limit is intentionally not restored:
    # downgrades must not make already durable large plans invalid.
    pass
