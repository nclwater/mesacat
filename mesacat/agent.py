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

    def update_route(self):
        """Updates the agent's route to the target node"""
        import numpy as np
        targets = [self.model.nodes.index.get_loc(node) for node in self.model.target_nodes.values]
        targets = list(set(targets))
        source = self.model.nodes.index.get_loc(self.pos)

        target_distances = self.model.igraph.shortest_paths_dijkstra(source=[source],
                                                                     target=set(targets),
                                                                     weights='length')[0]
        target = targets[int(np.argmin(target_distances))]
        path = self.model.igraph.get_shortest_paths(source, target)[0]

        self.route = self.model.nodes.iloc[path].index

    def distance_to_next_node(self):
        """Finds the distance to the next node along the route"""
        return self.model.G.get_edge_data(
            self.route[self.route_index], self.route[self.route_index+1])[0]['length'] - self.distance_along_edge

    def step(self):
        """Moves the agent towards the target node by 1 hour"""

        if self.route_index < len(self.route) - 1:

            distance_to_travel = self.speed

            distance_to_next_node = self.distance_to_next_node()

            while distance_to_travel >= distance_to_next_node:
                self.distance_along_edge = 0
                distance_to_travel -= distance_to_next_node
                self.route_index += 1
                self.model.grid.move_agent(self, self.route[self.route_index])

                if self.route_index >= len(self.route) - 1:
                    break

                distance_to_next_node = self.distance_to_next_node()

            self.distance_along_edge += distance_to_travel
