# Compatibility shim so the required command works from the repository root:
#   python -m unittest test_typosqat -v
from tests.test_typosquat import *  # noqa: F401,F403
