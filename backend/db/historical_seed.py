import logging
from sqlalchemy.orm import Session
from backend.db.models import HistoricalProject, HistoricalProjectLevel, HistoricalSteelComponent
from backend.db.historical_seed_data import HISTORICAL_PROJECTS, HISTORICAL_LEVELS, HISTORICAL_COMPONENTS

logger = logging.getLogger("buildora.historical_seed")

def seed_historical_data(db: Session) -> dict:
    """
    Idempotent historical steel dataset seeder.
    Populates HistoricalProject (22), HistoricalProjectLevel (24), and HistoricalSteelComponent (54) records.
    Independently verifies and seeds missing records for each table using key-based lookup.
    """
    p_count = db.query(HistoricalProject).count()
    l_count = db.query(HistoricalProjectLevel).count()
    c_count = db.query(HistoricalSteelComponent).count()

    if p_count == 22 and l_count == 24 and c_count == 54:
        logger.info(f"Historical dataset already fully seeded ({p_count} Projects, {l_count} Levels, {c_count} Components). Skipping.")
        return {
            "status": "already_seeded",
            "projects_count": p_count,
            "levels_count": l_count,
            "components_count": c_count
        }

    logger.info("Starting historical steel dataset seeding / verification...")

    # 1. Seed Historical Projects if missing
    if p_count == 0:
        for p_data in HISTORICAL_PROJECTS:
            proj = HistoricalProject(**p_data)
            db.add(proj)
        db.flush()

    # Build project_key -> id map
    project_key_to_id = {
        proj.project_key: proj.id for proj in db.query(HistoricalProject).all()
    }

    # 2. Seed Historical Project Levels if missing
    if l_count == 0:
        for l_data in HISTORICAL_LEVELS:
            data = dict(l_data)
            pkey = data.pop("project_key")
            proj_id = project_key_to_id.get(pkey)
            if not proj_id:
                raise ValueError(f"Foreign key resolution failed: project_key '{pkey}' not found.")
            data["project_id"] = proj_id
            level_obj = HistoricalProjectLevel(**data)
            db.add(level_obj)
        db.flush()

    # Build level_key -> id map
    level_key_to_id = {
        l_obj.level_key: l_obj.id for l_obj in db.query(HistoricalProjectLevel).all()
    }

    # 3. Seed Historical Steel Components if missing
    if c_count == 0:
        for c_data in HISTORICAL_COMPONENTS:
            data = dict(c_data)
            pkey = data.pop("project_key")
            lkey = data.pop("level_key")

            proj_id = project_key_to_id.get(pkey)
            if not proj_id:
                raise ValueError(f"Foreign key resolution failed: project_key '{pkey}' not found for component '{data.get('component_key')}'.")
            
            level_id = level_key_to_id.get(lkey) if lkey else None

            data["project_id"] = proj_id
            data["level_id"] = level_id

            comp_obj = HistoricalSteelComponent(**data)
            db.add(comp_obj)

    db.commit()

    p_count = db.query(HistoricalProject).count()
    l_count = db.query(HistoricalProjectLevel).count()
    c_count = db.query(HistoricalSteelComponent).count()

    logger.info(f"Historical steel dataset successfully verified/seeded: {p_count} Projects, {l_count} Levels, {c_count} Components.")

    # Validation checks
    assert p_count == 22, f"Expected 22 HistoricalProjects, got {p_count}"
    assert l_count == 24, f"Expected 24 HistoricalProjectLevels, got {l_count}"
    assert c_count == 54, f"Expected 54 HistoricalSteelComponents, got {c_count}"

    p022 = db.query(HistoricalProject).filter_by(project_key="P022").first()
    assert p022 is not None and p022.data_quality == "REFERENCE", "P022 REFERENCE validation failed."

    # Validate Foreign Keys
    for l in db.query(HistoricalProjectLevel).all():
        assert l.project_id is not None, f"Level {l.level_key} missing project_id"
    for c in db.query(HistoricalSteelComponent).all():
        assert c.project_id is not None, f"Component {c.component_key} missing project_id"

    # Only after successful validation: remove obsolete backup table if present
    from sqlalchemy import text
    try:
        db.execute(text("DROP TABLE IF EXISTS _old_historical_projects_backup"))
        db.commit()
    except Exception as ex:
        logger.warning(f"Note: Could not drop _old_historical_projects_backup table: {ex}")

    return {
        "status": "seeded",
        "projects_count": p_count,
        "levels_count": l_count,
        "components_count": c_count
    }
