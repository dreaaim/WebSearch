import pytest
from web_search.resolver.priority_engine import PriorityEngine, PriorityLevel
from web_search.core.models import SearchResult, Classification, SourceType, SourceLevel, Claim
from datetime import datetime

def create_result(classification, source_type, source_level, followers=0):
    return SearchResult(
        title="Test",
        url=f"https://test.com/{classification}/{source_type}",
        snippet="Test snippet",
        source_name="Test",
        source_domain="test.com",
        source_type=source_type,
        source_level=source_level,
        classification=classification,
        粉丝数=followers
    )

def create_claim(result, statement):
    return Claim(
        result=result,
        statement=statement,
        key_facts=[],
        timestamp=datetime.now()
    )

def test_priority_black_individual():
    engine = PriorityEngine()
    result = create_result(Classification.BLACK, SourceType.INDIVIDUAL, SourceLevel.LOCAL)
    priority, desc = engine.calculate_priority(result)
    assert priority == PriorityLevel.BLACK_INDIVIDUAL

def test_priority_white_national():
    engine = PriorityEngine()
    result = create_result(Classification.WHITE, SourceType.OFFICIAL, SourceLevel.NATIONAL)
    priority, desc = engine.calculate_priority(result)
    assert priority == PriorityLevel.WHITE_NATIONAL_OFFICIAL

def test_priority_gray_kol_big():
    engine = PriorityEngine()
    result = create_result(Classification.GRAY, SourceType.KOL, SourceLevel.NATIONAL, followers=2000000)
    priority, desc = engine.calculate_priority(result)
    assert priority == PriorityLevel.GRAY_KOL_BIG

def test_priority_gray_kol_medium():
    engine = PriorityEngine()
    result = create_result(Classification.GRAY, SourceType.KOL, SourceLevel.NATIONAL, followers=500000)
    priority, desc = engine.calculate_priority(result)
    assert priority == PriorityLevel.GRAY_KOL_MEDIUM

def test_priority_gray_kol_small():
    engine = PriorityEngine()
    result = create_result(Classification.GRAY, SourceType.KOL, SourceLevel.NATIONAL, followers=50000)
    priority, desc = engine.calculate_priority(result)
    assert priority == PriorityLevel.GRAY_KOL_SMALL

def test_resolve_collision_single():
    engine = PriorityEngine()
    result = create_result(Classification.GRAY, SourceType.MEDIA, SourceLevel.NATIONAL)
    claim = create_claim(result, "Test statement")
    collision = engine.resolve_collision([claim])
    assert collision.resolved_claim == claim
    assert collision.consensus_degree == 1.0

def test_resolve_collision_multiple():
    engine = PriorityEngine()
    white_result = create_result(Classification.WHITE, SourceType.OFFICIAL, SourceLevel.NATIONAL)
    gray_result = create_result(Classification.GRAY, SourceType.MEDIA, SourceLevel.MUNICIPAL)
    claims = [
        create_claim(white_result, "White statement"),
        create_claim(gray_result, "Gray statement")
    ]
    collision = engine.resolve_collision(claims)
    assert collision.resolved_claim.result == white_result
    assert collision.consensus_degree == 0.5