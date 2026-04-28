from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Dict

DEFAULT_INITIAL_SCORE = 1000.0


class SourceRegistry:
    def __init__(
        self,
        storage_path: Optional[str] = None,
        use_sqlite: bool = False
    ):
        self.storage_path = storage_path
        self.use_sqlite = use_sqlite
        self._scores: Dict[str, "TrustRankScore"] = {}

        if self.use_sqlite and self.storage_path:
            self._init_sqlite()
        elif self.storage_path:
            self._load_from_json()

    def _init_sqlite(self):
        if not self.storage_path:
            return
        Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.storage_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_registry (
                source_domain TEXT PRIMARY KEY,
                source_name TEXT NOT NULL,
                trust_score REAL NOT NULL,
                total_facts INTEGER DEFAULT 0,
                verified_facts INTEGER DEFAULT 0,
                falsified_facts INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()

    def _load_from_json(self):
        if not self.storage_path:
            return
        path = Path(self.storage_path)
        if path.exists():
            from .trust_rank_ladder import TrustRankScore
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for domain, score_data in data.items():
                    self._scores[domain] = TrustRankScore(**score_data)

    def _save_to_json(self):
        if not self.storage_path:
            return
        path = Path(self.storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {domain: asdict(score) for domain, score in self._scores.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _save_to_sqlite(self, score: "TrustRankScore"):
        if not self.use_sqlite or not self.storage_path:
            return
        from .trust_rank_ladder import TrustRankScore
        conn = sqlite3.connect(self.storage_path)
        conn.execute("""
            INSERT OR REPLACE INTO source_registry
            (source_domain, source_name, trust_score, total_facts, verified_facts, falsified_facts)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            score.source_domain,
            score.source_name,
            score.trust_score,
            score.total_facts,
            score.verified_facts,
            score.falsified_facts
        ))
        conn.commit()
        conn.close()

    def _load_from_sqlite(self):
        if not self.use_sqlite or not self.storage_path:
            return
        path = Path(self.storage_path)
        if not path.exists():
            return
        from .trust_rank_ladder import TrustRankScore
        conn = sqlite3.connect(self.storage_path)
        cursor = conn.execute("SELECT * FROM source_registry")
        for row in cursor:
            score = TrustRankScore(
                source_name=row[1],
                source_domain=row[0],
                trust_score=row[2],
                total_facts=row[3],
                verified_facts=row[4],
                falsified_facts=row[5]
            )
            self._scores[row[0]] = score
        conn.close()

    def register(
        self,
        source_name: str,
        source_domain: str,
        initial_score: float = DEFAULT_INITIAL_SCORE
    ) -> "TrustRankScore":
        if source_domain in self._scores:
            return self._scores[source_domain]
        from .trust_rank_ladder import TrustRankScore
        score = TrustRankScore(
            source_name=source_name,
            source_domain=source_domain,
            trust_score=initial_score,
            total_facts=0,
            verified_facts=0,
            falsified_facts=0
        )
        self._scores[source_domain] = score

        if self.use_sqlite:
            self._save_to_sqlite(score)
        elif self.storage_path:
            self._save_to_json()

        return score

    def get_score(self, source_domain: str) -> Optional["TrustRankScore"]:
        if source_domain in self._scores:
            return self._scores[source_domain]

        if self.use_sqlite:
            self._load_from_sqlite()
            return self._scores.get(source_domain)

        if self.storage_path and Path(self.storage_path).exists():
            self._load_from_json()
            return self._scores.get(source_domain)

        return None

    def update_score(self, score: "TrustRankScore") -> None:
        self._scores[score.source_domain] = score

        if self.use_sqlite:
            self._save_to_sqlite(score)
        elif self.storage_path:
            self._save_to_json()

    def get_all_scores(self) -> Dict[str, "TrustRankScore"]:
        return self._scores.copy()

    def initialize(self) -> None:
        if self.use_sqlite:
            self._load_from_sqlite()
        elif self.storage_path:
            self._load_from_json()