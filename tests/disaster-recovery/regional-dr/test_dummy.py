import logging
import pytest

from time import sleep

from ocs_ci.framework.testlib import rdr_test, acceptance
from ocs_ci.helpers import dr_helpers

logger = logging.getLogger(__name__)

@acceptance
@rdr_test
class TestDummy:
    """
    Test dummy action

    """

    def test_dummy(self):
        """

        """
        pass