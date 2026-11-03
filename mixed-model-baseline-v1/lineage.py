"""Call-level lineage: one node per call, every routed dependency an edge, content verified.

Step 1: a role (e.g. "coder") may be called several times; each call is its own
node ("coder#1", "coder#2"). A call can only consume nodes that already exist,
so the call graph is acyclic even when the role graph has cycles.

Step 2: `CallRecorder` wraps the model provider (MetaGPT's BaseLLM.aask and its
siblings), so every model call is recorded whichever role, action or helper
made it.

Step 3: external inputs are nodes too: the task specification, each role's
instructions ("instructions:coder") and the model settings ("model_config").
If one of them changes, every call that depends on it can be found.

Edges come from the workflow's routing, never from content alone, so an altered
message cannot make an edge disappear. Nodes always hold what the agent really
produced. A message changed in transit (e.g. a fault injection) is not modelled
or explained; it surfaces only as a mismatch on the edge it travelled, as an
unknown real-world fault would. Each edge records:

  verified    received content equals the registered/produced content
  mismatch    received content differs; the source of the change is unknown
  unverified  content was unavailable, so it could not be checked
  captured    first sight of an unregistered external input; nothing to compare
  undeclared  not routed, but the producer's full output appears in the prompt
"""

from __future__ import annotations

import argparse
import contextvars
import hashlib
import json
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

SCHEMA = "call-graph/v5"
# Undeclared matches shorter than this can be coincidences; such edges are marked weak.
MIN_EVIDENCE_CHARS = 32
MODEL_METHODS = ("aask", "aask_batch", "aask_code")
# The settings saved in every trace's model_config.
MODEL_SETTINGS = ("model", "base_url", "temperature", "max_token", "timeout", "stream")

_current_role = contextvars.ContextVar("lineage_role", default=None)
_current_routes = contextvars.ContextVar("lineage_routes", default=None)
# Set while a recorded call runs, so nested provider methods are not recorded twice.
_inside_call = contextvars.ContextVar("lineage_inside_call", default=False)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def text_forms(text):
    # JSON payloads escape quotes and newlines, so also look for escaped forms.
    return {text, json.dumps(text)[1:-1], json.dumps(text, ensure_ascii=False)[1:-1]}


def appears_in(text, haystack):
    return any(form in haystack for form in text_forms(text))


def flatten_text(value):
    """Collect every string sent to the model: plain text, chat dicts, Message objects."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in flatten_text(item)]
    if isinstance(value, (list, tuple)):
        return [text for item in value for text in flatten_text(item)]
    content = getattr(value, "content", None)
    return [content] if isinstance(content, str) else []


def instructions_text(system_messages):
    """Canonical form of a role's instructions: the ordered system messages."""
    return json.dumps(list(system_messages))


def model_settings_text(settings):
    """Canonical model settings from a config object or a saved model_config dict."""
    get = settings.get if isinstance(settings, dict) else (lambda key: getattr(settings, key, None))
    return json.dumps({key: get(key) for key in MODEL_SETTINGS}, sort_keys=True, default=str)


def request_system_messages(method, args, kwargs, llm):
    """The system messages a provider call actually sends (mirrors MetaGPT 0.8.2 BaseLLM)."""
    if method == "aask":
        if not getattr(llm, "use_system_prompt", True):
            return []
        system = kwargs.get("system_msgs", args[1] if len(args) > 1 else None)
        return list(system) if system else [getattr(llm, "system_prompt", "")]
    messages = kwargs.get("messages", args[0] if args else None)
    if isinstance(messages, list):
        return [m.get("content", "") for m in messages if isinstance(m, dict) and m.get("role") == "system"]
    return []


def payload_routes(depends_on, payload):
    """Routes for the five-role payload {original_specification, previous_stage, previous_artifact}.

    Each route is (dependency name, text the consumer received or None, payload field).
    """
    payload = payload or {}
    fields = {"specification": "original_specification"}
    if payload.get("previous_stage"):
        fields[payload["previous_stage"]] = "previous_artifact"
    return [(name, payload.get(fields[name]) if name in fields else None, fields.get(name)) for name in depends_on]


class CallGraph:
    def __init__(self):
        self.nodes = {}
        self._calls_per_role = {}
        # Most recent completed node for each role/source name.
        self._latest = {}
        # Output text of data nodes, kept in memory only for undeclared matching.
        self._texts = {}

    def add_source(self, name, text=None, kind="external_input", **details):
        """Register an external input or configuration; re-registering identical content is a no-op."""
        if name in self.nodes:
            if text is not None and self.nodes[name].get("output_sha256") not in (None, sha256_text(text)):
                raise ValueError(f"{name} is already registered with different content.")
            return name
        self.nodes[name] = dict(id=name, kind=kind, seq=len(self.nodes), status="completed", inputs=[], **details)
        self._latest[name] = name
        self._store_output(name, text)
        return name

    def resolve(self, name):
        """Map a routed dependency (role or source name) to its latest completed node."""
        if name not in self._latest:
            raise ValueError(f"No completed call or source named {name!r} exists yet.")
        return self._latest[name]

    def _edge(self, node_id, received, via, sent_text=None):
        edge = dict(node=node_id, via=via)
        produced = self.nodes[node_id].get("output_sha256")
        if received is None or produced is None:
            edge["status"] = "unverified"
            return edge
        received_sha = sha256_text(received)
        edge.update(status="verified" if received_sha == produced else "mismatch", sent_sha256=produced, received_sha256=received_sha)
        if sent_text is not None:
            # Confirms the routed content was really part of the model request.
            edge["in_prompt"] = appears_in(received, sent_text)
        return edge

    def check_inputs(self, routes, sent_text=None):
        """Edges for every route, verified against the producer's output, plus undeclared ones.

        `routes` is a list of (dependency name, received text or None, via label).
        `sent_text` is everything actually sent to the model, when known.
        """
        inputs = []
        for name, received, via in routes:
            inputs.append(self._edge(self.resolve(name), received, via, sent_text))
        if sent_text is not None:
            routed = {edge["node"] for edge in inputs}
            carried = [received for _, received, _ in routes if received is not None]
            inputs += self._undeclared_inputs(sent_text, routed, carried)
        return inputs

    def check_configuration(self, name, received, via):
        """Edge to a configuration node; registers it on first sight when the runner did not."""
        if name not in self.nodes:
            self.add_source(name, received, kind="configuration", registered_by="recorder")
            return dict(node=name, via=via, status="captured" if received is not None else "unverified")
        return self._edge(name, received, via)

    def _undeclared_inputs(self, sent_text, routed, carried):
        matches = {}
        for node_id, output in self._texts.items():
            if node_id in routed or self.nodes[node_id]["kind"] == "configuration":
                continue
            if not output.strip() or not appears_in(output, sent_text):
                continue
            # Text quoted inside a routed message is explained by that edge.
            if any(output in received for received in carried):
                continue
            matches[node_id] = output
        inputs = []
        for node_id, output in matches.items():
            edge = dict(node=node_id, via=None, status="undeclared", sent_sha256=sha256_text(output))
            if len(output.strip()) < MIN_EVIDENCE_CHARS:
                edge["weak"] = True
            # Identical or nested outputs cannot be told apart; keep both (safe for recompute).
            containing = [other for other, text in matches.items() if other != node_id and output in text]
            if containing:
                edge["ambiguous_with"] = containing
            inputs.append(edge)
        return inputs

    def start_call(self, role, inputs, kind="model_call", **details):
        """Create the next node for `role`; every input must be a completed earlier node."""
        for edge in inputs:
            if self.nodes.get(edge["node"], {}).get("status") != "completed":
                raise ValueError(f"{role}: input {edge['node']!r} is not a completed earlier node.")
        number = self._calls_per_role.get(role, 0) + 1
        self._calls_per_role[role] = number
        node_id = f"{role}#{number}"
        self.nodes[node_id] = dict(id=node_id, kind=kind, role=role, call=number, seq=len(self.nodes), status="running", inputs=inputs, **details)
        return node_id

    def finish_call(self, node_id, status="completed", output=None, **details):
        node = self.nodes[node_id]
        node.update(status=status, **details)
        # Only completed calls can feed later calls.
        if status == "completed":
            self._latest[node["role"]] = node_id
            self._store_output(node_id, output)

    def _store_output(self, node_id, text):
        if text is None:
            return
        self.nodes[node_id].update(output_sha256=sha256_text(text), output_chars=len(text))
        self._texts[node_id] = text

    def affected(self, node_id):
        """Every node that transitively consumes `node_id`, in execution order."""
        found = {node_id}
        for node in sorted(self.nodes.values(), key=lambda n: n["seq"]):
            if any(edge["node"] in found for edge in node["inputs"]):
                found.add(node["id"])
        found.discard(node_id)
        return [n for n in self.nodes if n in found]

    def role_edges(self):
        """Collapse calls back to roles; this view may contain cycles."""
        edges = set()
        for node in self.nodes.values():
            target = node.get("role", node["id"])
            for edge in node["inputs"]:
                source = self.nodes[edge["node"]]
                edges.add((source.get("role", source["id"]), target))
        return sorted(edges)

    def edge_counts(self):
        return Counter(edge["status"] for node in self.nodes.values() for edge in node["inputs"])

    def validate(self):
        """Every input must be an earlier node; this guarantees no cycles."""
        for node in self.nodes.values():
            for edge in node["inputs"]:
                if edge["node"] not in self.nodes:
                    raise ValueError(f"{node['id']} references unknown node {edge['node']}")
                if self.nodes[edge["node"]]["seq"] >= node["seq"]:
                    raise ValueError(f"{node['id']} consumes later node {edge['node']}; call graph is not acyclic")

    def to_json(self):
        self.validate()
        return dict(schema=SCHEMA, nodes=list(self.nodes.values()))

    @classmethod
    def from_json(cls, data):
        if data.get("schema") != SCHEMA:
            raise ValueError(f"Unsupported lineage schema: {data.get('schema')}")
        graph = cls()
        for node in data["nodes"]:
            graph.nodes[node["id"]] = node
            if "role" in node:
                graph._calls_per_role[node["role"]] = max(graph._calls_per_role.get(node["role"], 0), node["call"])
                if node["status"] == "completed":
                    graph._latest[node["role"]] = node["id"]
            else:
                graph._latest[node["id"]] = node["id"]
        graph.validate()
        return graph

    @classmethod
    def from_trace(cls, trace):
        """Rebuild a saved five-role trace, verifying each edge against the saved stage inputs."""
        graph = cls()
        graph.add_source("specification", trace.get("specification"), trace_field="specification")
        graph.add_source("model_config", model_settings_text(trace["model_config"]), kind="configuration", trace_field="model_config")
        for index, stage in enumerate(trace["stages"]):
            saved_input = stage.get("input")
            inputs = graph.check_inputs(payload_routes(stage["depends_on"], saved_input), json.dumps(saved_input) if saved_input else None)
            if "guidance" in stage and "role_prefix" in stage:
                inputs.append(graph.check_configuration(f"instructions:{stage['stage']}", instructions_text([stage["role_prefix"], stage["guidance"]]), "role_prefix+guidance"))
            # Stages do not save their own settings; the run-level record cannot verify itself.
            inputs.append(dict(node="model_config", via="trace.model_config", status="unverified"))
            node_id = graph.start_call(stage["stage"], inputs, kind="trace_stage", trace_stage=index, execution=stage.get("execution", "original"))
            # The node holds what the agent produced; a later change shows as a mismatch downstream.
            graph.finish_call(node_id, status=stage["status"], output=stage.get("original_output"))
            # A running/failed stage blocks later stages, so stop there.
            if stage["status"] != "completed":
                break
        return graph


class CallRecorder:
    """Record every model call into a CallGraph while `recording()` is active."""

    def __init__(self, graph=None):
        self.graph = graph or CallGraph()

    @contextmanager
    def routing(self, routes):
        """Declare what the next role turn receives: [(dependency, received text, via)]."""
        token = _current_routes.set(routes)
        try:
            yield
        finally:
            _current_routes.reset(token)

    @contextmanager
    def recording(self, llm_classes=None, role_classes=None):
        """Patch model providers and roles; originals are restored on exit.

        Defaults to MetaGPT's BaseLLM (and loaded subclasses) and Role. Other
        frameworks can pass their own classes with the same method names.
        """
        if llm_classes is None or role_classes is None:
            from metagpt.provider.base_llm import BaseLLM
            from metagpt.roles import Role
            llm_classes = llm_classes or [BaseLLM, *all_subclasses(BaseLLM)]
            role_classes = role_classes or [Role]
        patches = [(cls, "run", self._wrap_role_run) for cls in role_classes if "run" in vars(cls)]
        patches += [(cls, name, self._wrap_model_call) for cls in llm_classes for name in MODEL_METHODS if name in vars(cls)]
        if not any(name in MODEL_METHODS for _, name, _ in patches):
            raise RuntimeError("No model methods found to record; refusing to run unrecorded.")
        originals = [(cls, name, vars(cls)[name]) for cls, name, _ in patches]
        if any(getattr(original, "__lineage_wrapped__", False) for _, _, original in originals):
            raise RuntimeError("A CallRecorder is already recording.")
        for cls, name, wrap in patches:
            setattr(cls, name, wrap(vars(cls)[name], name))
        try:
            yield self
        finally:
            for cls, name, original in originals:
                setattr(cls, name, original)

    def _wrap_role_run(self, original, _name):
        async def run(role, *args, **kwargs):
            # Attribute model calls made anywhere inside this role's turn.
            token = _current_role.set(getattr(role, "name", None) or type(role).__name__)
            try:
                return await original(role, *args, **kwargs)
            finally:
                _current_role.reset(token)
        run.__lineage_wrapped__ = True
        return run

    def _wrap_model_call(self, original, method):
        graph = self.graph

        async def call(llm, *args, **kwargs):
            if _inside_call.get():
                return await original(llm, *args, **kwargs)
            role = _current_role.get() or "unattributed"
            sent_text = "\n".join(flatten_text([args, kwargs]))
            routes = _current_routes.get()
            inputs = graph.check_inputs(routes or [], sent_text)
            # Configuration actually used by this request, checked against what was registered.
            inputs.append(graph.check_configuration(f"instructions:{role}", instructions_text(request_system_messages(method, args, kwargs, llm)), "system_messages"))
            inputs.append(graph.check_configuration("model_config", model_settings_text(getattr(llm, "config", None)), "llm.config"))
            node_id = graph.start_call(
                role,
                inputs,
                # Without declared routing, only undeclared matches can be found.
                routing="declared" if routes is not None else "none",
                method=method,
                prompt_sha256=sha256_text(sent_text),
            )
            token = _inside_call.set(True)
            started = time.perf_counter()
            try:
                output = await original(llm, *args, **kwargs)
            except BaseException as exc:
                graph.finish_call(node_id, status="error", error=f"{type(exc).__name__}: {exc}", elapsed_seconds=round(time.perf_counter() - started, 3))
                raise
            finally:
                _inside_call.reset(token)
            text = output if isinstance(output, str) else json.dumps(output, default=str)
            graph.finish_call(node_id, output=text, elapsed_seconds=round(time.perf_counter() - started, 3))
            return output
        call.__lineage_wrapped__ = True
        return call


def all_subclasses(cls):
    found = []
    for subclass in cls.__subclasses__():
        found += [subclass, *all_subclasses(subclass)]
    return found


def save_lineage(path, trace):
    """Write lineage.json for a saved trace that was not recorded live."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(CallGraph.from_trace(trace).to_json(), indent=2), encoding="utf-8")
    temporary.replace(path)


def describe(graph):
    def fmt(edges):
        return ", ".join(f"{edge['node']} [{edge['status']}{'?' if edge.get('weak') or edge.get('ambiguous_with') else ''}]" for edge in edges) or "-"

    lines = ["Call graph (one node per call; always acyclic):"]
    for node in graph.nodes.values():
        data = [e for e in node["inputs"] if graph.nodes[e["node"]]["kind"] != "configuration"]
        config = [e for e in node["inputs"] if graph.nodes[e["node"]]["kind"] == "configuration"]
        lines.append(f"  {node['id']:<28} <- {fmt(data):<58} ({node['kind']})")
        if config:
            lines.append(f"  {'':<28}    config: {fmt(config)}")
    edges = graph.role_edges()
    reverse = {(b, a) for a, b in edges}
    cycles = sorted({tuple(sorted(edge)) for edge in edges if edge in reverse and edge[0] != edge[1]})
    lines.append("Role graph cycles: " + (", ".join(f"{a} <-> {b}" for a, b in cycles) if cycles else "none"))
    lines.append("Edge statuses: " + ", ".join(f"{status}={count}" for status, count in sorted(graph.edge_counts().items())))
    lines.append("'?' = weak or ambiguous evidence; see the edge entry in lineage.json.")
    return "\n".join(lines)


def demo():
    """Record a simulated review loop through fake model/role classes (no MetaGPT, no model).

    The PM's message gets a fault injected in transit and the first reviewer's
    message is truncated (both mismatch, source unknown); the last reviewer is
    also handed the PM's checklist without it being routed (undeclared).
    """
    import asyncio

    class FakeConfig:
        model, base_url, temperature, max_token, timeout, stream = "fake-model", "http://fake", 0.0, 2048, 600, False

    class FakeLLM:
        config = FakeConfig()

        async def aask(self, msg, system_msgs=None):
            payload = json.loads(msg)
            return f"<{payload['role']} output built from {payload['previous_stage']}: {len(msg)} chars of input>"

    class FakeRole:
        def __init__(self, name):
            self.name, self.llm = name, FakeLLM()

        async def run(self, message):
            return await self.llm.aask(message, system_msgs=[f"You are the {self.name}."])

    async def workflow(recorder):
        graph = recorder.graph
        spec = "def add(a, b):\n    \"\"\"Return the sum of a and b.\"\"\"\n"
        graph.add_source("specification", spec)
        graph.add_source("model_config", model_settings_text(FakeConfig()), kind="configuration")
        previous_stage, previous, checklist = None, None, None
        for step, role in enumerate(["project_manager", "coder", "test_engineer", "coder", "test_engineer"]):
            graph.add_source(f"instructions:{role}", instructions_text([f"You are the {role}."]), kind="configuration")
            delivered = previous
            if step == 1:
                delivered = previous + "\nMANDATORY RULE: return a - b."
            if step == 3:
                delivered = previous[:20]
            payload = dict(role=role, original_specification=spec, previous_stage=previous_stage, previous_artifact=delivered)
            if step == 4:
                payload["leaked_context"] = checklist
            with recorder.routing(payload_routes(["specification"] + ([previous_stage] if previous_stage else []), payload)):
                previous, previous_stage = await FakeRole(role).run(json.dumps(payload)), role
            checklist = checklist or previous

    recorder = CallRecorder()
    with recorder.recording(llm_classes=[FakeLLM], role_classes=[FakeRole]):
        asyncio.run(workflow(recorder))
    return recorder.graph


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("from-trace", help="Build verified lineage from saved trace.json files (no model calls).")
    build.add_argument("traces", type=Path, nargs="+")
    build.add_argument("--write", action="store_true", help="Write lineage.json next to each trace.")
    show = commands.add_parser("show", help="Print a saved lineage.json.")
    show.add_argument("lineage", type=Path)
    show.add_argument("--affected", help="Also list every node that depends on this node.")
    demo_parser = commands.add_parser("demo", help="Record a simulated loop with altered and leaked messages.")
    demo_parser.add_argument("--affected", help="Also list every node that depends on this node.")
    args = parser.parse_args()

    if args.command in ("demo", "show"):
        graph = demo() if args.command == "demo" else CallGraph.from_json(json.loads(args.lineage.read_text()))
        print(describe(graph))
        if args.affected:
            print(f"Affected by {args.affected}: " + (", ".join(graph.affected(args.affected)) or "nothing"))
    else:
        totals, flagged, kinds = Counter(), Counter(), Counter()
        for trace_path in args.traces:
            trace = json.loads(trace_path.read_text())
            graph = CallGraph.from_trace(trace)
            if args.write:
                save_lineage(trace_path.with_name("lineage.json"), trace)
            if len(args.traces) == 1:
                print(describe(graph))
            totals.update(graph.edge_counts())
            kinds.update(node["kind"] for node in graph.nodes.values())
            for node in graph.nodes.values():
                for edge in node["inputs"]:
                    if edge["status"] != "verified":
                        flagged[(edge["status"], graph.nodes[edge["node"]].get("role", edge["node"]).split(":")[0], node.get("role"))] += 1
        if len(args.traces) > 1:
            print(f"Validated {len(args.traces)} traces" + (" and wrote lineage.json beside each." if args.write else "."))
            print("Node kinds: " + ", ".join(f"{kind}={count}" for kind, count in sorted(kinds.items())))
            print("Edge statuses: " + ", ".join(f"{status}={count}" for status, count in sorted(totals.items())))
            for (status, source, target), count in sorted(flagged.items()):
                print(f"  {status:<10} {source} -> {target}: {count}")


if __name__ == "__main__":
    main()
