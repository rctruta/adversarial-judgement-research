import pytest

def pytest_addoption(parser):
    """Registers the custom command line flag."""
    parser.addoption(
        "--run-live", action="store_true", default=False, help="Run live API integration tests"
    )

def pytest_configure(config):
    """Registers the custom marker to prevent pytest warnings."""
    config.addinivalue_line("markers", "live: mark test as requiring a live API connection")

def pytest_collection_modifyitems(config, items):
    """Skips live tests unless the flag is explicitly passed."""
    if config.getoption("--run-live"):
        # If the flag is passed, do not skip anything
        return
    
    skip_live = pytest.mark.skip(reason="need --run-live option to run")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)