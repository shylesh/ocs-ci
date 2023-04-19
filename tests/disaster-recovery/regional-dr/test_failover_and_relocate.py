import logging
import pytest

from time import sleep

from ocs_ci.framework import config
from ocs_ci.framework.testlib import acceptance, tier1
from ocs_ci.helpers import dr_helpers
from ocs_ci.ocs.node import wait_for_nodes_status, get_node_objs
from ocs_ci.ocs.resources.pod import wait_for_pods_to_be_running
from ocs_ci.utility.utils import ceph_health_check

logger = logging.getLogger(__name__)


@acceptance
@tier1
class TestFailoverAndRelocate:
    """
    Test Failover and Relocate actions

    """

    @pytest.mark.parametrize(
        argnames=["primary_cluster_down"],
        argvalues=[
            pytest.param(
                False, marks=pytest.mark.polarion_id("OCS-4430"), id="primary_up"
            ),
            pytest.param(
                True, marks=pytest.mark.polarion_id("OCS-4427"), id="primary_down"
            ),
        ],
    )
    def test_failover_and_relocate(
        self,
        primary_cluster_down,
        nodes_multicluster,
        rdr_workload,
        node_restart_teardown,
    ):
        """
        Tests to verify application failover and relocate between managed clusters
        There are two test cases:
            1) Failover to secondary cluster when primary cluster is UP and Relocate
                back to primary cluster
            2) Failover to secondary cluster when primary cluster is DOWN and Relocate
                back to primary cluster once it recovers

        """
        dr_helpers.set_current_primary_cluster_context(rdr_workload.workload_namespace)
        primary_cluster_index = config.cur_index
        node_objs = get_node_objs()

        scheduling_interval = dr_helpers.get_scheduling_interval(
            rdr_workload.workload_namespace
        )
        wait_time = 2 * scheduling_interval  # Time in minutes
        logger.info(f"Waiting for {wait_time} minutes to run IOs")
        sleep(wait_time * 60)

        # Stop primary cluster nodes
        if primary_cluster_down:
            logger.info("Stopping primary cluster nodes")
            nodes_multicluster[primary_cluster_index].stop_nodes(node_objs)

        # Failover action
        secondary_cluster_name = dr_helpers.get_current_secondary_cluster_name(
            rdr_workload.workload_namespace
        )
        dr_helpers.failover(secondary_cluster_name, rdr_workload.workload_namespace)

        # Verify resources creation on new primary cluster (failoverCluster)
        dr_helpers.set_current_primary_cluster_context(rdr_workload.workload_namespace)
        dr_helpers.wait_for_all_resources_creation(
            rdr_workload.workload_pvc_count,
            rdr_workload.workload_pod_count,
            rdr_workload.workload_namespace,
        )

        # Verify resources deletion from previous primary or current secondary cluster
        dr_helpers.set_current_secondary_cluster_context(
            rdr_workload.workload_namespace
        )
        # Start nodes if cluster is down
        if primary_cluster_down:
            logger.info(
                f"Waiting for {wait_time} minutes before starting nodes of previous primary cluster"
            )
            sleep(wait_time * 60)
            nodes_multicluster[primary_cluster_index].start_nodes(node_objs)
            wait_for_nodes_status([node.name for node in node_objs])
            logger.info(
                "Wait for all the pods in openshift-storage to be in running state"
            )
            assert wait_for_pods_to_be_running(
                timeout=720
            ), "Not all the pods reached running state"
            logger.info("Checking for Ceph Health OK")
            ceph_health_check()
        dr_helpers.wait_for_all_resources_deletion(rdr_workload.workload_namespace)

        dr_helpers.wait_for_mirroring_status_ok()

        logger.info(f"Waiting for {wait_time} minutes to run IOs")
        sleep(wait_time * 60)

        # Relocate action
        secondary_cluster_name = dr_helpers.get_current_secondary_cluster_name(
            rdr_workload.workload_namespace
        )
        dr_helpers.relocate(secondary_cluster_name, rdr_workload.workload_namespace)

        # Verify resources deletion from previous primary or current secondary cluster
        dr_helpers.set_current_secondary_cluster_context(
            rdr_workload.workload_namespace
        )
        dr_helpers.wait_for_all_resources_deletion(rdr_workload.workload_namespace)

        # Verify resources creation on new primary cluster (preferredCluster)
        dr_helpers.set_current_primary_cluster_context(rdr_workload.workload_namespace)
        dr_helpers.wait_for_all_resources_creation(
            rdr_workload.workload_pvc_count,
            rdr_workload.workload_pod_count,
            rdr_workload.workload_namespace,
        )

        dr_helpers.wait_for_mirroring_status_ok()

        # TODO: Add data integrity checks
