import pytest
from web_search.trust.trust_rank_ladder import TrustRankLadder, TrustLevel
from web_search.trust.source_registry import DEFAULT_INITIAL_SCORE


class TestELOScoreWin:
    def setup_method(self):
        self.ladder = TrustRankLadder()

    def test_elo_score_win(self):
        source_domain = "test-source.example.com"
        self.ladder.register_new_source("Test Source", source_domain, initial_score=1000.0)
        initial_score = self.ladder.get_trust_score(source_domain)
        self.ladder.update_score(source_domain, "verified")
        new_score = self.ladder.get_trust_score(source_domain)
        assert new_score > initial_score


class TestELOScoreLoss:
    def setup_method(self):
        self.ladder = TrustRankLadder()

    def test_elo_score_loss(self):
        source_domain = "test-source.example.com"
        self.ladder.register_new_source("Test Source", source_domain, initial_score=1000.0)
        initial_score = self.ladder.get_trust_score(source_domain)
        self.ladder.update_score(source_domain, "falsified")
        new_score = self.ladder.get_trust_score(source_domain)
        assert new_score < initial_score


class TestELOScoreDraw:
    def setup_method(self):
        self.ladder = TrustRankLadder()

    def test_elo_score_draw(self):
        source_domain = "test-source.example.com"
        self.ladder.register_new_source("Test Source", source_domain, initial_score=1000.0)
        initial_score = self.ladder.get_trust_score(source_domain)
        self.ladder.update_score(source_domain, "neutral", opponent_score=1000.0)
        new_score = self.ladder.get_trust_score(source_domain)
        assert new_score == initial_score


class TestNewSourceDefaultScore:
    def setup_method(self):
        self.ladder = TrustRankLadder()

    def test_new_source_default_score(self):
        source_domain = "new-source.example.com"
        score = self.ladder.register_new_source("New Source", source_domain)
        assert score.trust_score == DEFAULT_INITIAL_SCORE
        assert DEFAULT_INITIAL_SCORE == 1000.0


class TestTrustLevelSTier:
    def setup_method(self):
        self.ladder = TrustRankLadder()

    def test_trust_level_s_tier(self):
        source_domain = "s-tier.example.com"
        self.ladder.register_new_source("S Tier Source", source_domain, initial_score=1800.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.S

    def test_trust_level_s_tier_boundary(self):
        source_domain = "s-tier-boundary.example.com"
        self.ladder.register_new_source("S Tier Boundary", source_domain, initial_score=1800.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.S


class TestTrustLevelATier:
    def setup_method(self):
        self.ladder = TrustRankLadder()

    def test_trust_level_a_tier(self):
        source_domain = "a-tier.example.com"
        self.ladder.register_new_source("A Tier Source", source_domain, initial_score=1600.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.A

    def test_trust_level_a_tier_lower_boundary(self):
        source_domain = "a-tier-lower.example.com"
        self.ladder.register_new_source("A Tier Lower", source_domain, initial_score=1500.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.A

    def test_trust_level_a_tier_upper_boundary(self):
        source_domain = "a-tier-upper.example.com"
        self.ladder.register_new_source("A Tier Upper", source_domain, initial_score=1799.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.A


class TestTrustLevelBTier:
    def setup_method(self):
        self.ladder = TrustRankLadder()

    def test_trust_level_b_tier(self):
        source_domain = "b-tier.example.com"
        self.ladder.register_new_source("B Tier Source", source_domain, initial_score=1300.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.B

    def test_trust_level_b_tier_lower_boundary(self):
        source_domain = "b-tier-lower.example.com"
        self.ladder.register_new_source("B Tier Lower", source_domain, initial_score=1200.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.B

    def test_trust_level_b_tier_upper_boundary(self):
        source_domain = "b-tier-upper.example.com"
        self.ladder.register_new_source("B Tier Upper", source_domain, initial_score=1499.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.B


class TestTrustLevelCTier:
    def setup_method(self):
        self.ladder = TrustRankLadder()

    def test_trust_level_c_tier(self):
        source_domain = "c-tier.example.com"
        self.ladder.register_new_source("C Tier Source", source_domain, initial_score=1100.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.C

    def test_trust_level_c_tier_lower_boundary(self):
        source_domain = "c-tier-lower.example.com"
        self.ladder.register_new_source("C Tier Lower", source_domain, initial_score=1000.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.C

    def test_trust_level_c_tier_upper_boundary(self):
        source_domain = "c-tier-upper.example.com"
        self.ladder.register_new_source("C Tier Upper", source_domain, initial_score=1199.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.C


class TestTrustLevelDTier:
    def setup_method(self):
        self.ladder = TrustRankLadder()

    def test_trust_level_d_tier(self):
        source_domain = "d-tier.example.com"
        self.ladder.register_new_source("D Tier Source", source_domain, initial_score=900.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.D

    def test_trust_level_d_tier_lower_boundary(self):
        source_domain = "d-tier-lower.example.com"
        self.ladder.register_new_source("D Tier Lower", source_domain, initial_score=800.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.D

    def test_trust_level_d_tier_upper_boundary(self):
        source_domain = "d-tier-upper.example.com"
        self.ladder.register_new_source("D Tier Upper", source_domain, initial_score=999.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.D


class TestTrustLevelETier:
    def setup_method(self):
        self.ladder = TrustRankLadder()

    def test_trust_level_e_tier(self):
        source_domain = "e-tier.example.com"
        self.ladder.register_new_source("E Tier Source", source_domain, initial_score=700.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.E

    def test_trust_level_e_tier_upper_boundary(self):
        source_domain = "e-tier-upper.example.com"
        self.ladder.register_new_source("E Tier Upper", source_domain, initial_score=799.0)
        trust_level = self.ladder.get_trust_level(source_domain)
        assert trust_level == TrustLevel.E


if __name__ == "__main__":
    pytest.main([__file__, "-v"])