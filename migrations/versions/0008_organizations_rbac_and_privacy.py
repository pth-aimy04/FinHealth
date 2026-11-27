"""Add multi-tenant organizations, RBAC, privacy erase support, and legacy backfill."""

import sqlalchemy as sa
from alembic import context, op

from finhealth.db import account_models as accounts
from finhealth.db.base import NAMING_CONVENTION, utc_now

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

ORG_MODELS = (
    accounts.Organization,
    accounts.OrganizationMember,
    accounts.OrganizationInvite,
    accounts.OrganizationAuditLog,
)


def _backfill_personal_organizations() -> None:
    """Create a default personal workspace for every existing user and link legacy rows."""
    bind = op.get_bind()
    now = utc_now()
    users = bind.execute(sa.text("SELECT id, display_name FROM users ORDER BY id")).fetchall()
    for user_id, display_name in users:
        existing_org_id = bind.execute(
            sa.text(
                "SELECT id FROM organizations "
                "WHERE created_by = :user_id AND is_personal = :is_personal "
                "ORDER BY id LIMIT 1"
            ),
            {"user_id": user_id, "is_personal": True},
        ).scalar()
        if existing_org_id is None:
            slug = f"personal-{user_id}"
            slug_taken = bind.execute(
                sa.text("SELECT id FROM organizations WHERE slug = :slug"),
                {"slug": slug},
            ).scalar()
            if slug_taken is not None:
                slug = f"personal-{user_id}-migrated"
            label = f"Không gian của {(display_name or '').strip() or f'Người dùng {user_id}'}"
            bind.execute(
                sa.text(
                    "INSERT INTO organizations "
                    "(name, slug, is_personal, active, created_by, created_at, updated_at) "
                    "VALUES (:name, :slug, :is_personal, :active, :created_by, :now, :now)"
                ),
                {
                    "name": label[:120],
                    "slug": slug,
                    "is_personal": True,
                    "active": True,
                    "created_by": user_id,
                    "now": now,
                },
            )
            org_id = bind.execute(
                sa.text("SELECT id FROM organizations WHERE slug = :slug"),
                {"slug": slug},
            ).scalar_one()
        else:
            org_id = existing_org_id

        member_exists = bind.execute(
            sa.text(
                "SELECT id FROM organization_members "
                "WHERE organization_id = :org_id AND user_id = :user_id"
            ),
            {"org_id": org_id, "user_id": user_id},
        ).scalar()
        if member_exists is None:
            bind.execute(
                sa.text(
                    "INSERT INTO organization_members "
                    "(organization_id, user_id, role, created_at) "
                    "VALUES (:org_id, :user_id, 'org_admin', :now)"
                ),
                {"org_id": org_id, "user_id": user_id, "now": now},
            )

        bind.execute(
            sa.text(
                "UPDATE user_sessions SET active_org_id = :org_id "
                "WHERE user_id = :user_id AND active_org_id IS NULL"
            ),
            {"org_id": org_id, "user_id": user_id},
        )
        for table_name in ("watchlist_items", "saved_screeners", "saved_analyses"):
            bind.execute(
                sa.text(
                    f"UPDATE {table_name} SET organization_id = :org_id "
                    "WHERE user_id = :user_id AND organization_id IS NULL"
                ),
                {"org_id": org_id, "user_id": user_id},
            )


def upgrade() -> None:
    """Create organization/RBAC tables, enable audit SET NULL on erase, and backfill users."""
    bind = op.get_bind()
    for model in ORG_MODELS:
        model.__table__.create(bind)

    op.add_column("users", sa.Column("job_title", sa.Unicode(120), nullable=True))

    with op.batch_alter_table("user_sessions", naming_convention=NAMING_CONVENTION) as batch:
        batch.add_column(sa.Column("active_org_id", sa.Integer(), nullable=True))
        batch.create_index("ix_user_sessions_active_org_id", ["active_org_id"], unique=False)
        batch.create_foreign_key(
            "fk_user_sessions_active_org_id_organizations",
            "organizations",
            ["active_org_id"],
            ["id"],
            ondelete="SET NULL",
        )

    for table_name in ("watchlist_items", "saved_screeners", "saved_analyses"):
        with op.batch_alter_table(table_name, naming_convention=NAMING_CONVENTION) as batch:
            batch.add_column(sa.Column("organization_id", sa.Integer(), nullable=True))
            batch.create_index(
                f"ix_{table_name}_organization_id", ["organization_id"], unique=False
            )
            batch.create_foreign_key(
                f"fk_{table_name}_organization_id_organizations",
                "organizations",
                ["organization_id"],
                ["id"],
                ondelete="CASCADE",
            )

    # Drop dependent index before alter_column to satisfy SQL Server Error 5074 rules.
    # Source: https://alembic.sqlalchemy.org/en/latest/batch.html
    with op.batch_alter_table("admin_audit_logs", naming_convention=NAMING_CONVENTION) as batch:
        batch.drop_constraint("fk_admin_audit_logs_actor_id_users", type_="foreignkey")
        batch.drop_index("ix_admin_audit_logs_actor_id")
        batch.alter_column("actor_id", existing_type=sa.Integer(), nullable=True)
        batch.create_index("ix_admin_audit_logs_actor_id", ["actor_id"], unique=False)
        batch.create_foreign_key(
            "fk_admin_audit_logs_actor_id_users",
            "users",
            ["actor_id"],
            ["id"],
            ondelete="SET NULL",
        )

    if not context.is_offline_mode():
        _backfill_personal_organizations()


def downgrade() -> None:
    """Reverse organization schema additions and restore strict admin_audit_logs.actor_id."""
    if not context.is_offline_mode():
        # Remove anonymized audit rows before re-applying NOT NULL on actor_id.
        op.execute(sa.text("DELETE FROM admin_audit_logs WHERE actor_id IS NULL"))
    with op.batch_alter_table("admin_audit_logs", naming_convention=NAMING_CONVENTION) as batch:
        batch.drop_constraint("fk_admin_audit_logs_actor_id_users", type_="foreignkey")
        batch.drop_index("ix_admin_audit_logs_actor_id")
        batch.alter_column("actor_id", existing_type=sa.Integer(), nullable=False)
        batch.create_index("ix_admin_audit_logs_actor_id", ["actor_id"], unique=False)
        batch.create_foreign_key(
            "fk_admin_audit_logs_actor_id_users",
            "users",
            ["actor_id"],
            ["id"],
        )

    for table_name in ("saved_analyses", "saved_screeners", "watchlist_items"):
        with op.batch_alter_table(table_name, naming_convention=NAMING_CONVENTION) as batch:
            batch.drop_constraint(
                f"fk_{table_name}_organization_id_organizations", type_="foreignkey"
            )
            batch.drop_index(f"ix_{table_name}_organization_id")
            batch.drop_column("organization_id")

    with op.batch_alter_table("user_sessions", naming_convention=NAMING_CONVENTION) as batch:
        batch.drop_constraint("fk_user_sessions_active_org_id_organizations", type_="foreignkey")
        batch.drop_index("ix_user_sessions_active_org_id")
        batch.drop_column("active_org_id")

    op.drop_column("users", "job_title")

    bind = op.get_bind()
    for model in reversed(ORG_MODELS):
        model.__table__.drop(bind)
