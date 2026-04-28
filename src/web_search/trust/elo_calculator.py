class ELOCalculator:
    K_FACTOR_NEW = 32
    K_FACTOR_ESTABLISHED = 16

    @staticmethod
    def calculate_expected_score(rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))

    def calculate_new_score(
        self,
        old_score: float,
        opponent_score: float,
        actual_result: float,
        k_factor: int
    ) -> float:
        expected = self.calculate_expected_score(old_score, opponent_score)
        return old_score + k_factor * (actual_result - expected)

    def get_k_factor(self, total_facts: int) -> int:
        return self.K_FACTOR_NEW if total_facts < 50 else self.K_FACTOR_ESTABLISHED

    def calculate_verification_result(
        self,
        verification_result: str
    ) -> float:
        result_map = {
            "verified": 1.0,
            "confirmed": 1.0,
            "true": 1.0,
            "correct": 1.0,
            "falsified": 0.0,
            "disproved": 0.0,
            "false": 0.0,
            "wrong": 0.0,
            "neutral": 0.5,
            "unverified": 0.5,
            "unknown": 0.5,
        }
        return result_map.get(verification_result.lower(), 0.5)