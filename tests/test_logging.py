
from app.logging_config import configure_logging, tail_log, list_log_files, log_dir

def test_configure_and_tail():
    d = configure_logging("INFO")
    assert d.exists()
    files = list_log_files()
    assert isinstance(files, list)
    # write a line via logger
    import logging
    logging.getLogger("mediaos").info("test_logging_probe")
    data = tail_log("mediaos.log", lines=50)
    assert "lines" in data
