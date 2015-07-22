#!/usr/bin/env python2
"""
    drbdmanage - management of distributed DRBD9 resources
    Copyright (C) 2013, 2014   LINBIT HA-Solutions GmbH
                               Author: R. Altnoeder

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import drbdmanage.utils
import drbdmanage.drbd.drbdcore


class Quorum(object):
    """
    Implements a simple quorum algorithm
    """

    COUNT_MIN = 1
    COUNT_MAX = 31

    FULL_MIN = 3

    _server = None

    _quorum_count = 1
    _quorum_full  = 1
    _quorum_nodes = {}


    def __init__(self, server_ref):
        self._server = server_ref


    def node_joined(self, node_name):
        """
        Adds a node to the partition (if the node type fits)
        """
        # Check whether the target of the new connection
        # is already in the list of quorum nodes
        if node_name not in self._quorum_nodes:
            # Check whether the target of the new connection
            # is a known drbdmanage node
            quorum_node = self._server.get_node(node_name)
            if quorum_node is not None:
                state = quorum_node.get_state()
                if drbdmanage.utils.is_set(state, drbdmanage.drbd.drbdcore.DrbdNode.FLAG_DRBDCTRL):
                    # Add the node to the list of joined quorum nodes
                    # and increase the quorum count
                    connected_count = len(self._quorum_nodes)
                    if connected_count < Quorum.COUNT_MAX:
                        self._quorum_nodes[node_name] = None
                        connected_count += 1

                        # The number of nodes in the partition is
                        # the number of connected nodes plus the local node
                        self._quorum_count = connected_count + 1

                        # If more than the number of expected nodes are connected,
                        # increase the expected number of nodes
                        # (automatic quorum readjustment)
                        if self._quorum_count > self._quorum_full:
                            self._quorum_full = self._quorum_count
                            logging.debug("Quorum: Expected number of nodes increased to %d"
                                          % (self._quorum_full))
                        logging.debug("Quorum: Node %s joined the partition, "
                                      "[%d nodes of %d expected nodes present]"
                                      % (node_name,
                                         self._quorum_count, self._quorum_full))
                    else:
                        logging.error("Quorum: Cannot add node, exceeding maximum of %d nodes"
                                      % (Quorum.COUNT_MAX))
                        logging.error("Quorum: Internal error or incompatible "
                                      "version of DRBD")
                else:
                    logging.debug("Quorum: Diskless node %s joined the partition, "
                                  "quorum count unchanged"
                                  % (node_name))
            else:
                logging.warning("Quorum: Node %s is not a registered drbdmanage node")


    def node_left(self, node_name):
        """
        Removes a node from the partition
        """
        if node_name in self._quorum_nodes:
            del self._quorum_nodes[node_name]
            connected_count = len(self._quorum_nodes)
            self._quorum_count = connected_count + 1
            logging.debug("Quorum: Node %s left the partition "
                          "[%d nodes of %d expected nodes present]"
                          % (node_name, self._quorum_count, self._quorum_full))
        else:
            logging.debug("Quorum: Node %s left the partition, but was not listed "
                          "as a quorum member, quorum count unchanged"
                          % (node_name))


    def is_present(self):
        """
        Indicates whether the partition has a quorum or not
        """
        present = False
        if self._quorum_full >= Quorum.FULL_MIN:
            threshold = int(self._quorum_full) / 2 + 1
            if self._quorum_count >= threshold:
                present = True
        else:
            present = True
        return present


    def is_active_member_node(self, node_name):
        """
        Indicates whether a node is an active member of this partition
        """
        return True if node_name in self._quorum_nodes else False


    def set_full_member_count(self, count):
        """
        Sets the maximum number of nodes that are expected as quorum members
        """
        if count >= 1 and count <= Quorum.COUNT_MAX:
            self._quorum_full = count
        else:
            raise ValueError


    def get_full_member_count(self):
        """
        Returns the maximum number of nodes that are expected as quorum members
        """
        return self._quorum_full


    def get_active_member_count(self):
        """
        Returns the number of currently active member nodes
        """
        return self._quorum_count
