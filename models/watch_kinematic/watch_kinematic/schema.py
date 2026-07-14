REQUIRED_CASE_FIELDS = (
    "case_id",
    "mechanism_type",
    "case_diameter_mm",
    "movement_thickness_mm",
    "local_frame",
    "drive_axis",
    "output_axes",
    "style",
    "excluded_systems",
    "acceptance_criteria",
)

ALLOWED_EXCLUDED_SYSTEMS = frozenset(
    {
        "real_escapement",
        "mainspring_torque_model",
        "keyless_works",
        "time_setting",
        "automatic_winding",
        "calendar",
        "jewel_shock_protection",
        "timing_accuracy",
    }
)
