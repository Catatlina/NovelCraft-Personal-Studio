"""
Ten-Layer Book Analysis Model (十层分析模型)

Analyzes scanned books from ranking/import across 10 depth layers.
Each layer calls gateway.complete() for real AI analysis — no mock/fallback.
"""

from __future__ import annotations

import json
from typing import Any

from app.gateway import BudgetExceeded, ProviderError, complete


class TenLayerAnalyzer:
    """Deep book analysis across 10 layers, producing structured JSON per layer."""

    def __init__(self, project_id: str):
        self.project_id = project_id

    # ── Layer 1: BookProfile ───────────────────────────────────────
    def analyze_book_profile(self, book_profiles: list[dict]) -> dict:
        """Extract metadata: title, author, platform, category, tags, word_count, status, rating, etc."""
        return self._call(
            task_type="analysis_book_profile",
            prompt_name="analysis.book_profile",
            variables={"book_profiles": json.dumps(book_profiles, ensure_ascii=False)},
            layer="01_BookProfile",
        )

    # ── Layer 2: GenreReport ────────────────────────────────────────
    def analyze_genre_report(self, book_profiles: list[dict]) -> dict:
        """First/second/third-level genre classification, TOP100 tags, co-occurrence, trends."""
        return self._call(
            task_type="analysis_genre_report",
            prompt_name="analysis.genre_report",
            variables={"book_profiles": json.dumps(book_profiles, ensure_ascii=False)},
            layer="02_GenreReport",
        )

    # ── Layer 3: SellingPoints ──────────────────────────────────────
    def analyze_selling_points(self, book_profiles: list[dict]) -> dict:
        """Why each book succeeds — opening hooks, system arrival, divorce, future memory, lottery, etc."""
        return self._call(
            task_type="analysis_selling_points",
            prompt_name="analysis.selling_points",
            variables={"book_profiles": json.dumps(book_profiles, ensure_ascii=False)},
            layer="03_SellingPoints",
        )

    # ── Layer 4: Golden3Chapter ─────────────────────────────────────
    def analyze_golden_3_chapter(self, book_profiles: list[dict]) -> dict:
        """First 3 chapters — first sentence, paragraph, 3000 chars, first conflict/climax/reversal/hook."""
        return self._call(
            task_type="analysis_golden_3",
            prompt_name="analysis.golden_3_chapter",
            variables={"book_profiles": json.dumps(book_profiles, ensure_ascii=False)},
            layer="04_Golden3Chapter",
        )

    # ── Layer 5: PlotRhythm ─────────────────────────────────────────
    def analyze_plot_rhythm(self, book_profiles: list[dict]) -> dict:
        """Per-chapter events, conflicts, reversals, climaxes, suspense, character appearances."""
        return self._call(
            task_type="analysis_plot_rhythm",
            prompt_name="analysis.plot_rhythm",
            variables={"book_profiles": json.dumps(book_profiles, ensure_ascii=False)},
            layer="05_PlotRhythm",
        )

    # ── Layer 6: Character ──────────────────────────────────────────
    def analyze_characters(self, book_profiles: list[dict]) -> dict:
        """Protagonist age/identity/personality/growth/abilities/values/goals + supporting cast + antagonists."""
        return self._call(
            task_type="analysis_characters",
            prompt_name="analysis.characters",
            variables={"book_profiles": json.dumps(book_profiles, ensure_ascii=False)},
            layer="06_Character",
        )

    # ── Layer 7: WorldBuilding ──────────────────────────────────────
    def analyze_world_building(self, book_profiles: list[dict]) -> dict:
        """World setting, timeline, power system, currency, tech, organizations, factions, rules."""
        return self._call(
            task_type="analysis_world_building",
            prompt_name="analysis.world_building",
            variables={"book_profiles": json.dumps(book_profiles, ensure_ascii=False)},
            layer="07_WorldBuilding",
        )

    # ── Layer 8: StyleReport ────────────────────────────────────────
    def analyze_style_report(self, book_profiles: list[dict]) -> dict:
        """Avg sentence/paragraph length, dialogue/description/psychology/action ratios,
        noun/adjective density, idiom ratio, internet slang ratio, AI-score."""
        return self._call(
            task_type="analysis_style_report",
            prompt_name="analysis.style_report",
            variables={"book_profiles": json.dumps(book_profiles, ensure_ascii=False)},
            layer="08_StyleReport",
        )

    # ── Layer 9: ReaderReport ───────────────────────────────────────
    def analyze_reader_report(self, book_profiles: list[dict]) -> dict:
        """Comments, reviews, chapter feedback — most liked/urgent/dropped/toxic/tear-jerking/fun/satisfying moments."""
        return self._call(
            task_type="analysis_reader_report",
            prompt_name="analysis.reader_report",
            variables={"book_profiles": json.dumps(book_profiles, ensure_ascii=False)},
            layer="09_ReaderReport",
        )

    # ── Layer 10: AIInsight ─────────────────────────────────────────
    def analyze_ai_insight(self, book_profiles: list[dict]) -> dict:
        """Market trends (30-day), viral formulas, innovation suggestions,
        AI generation recommendations (title/tags/synopsis/selling points/golden chapters/
        worldbuilding/characters/pacing/word count/update frequency/platforms)."""
        return self._call(
            task_type="analysis_ai_insight",
            prompt_name="analysis.ai_insight",
            variables={"book_profiles": json.dumps(book_profiles, ensure_ascii=False)},
            layer="10_AIInsight",
        )

    # ── Helpers ─────────────────────────────────────────────────────
    def _call(
        self,
        task_type: str,
        prompt_name: str,
        variables: dict[str, Any],
        layer: str,
    ) -> dict:
        """Call gateway.complete() with error propagation — no mock/fallback.

        Returns structured result or raises HTTP-suitable exception.
        """
        try:
            output = complete(
                run_id=None,
                node_key=None,
                project_id=self.project_id,
                task_type=task_type,
                prompt_name=prompt_name,
                variables=variables,
                client_mutation_id=f"ten-layer:{self.project_id}:{layer}:v1",
            )
            return {"layer": layer, "status": "succeeded", "data": output}
        except (ProviderError, BudgetExceeded) as exc:
            return {"layer": layer, "status": "failed", "error": str(exc), "error_type": type(exc).__name__}

    # ── Full batch analysis ─────────────────────────────────────────
    def analyze(
        self,
        book_profiles: list[dict],
        platforms: list[str] | None = None,
        analysis_mode: str = "all",
    ) -> dict:
        """Run all 10 layers sequentially and collect results.

        Args:
            book_profiles: list of book metadata dicts from scanned ranking
            platforms: source platforms (e.g. ["fanqie", "qidian"])
            analysis_mode: "single" | "multi" | "all"

        Returns:
            dict with ScanResult containing per-layer results + HeatMap + KeywordCloud + TrendReport
        """
        if not book_profiles:
            return {"status": "error", "message": "book_profiles is empty", "layers": {}}

        layers_map = {
            "01_BookProfile": self.analyze_book_profile,
            "02_GenreReport": self.analyze_genre_report,
            "03_SellingPoints": self.analyze_selling_points,
            "04_Golden3Chapter": self.analyze_golden_3_chapter,
            "05_PlotRhythm": self.analyze_plot_rhythm,
            "06_Character": self.analyze_characters,
            "07_WorldBuilding": self.analyze_world_building,
            "08_StyleReport": self.analyze_style_report,
            "09_ReaderReport": self.analyze_reader_report,
            "10_AIInsight": self.analyze_ai_insight,
        }

        if analysis_mode == "single":
            # Only run the most valuable layers
            selected = ["01_BookProfile", "03_SellingPoints", "06_Character", "10_AIInsight"]
            layers_to_run = {k: v for k, v in layers_map.items() if k in selected}
        elif analysis_mode == "multi":
            selected = ["01_BookProfile", "02_GenreReport", "03_SellingPoints",
                        "04_Golden3Chapter", "06_Character", "08_StyleReport", "10_AIInsight"]
            layers_to_run = {k: v for k, v in layers_map.items() if k in selected}
        else:  # "all"
            layers_to_run = layers_map

        results: dict[str, dict] = {}
        errors: list[dict] = []

        for layer_name, method in layers_to_run.items():
            result = method(book_profiles)
            results[layer_name] = result
            if result.get("status") == "failed":
                errors.append({"layer": layer_name, "error": result.get("error"), "error_type": result.get("error_type")})

        # Generate synthetic metadata reports
        heat_map = self._generate_heat_map(results, book_profiles)
        keyword_cloud = self._generate_keyword_cloud(results)
        trend_report = self._generate_trend_report(results, platforms or [])

        all_layers_count = len(layers_to_run)
        succeeded_count = sum(1 for r in results.values() if r.get("status") == "succeeded")

        return {
            "status": "completed" if not errors else "partial",
            "total_layers": all_layers_count,
            "succeeded_layers": succeeded_count,
            "failed_layers": len(errors),
            "platforms": platforms or [],
            "analysis_mode": analysis_mode,
            "ScanResult": results,
            "HeatMap": heat_map,
            "KeywordCloud": keyword_cloud,
            "TrendReport": trend_report,
            "errors": errors,
        }

    def _generate_heat_map(self, results: dict, book_profiles: list[dict]) -> dict:
        """Generate a heat map from genre + scores data."""
        genres: dict[str, int] = {}
        scores: list[float] = []
        for profile in book_profiles:
            category = str(profile.get("category", "general"))
            genres[category] = genres.get(category, 0) + 1
            score = profile.get("metrics", {}).get("confidence", 0)
            if isinstance(score, (int, float)):
                scores.append(float(score))
        return {
            "genre_distribution": genres,
            "avg_confidence": round(sum(scores) / len(scores), 2) if scores else 0,
            "total_books": len(book_profiles),
        }

    def _generate_keyword_cloud(self, results: dict) -> dict:
        """Extract keyword frequency from analysis results."""
        profile_data = results.get("01_BookProfile", {}).get("data", {})
        genre_data = results.get("02_GenreReport", {}).get("data", {})
        return {
            "top_tags": genre_data.get("top_tags", [])[:20] if isinstance(genre_data, dict) else [],
            "categories": profile_data.get("categories", []) if isinstance(profile_data, dict) else [],
        }

    def _generate_trend_report(self, results: dict, platforms: list[str]) -> dict:
        """Generate a trend report synthesizing AIInsight."""
        insight = results.get("10_AIInsight", {}).get("data", {})
        return {
            "platforms": platforms,
            "market_trends": insight.get("market_trends", []) if isinstance(insight, dict) else [],
            "viral_formulas": insight.get("viral_formulas", []) if isinstance(insight, dict) else [],
            "recommendations": insight.get("recommendations", {}) if isinstance(insight, dict) else {},
            "generated_at": None,  # filled by caller
        }
