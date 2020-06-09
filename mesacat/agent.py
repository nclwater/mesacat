from __future__ import annotations
from . import model
from mesa import Agent
import typing


class EvacuationAgent(Agent):
    """A person who is evacuating at a given speed

    Args:
        unique_id: an identifier for the agent
        evacuation_model: the parent EvacuationModel

    Attributes:
        route (typing.List[int]): a list of node IDs that the agent is traversing
        route_index (int): the number of nodes that the agent has passed along the route
        speed (float): the speed at which the agent is travelling (km/hr)
        distance_along_edge (float): the distance that the agent has travelled from the most recent node
        pos (int): the ID of the most recent node that has been passed
    """
    def __init__(self, unique_id: int, evacuation_model: model.EvacuationModel):
        super().__init__(unique_id, evacuation_model)
        self.route = []
        self.route_index = 0
        self.speed = 3
        self.distance_along_edge = 0
        self.pos = 0
        self.evacuated = False
        self.stranded = False

    def update_route(self):
        """Updates the agent's route to the target node"""
        import numpy as np
        if len(self.model.target_nodes) == 0:
            self.stranded = True
            return
        targets = [self.model.nodes.index.get_loc(node) for node in self.model.target_nodes.values]
        source = self.model.nodes.index.get_loc(self.pos)

        target_distances = self.model.igraph.shortest_paths_dijkstra(source=[source],
                                                                     target=targets,
                                                                     weights='length')[0]
        target = targets[int(np.argmin(target_distances))]
        path = self.model.igraph.get_shortest_paths(source, target, weights='length')[0]

        self.route = self.model.nodes.iloc[path].index
        self.route_index = 0

    def distance_to_next_node(self):
        """Finds the distance to the next node along the route"""
        return self.model.G.get_edge_data(
            self.route[self.route_index], self.route[self.route_index+1])[0]['length'] - self.distance_along_edge

    def step(self):
        """Moves the agent towards the target node by 10 seconds"""

        if self.evacuated or self.stranded:
            return

        distance_to_travel = self.speed / 60 / 60 * 10 * 1000  # metres travelled in ten seconds

        # If new node is reached
        while distance_to_travel >= self.distance_to_next_node():
            self.distance_along_edge = 0
            distance_to_travel -= self.distance_to_next_node()
            self.route_index += 1
            self.model.grid.move_agent(self, self.route[self.route_index])

            # If target is reached
            if self.route_index == len(self.route) - 1:
                # If target is at capacity
                if len(self.model.grid.get_cell_list_contents([self.pos])) > self.model.target_limit:
                    self.model.target_nodes = self.model.target_nodes[self.model.target_nodes.values != self.pos]
                    self.update_route()
                    if self.stranded:
                        return
                # If target is not at capacity
                else:
                    self.evacuated = True
                    return

        # If new node is not reached
        self.distance_along_edge += distance_to_travel
