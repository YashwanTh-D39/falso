"""
FALSO 4.11 Security Evidence Graph.

Models verified relationships between security entities:
HOST -> PROCESS -> SOCKET -> PORT -> NETWORK -> EVENT -> FINDING
PROCESS -> FILE, PROCESS -> PARENT_PROCESS, SERVICE -> PROCESS
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

from app.services.automation.operator.security.evidence import SecretRedactor


@dataclass
class GraphNode:
    node_id: str
    node_type: str  # "host", "process", "socket", "port", "network", "file", "event", "finding"
    properties: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "properties": SecretRedactor.redact_dict(self.properties),
            "timestamp": self.timestamp,
        }


@dataclass
class GraphEdge:
    from_node: str
    to_node: str
    relation: str  # "owns", "binds", "created", "targets", "parent_of", "accessed"
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_node": self.from_node,
            "to_node": self.to_node,
            "relation": self.relation,
            "properties": SecretRedactor.redact_dict(self.properties),
        }


class SecurityEvidenceGraph:
    """Directed graph representing structured relationships between security entities."""

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []

    def add_node(self, node_id: str, node_type: str, properties: dict[str, Any] | None = None) -> GraphNode:
        node = GraphNode(node_id=node_id, node_type=node_type, properties=properties or {})
        self.nodes[node_id] = node
        return node

    def add_edge(self, from_node: str, to_node: str, relation: str, properties: dict[str, Any] | None = None) -> GraphEdge:
        edge = GraphEdge(from_node=from_node, to_node=to_node, relation=relation, properties=properties or {})
        self.edges.append(edge)
        return edge

    def correlate_port_to_process(self, port: int) -> dict[str, Any] | None:
        """Trace from Port -> Socket -> Process in graph."""
        port_node_id = f"port_{port}"
        if port_node_id not in self.nodes:
            return None

        # Find incoming edge to port
        for e in self.edges:
            if e.to_node == port_node_id and e.relation in ("binds", "listens_on"):
                socket_node = self.nodes.get(e.from_node)
                # Find process owning this socket
                for e2 in self.edges:
                    if e2.to_node == e.from_node and e2.relation == "owns":
                        proc_node = self.nodes.get(e2.from_node)
                        return {
                            "port": port,
                            "socket": socket_node.properties if socket_node else {},
                            "process": proc_node.properties if proc_node else {},
                        }
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
        }
