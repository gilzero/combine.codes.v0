import pytest
import logging

@pytest.fixture(autouse=True)
def setup_logging(caplog):
    caplog.set_level(logging.INFO)
    logging.getLogger().setLevel(logging.INFO)
    # Configure the root logger to output to console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler) 