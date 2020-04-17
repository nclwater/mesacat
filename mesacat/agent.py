from __future__ import annotations
from . import model
from mesa import Agent
from networkx import shortest_path, NetworkXException
import typing


class EvacuationAgent(Agent):
    """A person who is evacuating at a given speed

    Attributes:
        route: a list of node IDs that the agent is traversing
        route_index: the number of nodes that the agent has passed along the route
        speed: the speed at which the agent is travelling (km/hr)
        distance_along_edge: the distance that the agent has travelled from the most recent node
        pos: the ID of the most recent node that has been passed
    """
    def __init__(self, unique_id: int, evacuation_model: model.EvacuationModel):
        """
        Args:
            unique_id: an identifier for the agent
            evacuation_model: the parent EvacuationModel
        """
        super().__init__(unique_id, evacuation_model)
        self.route: typing.List[int] = []
        self.route_index: int = 0
        self.speed: float = 3
        self.distance_along_edge = 0
        self.pos: int = 0

    def update_route(self):
        """Updates the agent's route to the target node
        If there are no routes available, the agent is randomly placed at a different node until a route can be found
        """
        try:
            self.route = shortest_path(self.model.G, self.pos, self.model.target_node, 'length')
        except NetworkXException:
            self.model.place_agent(self)
            self.update_route()

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
