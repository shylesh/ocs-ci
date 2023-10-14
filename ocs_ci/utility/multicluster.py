"""
All multicluster specific utility functions and classes can be here

"""


class MutliClusterUpgradeParametrize(object):
    """
    This base class abstracts upgrade parametrization for multicluster scenarios: MDR, RDR and Managed service

    """

    MULTICLUSTER_UPGRADE_MARKERS = [
               "pre_upgrade",
               "pre_ocp_upgrade",
               "ocp_upgrade",
               "post_ocp_upgrade",
               "pre_ocs_upgrade",
               "ocs_upgrade",
               "post_ocs_upgrade",
               "post_upgrade"
    ]

    def __init__(self):
        self.roles = []
        # List of zones which are participating in this multicluster setup
        self.zones = []
        self.zone_base_rank = 100
        # Each zone will be assigned with a rank
        # This rank comes handy when we have to order the tests
        self.zone_ranks = {}

    def get_roles(self, metafunc):
        """
        should be overridden in the child class
        Look for specific role markers based on multicluster scenario

        Args:
            metafunc: Pytest metafunc fixture object
        """
        pass

    def generate_zone_ranks(self):
        """
        For each zone we would be generating the ranks, we will add the zone's respective indexes 
        to the base rank values which keeps the zone ranks apart and create spaces (for ranks)
        in between to accomodate other tests

        """
        for i in range(len(self.zones)):
            self.zone_ranks[f"{self.zones[i]}"] = self.zone_base_rank + i * self.zone_base_rank
            
    def generate_role_ranks(self):
        """
        Based on the multicluster scenario, child class should generate the corresponding
        role ranks. Roles are specific to multicluster scenarios

        """
        pass

    def generate_pytest_parameters(self, metafunc, roles):
        """
        should be overridden in the child class.
        This will be called for every testcase parametrization

        """
        pass

    def get_zone_info(self):
        """
        Get the list of participating zones

        """
        #TODO: Implement this
        return ['a', 'b', 'c']


class MDRClusterUpgradeParametrize(MutliClusterUpgradeParametrize):
    """
    This child class handles MDR upgrade scenario specific pytest parametrization

    """
    def __init__(self):
        super().__init__()
        self.zones = self.get_zone_info()
        self.mdr_roles = self.get_mdr_roles()
        self.generate_zone_ranks()
        self.generate_role_ranks()
        self.roles_to_param_tuples = {}
        self.generate_role_to_param_tuple_map()

    # In ocs-ci we need to build this based on the config provided
    def get_config_index_map(self):
        # Convention: build a dictionary with role name as key and a tuple (zone_rank, config_index) as 
        #value. For ex: {'ActiveACM': (100, 0), 'PassiceACM: (200, 1), 'Primary': (100, 2)
        # TO BE built before pytest_generate_test
        # TODO: Implement this to fetch indexes at run time
        return {'ActiveACM': 0, 'PassiveACM': 1, 'Primary_odf': 2, 'Secondary_odf': 3}

    def get_mdr_roles(self):
        """
        All MDR applicable roles
        """
        return ["ActiveACM", "PassiveACM", "Primary_odf", "Secondary_odf"]


    def generate_role_ranks(self):
        """
        Based on current roles for MDR : ActiveACM:1, PassiceACM:1, Primary:2, Secondary: 2

        """
        # TODO: add some more dynamic stuff
        self.role_ranks = {'ActiveACM': 1, 'PassiveACM': 1, 'Primary_odf': 2, 'Secondary_odf': 2}

    def get_zone_for_role(self, role):
        """
        Get zone to cluster with a multicluster role mapping

        """
        # TODO: Fetch zone to cluster mapping dynamically
        zone_role_map = {'ActiveACM': 'b', 'PassiveACM': 'c', 'Primary_odf': 'b', 'Secondary_odf': 'c'}
        return zone_role_map[role]

    def generate_role_to_param_tuple_map(self):
        """
        For each of the MDRs applicable roles store a tuple (zone_rank, role_rank, config_index)

        """
        for role in self.mdr_roles:
            self.roles_to_param_tuples[role] = (
                self.zone_ranks[self.get_zone_for_role(role)],
                self.role_ranks[role], 
                self.get_config_index_map()[role]
            )

    def get_pytest_params_tuple(self, role):
        """
        Generate a tuple of parameters applicable to the given role
        For ex: if role is 'ActiveACM', then generate a tuple which is applicable to 
                that role. If the role is 'all' then we will generate tuple of parameter 
                for each of the role applicable from MDRs perspective.
                Parmeter tuples looks like (zone_rank, role_rank, config_index)
        """
        param_list = list() 
        if role == 'all':
            for t in self.roles_to_param_tuples.values():
                param_list.append(t)
            param_list 
        else:
            param_list.append(self.roles_to_param_tuples[role])
        return param_list

    def get_roles(self, metafunc):
        # Return a list of roles applicable to the current test
        for marker in metafunc.definition.iter_markers():
            if marker.name == 'mdr_roles':
                return marker.args[0]

    def generate_pytest_parameters(self, metafunc, roles):
        """
        We will have to parametrize the test based on the MDR roles to which the test is applicable to,
        Parameters will be a tuple of (zone_rank, role_rank, config_index)

        """
        pytest_params = []
        for role in roles:
            pytest_params.extend(self.get_pytest_params_tuple(role))
        return pytest_params


multicluster_upgrade_parametrizer = {"metro-dr": MDRClusterUpgradeParametrize}


def get_multicluster_upgrade_parametrizer():
    return multicluster_upgrade_parametrizer["metro-dr"]()