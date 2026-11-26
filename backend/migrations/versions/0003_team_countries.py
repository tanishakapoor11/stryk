"""Attach national teams to their country.

0002 created the ``country`` table and ``team.country_id`` but nothing ever
filled them: every team sat with a null country, so the interface had no flag
and no abbreviation to show for anything outside the IPL. The country
catalogue has since grown from the 15 full members to every national side in
the data, and this links them by name.

No schema change — it re-seeds the catalogue and runs the same linking pass
the importer now runs, so a migrated database and a freshly ingested one are
identical.

Revision ID: 0003
Revises: 0002
"""

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from alembic import op
    from sqlalchemy.orm import Session

    from app import catalog
    from app.ingestion.linking import link_countries

    with Session(bind=op.get_bind()) as db:
        catalog.seed(db)
        linked = link_countries(db)
        db.commit()
    print(f"  linked {linked} national team(s) to a country")


def downgrade() -> None:
    from alembic import op
    from sqlalchemy import text

    op.get_bind().execute(text("UPDATE team SET country_id = NULL"))
