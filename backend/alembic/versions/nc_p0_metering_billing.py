"""P0 remediation: per-user AI metering + plan-derived cost budget.

- Adds ``ai_calls.user_id`` so every AI call is attributed to the user who
  triggered it (enables the per-user token bill and the plan-derived monthly
  cost budget in ``app.core.billing``).
- Adds ``plans.monthly_budget_cny`` (CNY) so each plan carries a finite monthly
  AI-cost ceiling instead of the previously hardcoded 2.0/50.0 literals.
"""
from alembic import op


revision = "nc_p0_metering_billing"
down_revision = "nc_versions_reason_text"


def upgrade():
    # 1) Attribute AI calls to the requesting user.
    op.execute("ALTER TABLE ai_calls ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_calls_user_created "
        "ON ai_calls(user_id, created_at)"
    )

    # 2) Per-plan monthly AI-cost ceiling (finite; Free aligns with dev seed 50.0).
    op.execute(
        "ALTER TABLE plans ADD COLUMN IF NOT EXISTS monthly_budget_cny DECIMAL(10, 2) "
        "NOT NULL DEFAULT 50.0"
    )
    op.execute("UPDATE plans SET monthly_budget_cny = 50.0 WHERE id = 'plan_free'")
    op.execute("UPDATE plans SET monthly_budget_cny = 500.0 WHERE id = 'plan_pro'")
    op.execute("UPDATE plans SET monthly_budget_cny = 5000.0 WHERE id = 'plan_enterprise'")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_ai_calls_user_created")
    op.execute("ALTER TABLE ai_calls DROP COLUMN IF EXISTS user_id")
    op.execute("ALTER TABLE plans DROP COLUMN IF EXISTS monthly_budget_cny")
