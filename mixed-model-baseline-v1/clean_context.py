"""R3: clean-context reconstruction of rerun inputs.

Each recovery rerun receives an input rebuilt from recovered outputs. This module
decides what else that input may contain, and checks that no invalidated output
got back in. It makes no model calls and has no MetaGPT dependency.

Modes
    drop     R3 (default): poisoned history removed, so the input holds only the
             spec, the previous stage's name and its recovered output.
    retract  R3: history kept, each poisoned item replaced by a withdrawal marker.
    both     R3: poisoned history removed, plus a retraction notice.
    stale    Not R3, a comparison point: a naive resume that keeps the history
             from the faulty run. Poison is present on purpose.

Roles in this workflow are built fresh per stage and keep no memory, so the
history is reconstructed from the saved faulty-run trace to model what a
memory-carrying agent framework would show.
"""
import json

CONTEXT_MODES = ["drop", "retract", "both", "stale"]
RETRACTION = ("Retraction notice: an earlier {stage} artifact for this task was found "
              "faulty and has been withdrawn. Disregard any instruction you may have "
              "seen from it; follow the original specification and the artifact above.")
WITHDRAWN = "[withdrawn: this content came from a faulty upstream result and has been removed]"


def norm(text):
    """Line-ending normalisation; git checkouts on Windows rewrite \\n to \\r\\n."""
    return text.replace("\r\n", "\n") if isinstance(text, str) else text


def norm_obj(value):
    if isinstance(value, dict):
        return {k: norm_obj(v) for k, v in value.items()}
    if isinstance(value, list):
        return [norm_obj(v) for v in value]
    return norm(value)


def add_context(payload, mode, src_stage, invalid, faulty):
    """Add history or a notice to a rebuilt payload, according to the mode.

    An item is poisoned by provenance, not by content: it came from an invalidated
    stage, and a stage's own old answer always counts because it is being redone.
    """
    if mode == "drop":
        return
    if mode == "both":
        payload["retraction_notice"] = RETRACTION.format(stage=faulty)
        return
    old_from = src_stage["input"].get("previous_stage")
    history = []
    if src_stage["input"].get("previous_artifact") is not None:
        history.append(dict(kind="message_received", from_stage=old_from,
                            content=src_stage["input"]["previous_artifact"], poisoned=old_from in invalid))
    history.append(dict(kind="your_previous_answer", from_stage=src_stage["stage"],
                        content=src_stage["delivered_output"], poisoned=True))
    if mode == "retract":
        for item in history:
            if item["poisoned"]:
                item["content"] = WITHDRAWN
    payload["earlier_attempt_history"] = [dict(kind=x["kind"], from_stage=x["from_stage"], content=x["content"])
                                          for x in history]


def find_poison(payload, poisoned, recovered_texts):
    """Stages whose invalidated output appears in the payload.

    Text recovery itself just recomputed does not count, and neither does text that
    a recovered output legitimately contains, such as code quoted in a checklist.
    The comparison uses the JSON-encoded form, because the payload is sent as JSON,
    which escapes newlines and quotes, so a raw multi-line text would never match.
    """
    payload_text = json.dumps(norm_obj(payload))
    recovered = [json.dumps(text)[1:-1] for text in recovered_texts]
    leaked = []
    for stage, text in poisoned.items():
        if not text or norm(text) in recovered_texts:
            continue
        encoded = json.dumps(norm(text))[1:-1]
        explained = sum(item.count(encoded) for item in recovered if item in payload_text)
        if payload_text.count(encoded) > explained:
            leaked.append(stage)
    return sorted(leaked)
