import tempfile
import unittest
from pathlib import Path

from models.watch_kinematic.watch_kinematic.chain_solver_loop import run_chain_solver_loop_probe


class WatchChainSolverLoopTests(unittest.TestCase):
    def test_loop_probe_reports_bridge_area_and_service_island_diversity(self):
        report = run_chain_solver_loop_probe(seeds=[1, 2, 4, 5, 6], output_dir=None)

        self.assertEqual([1, 2, 4, 5, 6], report["seeds"])
        self.assertIn("diversity_metrics", report)
        self.assertIn("bridge_area_by_candidate", report["diversity_metrics"])
        self.assertIn("outer_service_island_span_by_candidate", report["diversity_metrics"])
        self.assertIn(report["diversity_status"], {"pass", "fail"})

    def test_loop_probe_generates_five_planar_candidate_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_chain_solver_loop_probe(seeds=[1, 2, 4, 5, 6], output_dir=Path(tmp))

            self.assertEqual(5, len(report["candidates"]))
            self.assertIn("contact_sheet", report["artifacts"])
            self.assertTrue(Path(report["artifacts"]["contact_sheet"]).exists())
            for candidate in report["candidates"]:
                with self.subTest(seed=candidate["seed"]):
                    self.assertIn("pattern_solver_variables", candidate)
                    self.assertIn("bridge_partition_candidate", candidate)
                    self.assertIn(
                        candidate["bridge_partition_candidate"],
                        {
                            "continuous_outer_arc_y",
                            "service_island_power_partition",
                            "centroid_voronoi_partition",
                            "barrel_local_island_partition",
                            "escapement_local_island_partition",
                        },
                    )
                    self.assertEqual("pass", candidate["geometric_status"])
                    self.assertTrue(Path(candidate["image_path"]).exists())

    def test_loop_probe_scores_quantitative_diversity(self):
        report = run_chain_solver_loop_probe(seeds=[1, 2, 4, 5, 6], output_dir=None)

        metrics = report["diversity_metrics"]
        self.assertIn("bridge_area_coefficient_of_variation", metrics)
        self.assertIn("outer_service_island_span_coefficient_of_variation", metrics)
        self.assertIn("key_axis_angle_spread_deg", metrics)
        self.assertIn("failure_reasons", report)
        self.assertIn(report["diversity_status"], {"pass", "fail"})
        for bridge_id in ["barrel_bridge", "train_bridge", "escapement_bridge"]:
            with self.subTest(bridge=bridge_id):
                self.assertIn(bridge_id, metrics["bridge_area_coefficient_of_variation"])
                self.assertIn(bridge_id, metrics["outer_service_island_span_coefficient_of_variation"])
        for axis_key in [
            "barrel_angle_deg",
            "third_angle_deg",
            "fourth_angle_deg",
            "escape_angle_deg",
            "balance_angle_deg",
        ]:
            with self.subTest(axis=axis_key):
                self.assertIn(axis_key, metrics["key_axis_angle_spread_deg"])

    def test_loop_probe_writes_visual_review_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = run_chain_solver_loop_probe(seeds=[1, 2, 4, 5, 6], output_dir=Path(tmp))

            self.assertIn("visual_review_prompt", report["artifacts"])
            self.assertIn("diversity_report", report["artifacts"])
            self.assertTrue(Path(report["artifacts"]["visual_review_prompt"]).exists())
            self.assertTrue(Path(report["artifacts"]["diversity_report"]).exists())
            prompt = Path(report["artifacts"]["visual_review_prompt"]).read_text(encoding="utf-8")
            self.assertIn("visual_status: pass | fail", prompt)
            self.assertIn("same gear-axis layout family", prompt)

    def test_loop_probe_does_not_collapse_to_one_partition_topology(self):
        report = run_chain_solver_loop_probe(seeds=[1, 2, 4, 5, 6], output_dir=None)

        topology_counts = report["diversity_metrics"]["selected_partition_topology_counts"]
        self.assertGreaterEqual(len(topology_counts), 2)
        self.assertNotIn("all_candidates_use_same_partition_topology", report["failure_reasons"])

    def test_loop_probe_selects_set_with_barrel_bridge_diversity(self):
        report = run_chain_solver_loop_probe(seeds=[1, 2, 4, 5, 6], output_dir=None)

        area_cv = report["diversity_metrics"]["bridge_area_coefficient_of_variation"]["barrel_bridge"]
        span_cv = report["diversity_metrics"]["outer_service_island_span_coefficient_of_variation"]["barrel_bridge"]
        self.assertGreater(area_cv, 0.10)
        self.assertGreater(span_cv, 0.10)

    def test_bridge_partition_pass_does_not_make_axis_loop_pass(self):
        report = run_chain_solver_loop_probe(seeds=[1, 2, 4, 5, 6], output_dir=None)

        self.assertEqual("pass", report["bridge_partition_diversity_status"])
        if report["axis_diversity_status"] != "pass" or report["functional_envelope_diversity_status"] != "pass":
            self.assertEqual("fail", report["diversity_status"])
            self.assertNotEqual([], report["failure_reasons"])

    def test_loop_probe_requires_axis_and_envelope_diversity_gates(self):
        report = run_chain_solver_loop_probe(seeds=[1, 2, 4, 5, 6], output_dir=None)

        self.assertIn("axis_diversity_status", report)
        self.assertIn("functional_envelope_diversity_status", report)
        self.assertIn("bridge_partition_diversity_status", report)
        self.assertIn("axis_position_by_candidate", report["diversity_metrics"])
        self.assertIn("functional_envelope_overlap_by_group", report["diversity_metrics"])
        self.assertIn(report["axis_diversity_status"], {"pass", "fail"})
        self.assertIn(report["functional_envelope_diversity_status"], {"pass", "fail"})
        if report["axis_diversity_status"] != "pass" or report["functional_envelope_diversity_status"] != "pass":
            self.assertEqual("fail", report["diversity_status"])

    def test_loop_probe_axis_diversity_passes_after_structure_family_selection(self):
        report = run_chain_solver_loop_probe(seeds=[1, 2, 4, 5, 6], output_dir=None)

        self.assertEqual("pass", report["axis_diversity_status"])
        self.assertEqual([], report["axis_failure_reasons"])


if __name__ == "__main__":
    unittest.main()
