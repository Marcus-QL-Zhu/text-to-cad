def test_watch_generator_runtime_dependencies_import():
    import build123d  # noqa: F401
    import matplotlib  # noqa: F401
    import numpy  # noqa: F401
    import PIL  # noqa: F401
    import scipy  # noqa: F401
