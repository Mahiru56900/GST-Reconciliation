"""Minimal local NetworkX-compatible subset for offline environments.

Implements only what this project needs: MultiDiGraph with node/edge operations.
"""

from __future__ import annotations


class MultiDiGraph:
    def __init__(self) -> None:
        self._nodes = {}
        self._out = {}
        self._edge_key = 0

    def add_node(self, node, **attrs):
        self._nodes[node] = dict(attrs)
        self._out.setdefault(node, [])

    def has_node(self, node) -> bool:
        return node in self._nodes

    @property
    def nodes(self):
        class _NodeView:
            def __init__(self, nodes):
                self._nodes = nodes

            def __getitem__(self, item):
                return self._nodes[item]

            def __call__(self, data=False):
                if data:
                    return list(self._nodes.items())
                return list(self._nodes.keys())

        return _NodeView(self._nodes)

    def add_edge(self, source, target, **attrs):
        self._out.setdefault(source, [])
        key = self._edge_key
        self._edge_key += 1
        self._out[source].append((source, target, key, dict(attrs)))

    def out_edges(self, node, keys=False, data=False):
        rows = self._out.get(node, [])
        result = []
        for source, target, key, attrs in rows:
            item = [source, target]
            if keys:
                item.append(key)
            if data:
                item.append(attrs)
            result.append(tuple(item))
        return result
