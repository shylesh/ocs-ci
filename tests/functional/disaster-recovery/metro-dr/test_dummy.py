import logging
import pytest

logger = logging.getLogger(__name__)


class TestDummy:
    """ """

    @pytest.fixture(autouse=True)
    def teardown(self, request):
        """ """

        def finalizer():
            pass

        request.addfinalizer(finalizer)

    @pytest.mark.polarion_id("OCS-XXXX")
    def test_dummy(self):
        """
        Tests dummy

        """
        logger.info("dummy test run")
