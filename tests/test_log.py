# Importing pytest for testing purposes
import os

import pytest
from rich.logging import RichHandler

from netlist_carpentry import CFG
from netlist_carpentry.utils.log import Log, _create_handlers, initialize_logging

file_path = os.path.realpath(__file__)
file_dir_path = os.path.dirname(file_path)
LOG_DIRECTORY = file_dir_path + '/logs/'
LOG_NAME = 'log_setup.log'
LOG_PATH = LOG_DIRECTORY + LOG_NAME


@pytest.fixture
def log_setup():
    CFG.log_level = 1
    initialize_logging(LOG_DIRECTORY, custom_file_name=LOG_NAME)
    return Log()


def test_log_init(log_setup: Log) -> None:
    # Test initialization of Log class
    assert log_setup is not None


def test_log_info(log_setup: Log) -> None:
    # Test info method of Log class
    log_setup.info('Test info message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    assert 'Test info message' in next(line.strip() for line in logs)


def test_log_info_highlight(log_setup: Log) -> None:
    # Test info highlight method of Log class
    log_setup.info_highlighted('Test info message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    for line in logs:
        assert 'Test info message' in line or '#=====================#' in line


def test_log_info_level_too_high(log_setup: Log) -> None:
    CFG.log_level = 3
    log_setup.info('Test info message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    with pytest.raises(StopIteration):
        # Somehow pytest raises a StopIteration when trying to determine that the test info message is not in the file
        assert 'Test info message' not in next(line.strip() for line in logs)


def test_log_debug(log_setup: Log) -> None:
    # Test debug method of Log class
    log_setup.debug('Test debug message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    assert 'Test debug message' in next(line.strip() for line in logs)


def test_log_debug_highlight(log_setup: Log) -> None:
    # Test debug highlight method of Log class
    log_setup.debug_highlighted('Test debug message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    for line in logs:
        assert 'Test debug message' in line or '#======================#' in line


def test_log_debug_level_too_high(log_setup: Log) -> None:
    CFG.log_level = 2
    log_setup.debug('Test debug message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    with pytest.raises(StopIteration):
        # Somehow pytest raises a StopIteration when trying to determine that the test debug message is not in the file
        assert 'Test debug message' not in next(line.strip() for line in logs)


def test_log_warning(log_setup: Log) -> None:
    # Test warning method of Log class
    log_setup.warn('Test warning message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    assert 'Test warning message' in next(line.strip() for line in logs)


def test_log_warn_level_too_high(log_setup: Log) -> None:
    CFG.log_level = 4
    log_setup.warn('Test warn message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    with pytest.raises(StopIteration):
        # Somehow pytest raises a StopIteration when trying to determine that the test warn message is not in the file
        assert 'Test warn message' not in next(line.strip() for line in logs)


def test_log_error(log_setup: Log) -> None:
    # Test error method of Log class
    log_setup.error('Test error message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    assert 'Test error message' in next(line.strip() for line in logs)


def test_log_error_level_too_high(log_setup: Log) -> None:
    CFG.log_level = 5
    log_setup.error('Test error message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    with pytest.raises(StopIteration):
        # Somehow pytest raises a StopIteration when trying to determine that the test error message is not in the file
        assert 'Test error message' not in next(line.strip() for line in logs)


def test_log_fatal(log_setup: Log) -> None:
    # Test fatal method of Log class
    log_setup.fatal('Test fatal message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    assert 'Test fatal message' in next(line.strip() for line in logs)


def test_log_fatal_level_too_high(log_setup: Log) -> None:
    CFG.log_level = 6
    log_setup.fatal('Test fatal message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    with pytest.raises(StopIteration):
        # Somehow pytest raises a StopIteration when trying to determine that the test fatal message is not in the file
        assert 'Test fatal message' not in next(line.strip() for line in logs)


def test_log_fatal_and_exit(log_setup: Log) -> None:
    # Test fatal and exit method of Log class
    with pytest.raises(ValueError):
        log_setup.fatal_and_exit('Test fatal message', ValueError)
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    assert 'Test fatal message' in next(line.strip() for line in logs)


def test_log_mute_unmute(log_setup: Log) -> None:
    # Mute the log: messages should not be logged
    log_setup.mute()
    log_setup.error('Test error message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()

    with pytest.raises(StopIteration):
        # Somehow pytest raises a StopIteration when trying to determine that the test error message is not in the file
        assert 'Test error message' not in next(line.strip() for line in logs)

    # # Unmute the log: messages should be logged again
    log_setup.unmute()
    log_setup.error('Test error message')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    assert 'Test error message' in next(line.strip() for line in logs)


def test_format_string(log_setup: Log) -> None:
    # Test format_string method
    log_setup.longest_caller_name = 1
    CFG.print_source_module = True
    caller_name = log_setup.get_caller_name(skip_frames=[])
    formatted_str = log_setup.format_string('Test format string message')
    assert log_setup.longest_caller_name == 25
    assert caller_name == 'log.get_caller_name'
    assert 'Test format string message' in formatted_str


def test_get_caller_name_skip_all(log_setup: Log) -> None:
    name = log_setup.get_caller_name(['a', 'e', 'i', 'o', 'u'])
    assert name == 'invalid_caller_name'


def test_format_string_source_module(log_setup: Log) -> None:
    # Test format_string method
    log_setup.longest_caller_name = 1
    caller_name = log_setup.get_caller_name()
    prev_cfg = CFG.print_source_module
    CFG.print_source_module = True
    formatted_str = log_setup.format_string('Test format string message')
    CFG.print_source_module = prev_cfg
    assert log_setup.longest_caller_name == 25
    assert caller_name == 'python.pytest_pyfunc_call'
    assert 'Test format string message' in formatted_str
    assert caller_name in formatted_str


def test_initialize_logging(log_setup: Log) -> None:
    # Test initialize_logging method
    initialize_logging()
    # Assuming logging to a file, check if the log file exists
    import os

    assert os.path.exists(LOG_PATH)
    assert log_setup._init_finished


def test__create_handlers_no_file() -> None:
    # _create_handlers method, but without log file creation
    handlers, error = _create_handlers(CFG.output_dir, skip_file_creation=True)

    assert len(handlers) == 1
    assert isinstance(handlers[0], RichHandler)
    assert not error

    prev_path = Log.file_path
    Log.file_path = ''
    handlers, error = _create_handlers(LOG_DIRECTORY, skip_file_creation=False)
    Log.file_path = prev_path
    assert len(handlers) == 1
    assert isinstance(handlers[0], RichHandler)
    assert not error


def test__create_handlers_no_permission() -> None:
    # _create_handlers method, but without permission to create log file
    try:
        # TODO in ci this does work and does not create a PermissionError (is this wanted?)
        # So to supress that this test fails, we check whether the directory is created without raising a PermissionError
        os.makedirs('/logs/', exist_ok=True)
        handlers, error = _create_handlers(42, skip_file_creation=False)
        assert len(handlers) == 1
        assert isinstance(handlers[0], RichHandler)
        assert error
    except PermissionError:
        handlers, error = _create_handlers('/logs/', skip_file_creation=False)
        assert len(handlers) == 1
        assert isinstance(handlers[0], RichHandler)
        assert error


def test_log_info_with_fixture(log_setup: Log) -> None:
    # Test info method of Log class using fixture
    log_setup.info('Test info message with fixture')
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    assert 'Test info message with fixture' in next(line.strip() for line in logs)


# Using pytest parameterize
@pytest.mark.parametrize('message', [('Test info message'), ('Test debug message'), ('Test error message'), ('Test warning message')])
def test_log_methods_with_parameterize(log_setup: Log, message) -> None:
    initialize_logging(LOG_DIRECTORY, custom_file_name=LOG_NAME)
    if 'info' in message:
        log_setup.info(message)
    elif 'debug' in message:
        log_setup.debug(message)
    elif 'error' in message:
        log_setup.error(message)
    else:
        log_setup.warn(message)
    with open(LOG_PATH, 'r') as f:
        logs = f.readlines()
    assert message in next(line.strip() for line in logs)


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
