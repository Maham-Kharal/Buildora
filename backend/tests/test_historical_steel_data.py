import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base
from backend.db.models import HistoricalProject, HistoricalProjectLevel, HistoricalSteelComponent
from backend.db.historical_seed import seed_historical_data
from backend.shared.ai.tools import query_historical_projects_db
from backend.modules.admin.steel_estimator.service import calculate_steel_estimation
from backend.modules.admin.steel_estimator.schemas import SteelEstimateRequestSchema


@pytest.fixture(scope="module")
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed historical data
    seed_historical_data(session)

    yield session

    session.close()


def test_historical_counts(test_db):
    p_count = test_db.query(HistoricalProject).count()
    l_count = test_db.query(HistoricalProjectLevel).count()
    c_count = test_db.query(HistoricalSteelComponent).count()

    assert p_count == 22, f"Expected 22 HistoricalProjects, got {p_count}"
    assert l_count == 24, f"Expected 24 HistoricalProjectLevels, got {l_count}"
    assert c_count == 54, f"Expected 54 HistoricalSteelComponents, got {c_count}"


def test_p022_reference_tag(test_db):
    p022 = test_db.query(HistoricalProject).filter_by(project_key="P022").first()
    assert p022 is not None, "Project P022 must exist."
    assert p022.data_quality == "REFERENCE", f"P022 data_quality must be 'REFERENCE', got '{p022.data_quality}'"

    # Default query excluding REFERENCE should return 21 projects
    source_backed = test_db.query(HistoricalProject).filter(HistoricalProject.data_quality != "REFERENCE").all()
    assert len(source_backed) == 21, f"Expected 21 source-backed projects, got {len(source_backed)}"


def test_foreign_keys_integrity(test_db):
    levels = test_db.query(HistoricalProjectLevel).all()
    for l in levels:
        assert l.project_id is not None
        proj = test_db.query(HistoricalProject).filter_by(id=l.project_id).first()
        assert proj is not None, f"Level {l.level_key} points to non-existent project_id {l.project_id}"

    components = test_db.query(HistoricalSteelComponent).all()
    for c in components:
        assert c.project_id is not None
        proj = test_db.query(HistoricalProject).filter_by(id=c.project_id).first()
        assert proj is not None, f"Component {c.component_key} points to non-existent project_id {c.project_id}"

        if c.level_id is not None:
            level = test_db.query(HistoricalProjectLevel).filter_by(id=c.level_id).first()
            assert level is not None, f"Component {c.component_key} points to non-existent level_id {c.level_id}"


def test_seeding_idempotency(test_db):
    res = seed_historical_data(test_db)
    assert res.get("status") == "already_seeded"
    assert test_db.query(HistoricalProject).count() == 22
    assert test_db.query(HistoricalProjectLevel).count() == 24
    assert test_db.query(HistoricalSteelComponent).count() == 54


def test_query_historical_projects_db_tool(test_db):
    result = query_historical_projects_db(test_db, sqft_filter=45000.0)
    assert result["matching_count"] > 0
    projects = result["projects"]
    for p in projects:
        assert p["data_quality"] != "REFERENCE", "REFERENCE project P022 must not appear in standard query results."
        assert p["cost_usd"] is None, "Historical cost_usd must be None."


def test_service_estimation_similarity(test_db):
    req = SteelEstimateRequestSchema(
        project_name="Test Project",
        project_type="Commercial",
        total_sqft=45000.0
    )
    res = calculate_steel_estimation(test_db, req)
    assert len(res.similar_historical_projects) > 0
    for sim_p in res.similar_historical_projects:
        assert sim_p.cost_usd is None
        assert sim_p.name != "P022 REFERENCE"
