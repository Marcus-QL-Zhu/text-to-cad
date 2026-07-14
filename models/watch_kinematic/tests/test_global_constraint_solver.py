import unittest

from models.watch_kinematic.watch_kinematic.chain_solver_loop import run_global_constraint_solver_loop_probe
from models.watch_kinematic.watch_kinematic.global_constraint_solver import solve_global_axis_constraints


class WatchGlobalConstraintSolverTests(unittest.TestCase):
    def test_solves_multiple_global_axis_candidates(self):
        report = solve_global_axis_constraints(seed=42, target_count=5)

        self.assertEqual("watch_global_axis_constraint_solver_report", report["kind"])
        self.assertEqual("pass", report["status"])
        self.assertEqual("region_classify_prune_refine_cluster", report["selection_strategy"])
        self.assertGreaterEqual(len(report["candidates"]), 5)
        self.assertIn("distance(center, third) = center_third_mesh_distance", report["constraint_equations"])
        self.assertIn("variable_domains", report)
        self.assertIn("region_classification", report)
        self.assertGreater(report["region_classification"]["classified_region_count"], 0)
        self.assertGreater(report["region_classification"]["pruned_region_count"], 0)
        self.assertGreaterEqual(report["region_classification"]["feasible_region_count"], 5)

        signatures = set()
        for candidate in report["candidates"][:5]:
            with self.subTest(candidate=candidate["candidate_id"]):
                self.assertEqual("pass", candidate["status"])
                self.assertEqual("pass", candidate["global_constraint_status"])
                self.assertIn("axes", candidate)
                self.assertIn("variables", candidate)
                self.assertIn("solver_residual_norm", candidate)
                self.assertLess(candidate["solver_residual_norm"], 1e-5)
                self.assertTrue(candidate["global_solver_source"].startswith("region_box:"))
                self.assertNotIn("baseline_diagonal", candidate["global_solver_source"])
                self.assertNotIn("lower_train_sweep", candidate["global_solver_source"])
                self.assertNotIn("upper_arc_sweep", candidate["global_solver_source"])
                self.assertTrue(all(proof["status"] == "pass" for proof in candidate["center_distance_proofs"]))
                self.assertEqual([], candidate["failed_reasons"])
                axes = {axis["axis_id"]: axis for axis in candidate["axes"]}
                signatures.add(
                    tuple(
                        (
                            axis_id,
                            round(axes[axis_id]["x"], 1),
                            round(axes[axis_id]["y"], 1),
                        )
                        for axis_id in ["barrel_axis", "third_axis", "fourth_axis", "escape_axis", "balance_axis"]
                    )
                )
        self.assertGreaterEqual(len(signatures), 3)

    def test_region_cluster_representatives_are_from_distinct_regions(self):
        report = solve_global_axis_constraints(seed=42, target_count=5)

        self.assertEqual("pass", report["status"])
        self.assertEqual(5, len(report["representative_clusters"]))
        regions = {candidate["region_id"] for candidate in report["candidates"][:5]}
        clusters = {candidate["cluster_id"] for candidate in report["candidates"][:5]}
        self.assertEqual(5, len(regions))
        self.assertEqual(5, len(clusters))
        for cluster in report["representative_clusters"]:
            self.assertEqual("pass", cluster["status"])
            self.assertIn("representative_candidate_id", cluster)

    def test_global_constraint_candidates_pass_axis_loop_probe(self):
        report = run_global_constraint_solver_loop_probe(seed=42, target_count=5, output_dir=None)

        self.assertEqual("watch_global_constraint_solver_loop_probe", report["kind"])
        self.assertEqual("pass", report["axis_diversity_status"])
        self.assertEqual("pass", report["functional_envelope_diversity_status"])
        self.assertEqual("pass", report["diversity_status"])
        self.assertEqual([], report["failure_reasons"])
        self.assertGreaterEqual(len(report["candidates"]), 5)


if __name__ == "__main__":
    unittest.main()
