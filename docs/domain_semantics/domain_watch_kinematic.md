# Scope

`watch_kinematic` covers V1 watch-style kinematic demonstration mechanisms. It models visible rotational transmission, supported display axes, hands, bridges, plates, and decorative watch-case motifs for semantic and animation review. V1 is not a production mechanical-watch movement.

# V1 Object Types

- `watch_case`
- `movement_plate`
- `bridge`
- `drive_axis`
- `output_axis`
- `gear`
- `gear_train`
- `hand`
- `pivot_support`
- `decorative_motif`

# V1 Relations

- `drives_rotation(source_axis, target_axis)`
- `meshes_with(source_gear, target_gear)`
- `supports_axis(support_feature, motion_axis)`
- `displays_motion(hand, output_axis)`
- `decorates_case(decorative_motif, watch_case)`
- `uses_local_frame(object, local_frame)`

# V1 Motion Concepts

- `local_z_rotation`
- `visible_speed_ratio`
- `moving_group`
- `animation_sidecar`
- `motion_axis_local_frame`
- `gear_mesh_center_distance`

# V1 Exclusions

- `real_escapement`
- `mainspring_torque_model`
- `keyless_works`
- `time_setting`
- `automatic_winding`
- `calendar`
- `jewel_shock_protection`
- `timing_accuracy`

# Promotion Rules

`watch_kinematic` terms are domain terms and cannot be promoted to `mech_core` until at least one non-watch domain reuses the same term with deterministic validation.

Promotion candidates must have a stable definition, a deterministic validation check, and evidence that the concept is not only decorative watch-demo vocabulary.

# Validation Mapping

- `input_drive_axis_exists` validates that the case declares a drive axis.
- `gear_train_connects_drive_to_each_output_axis` validates that every output axis has a rotational transmission path from the drive axis.
- `each_visible_axis_has_support_path` validates that each visible rotating axis has support semantics.
- `mesh_pairs_have_center_distance_match` validates gear mesh layout compatibility.
- `no_unexplained_overlapping_gears` validates that overlapping rotating parts are either legal interfaces or reported errors.
- `animation_sidecar_covers_all_moving_groups` validates that every moving group has animation metadata.
- `all_motion_axes_have_local_frames` validates that drive and output axes resolve to the movement local frame.
