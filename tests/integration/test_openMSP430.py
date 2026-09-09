import os

import pytest


def test_integration_tests() -> None:
    print('=================================================================== INTEGRATION TESTS')
    assert True


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
