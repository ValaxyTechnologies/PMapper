"""Python code for implementing a graph

Beyond G = (N, E), this object also holds the policy + group objects that are also part of evaluation. To
create a graph object, you need all the policies, then all the groups, then you can build the lists of nodes and edges.
"""

import json
import os
import os.path

from principalmapper.common.edges import Edge
from principalmapper.common.groups import Group
from principalmapper.common.nodes import Node
from principalmapper.util.storage import get_storage_root


class Graph(object):
    """The basic Graph object"""

    def __init__(self, nodes: list = None, edges: list = None, policies: list = None, groups: list = None,
                 metadata: dict = None):
        """Constructor"""
        for arg, value in {'nodes': nodes, 'edges': edges, 'policies': policies, 'groups': groups,
                           'metadata': metadata}.items():
            if value is None:
                raise ValueError('Required constructor argument {} was None'.format(arg))
        self.nodes = nodes
        self.edges = edges
        self.policies = policies
        self.groups = groups
        if 'account_id' not in metadata:
            raise ValueError('Incomplete metadata input, expected key: "account_id"')
        self.metadata = metadata

    def store_graph_as_json(self):
        """Stores the current Graph as a set of JSON documents on-disk at a standard location.

        If the directory does not exist yet, it is created.

        Structure:
        <root>/
        |--- <account id>
        |------- metadata.json
        |------- graph/
        |----------- nodes.json
        |----------- edges.json
        |----------- policies.json
        |----------- groups.json
        |------- visualizations/
        |----------- output.svg
        """
        rootpath = get_storage_root()
        rootpath = os.path.join(rootpath, self.metadata['account_id'])
        if not os.path.exists(rootpath):
            os.makedirs(rootpath, 0o700)
        graphdir = os.path.join(rootpath, 'graph')
        if not os.path.exists(graphdir):
            os.makedirs(graphdir, 0o700)
        metadatafilepath = os.path.join(rootpath, 'metadata.json')
        nodesfilepath = os.path.join(graphdir, 'nodes.json')
        edgesfilepath = os.path.join(graphdir, 'edges.json')
        policiesfilepath = os.path.join(graphdir, 'policies.json')
        groupsfilepath = os.path.join(graphdir, 'groups.json')

        old_umask = os.umask(0o077)  # block rwx for group/all
        with open(metadatafilepath, 'w') as f:
            json.dump(self.metadata, f, indent=4)
        with open(nodesfilepath, 'w') as f:
            json.dump([node.to_dictionary() for node in self.nodes], f, indent=4)
        with open(edgesfilepath, 'w') as f:
            json.dump([edge.to_dictionary() for edge in self.edges], f, indent=4)
        with open(policiesfilepath, 'w') as f:
            json.dump([policy.to_dictionary() for policy in self.policies], f, indent=4)
        with open(groupsfilepath, 'w') as f:
            json.dump([group.to_dictionary() for group in self.groups], f, indent=4)
        os.umask(old_umask)

    @classmethod
    def create_graph_from_local_disk(cls, account_id):
        """Generates a Graph object by pulling data from an account ID on disk

        Loads metadata, then policies, then groups, then nodes, then edges (to handle dependencies)
        """
        rootpath = get_storage_root()
        rootpath = os.path.join(rootpath, account_id)
        if not os.path.exists(rootpath):
            raise ValueError('This host does not have a Graph for account ID {}.'.format(account_id))
        graphdir = os.path.join(rootpath, 'graph')
        metadatafilepath = os.path.join(rootpath, 'metadata.json')
        nodesfilepath = os.path.join(graphdir, 'nodes.json')
        edgesfilepath = os.path.join(graphdir, 'edges.json')
        policiesfilepath = os.path.join(graphdir, 'policies.json')
        groupsfilepath = os.path.join(graphdir, 'groups.json')

        with open(metadatafilepath) as f:
            metadata = json.load(f)

        with open(policiesfilepath) as f:
            policies = json.load(f)

        with open(groupsfilepath) as f:
            unresolved_groups = json.load(f)
        groups = []
        for group in unresolved_groups:
            # dig through string list of attached policies to match up with policy objects with matching ARNs
            group_policies = []
            for policy in policies:
                if policy.arn in group['attached_policies']:
                    group_policies.append(policy)
            groups.append(Group(arn=group['arn'], attached_policies=group_policies))

        with open(nodesfilepath) as f:
            unresolved_nodes = json.load(f)
        nodes = []
        for node in unresolved_nodes:
            # dig through string list of groups and policies to match up with group and policy objects
            node_policies = []
            group_memberships = []
            for policy in policies:
                if policy.arn in node['attached_policies']:
                    node_policies.append(policy)
                    break
            for group in groups:
                if group.arn in node['group_memberships']:
                    group_memberships.append(group)
                    break
            nodes.append(Node(arn=node['arn'], attached_policies=node_policies, group_memberships=group_memberships,
                              access_keys=node['access_keys'], active_password=node['active_password'],
                              is_admin=node['is_admin']))

        with open(edgesfilepath) as f:
            unresolved_edges = json.load(f)
        edges = []
        for edge in unresolved_edges:
            # dig through nodes to find matching ARNs
            source = None
            destination = None
            for node in nodes:
                if node.arn == edge['source']:
                    source = node
                if node.arn == edge['destination']:
                    destination = node
                if source is not None and destination is not None:
                    break
            edges.append(Edge(source=source, destination=destination))

        return Graph(nodes=nodes, edges=edges, policies=policies, groups=groups, metadata=metadata)