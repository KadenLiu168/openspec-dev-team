#!/usr/bin/env python3
"""Deterministic, local state transitions for an OpenSpec team run."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
import uuid


ACTIVE_STATES = {
    "NEW", "EXPLORING", "AWAITING_EXPLORE_APPROVAL", "PROPOSING",
    "REVIEWING_PROPOSAL", "REVISING_PROPOSAL", "APPLYING", "AUDITING",
    "FIXING_IMPLEMENTATION", "READY_TO_PUBLISH", "PUBLISHING",
    "BLOCKED", "NEEDS_HUMAN",
}

OWNER_BY_STATE = {
    "NEW": "Orchestrator",
    "EXPLORING": "Explore / Proposal",
    "AWAITING_EXPLORE_APPROVAL": "Orchestrator + Human",
    "PROPOSING": "Explore / Proposal",
    "REVIEWING_PROPOSAL": "Proposal Reviewer",
    "REVISING_PROPOSAL": "Explore / Proposal",
    "APPLYING": "Apply Executor",
    "AUDITING": "Pre-Archive Auditor",
    "FIXING_IMPLEMENTATION": "Apply Executor",
    "READY_TO_PUBLISH": "Orchestrator",
    "PUBLISHING": "Archivist / Publisher",
    "DONE": None,
    "CANCELLED": None,
    "BLOCKED": "current specialist -> Orchestrator",
    "NEEDS_HUMAN": "Orchestrator + Human",
}

REQUIRED_BY_STATE = {
    "EXPLORING": ("PRE_CHANGE",),
    "PROPOSING": ("POST_CHANGE", "HUMAN_GATE"),
    "REVIEWING_PROPOSAL": ("POST_CHANGE", "HUMAN_GATE"),
    "REVISING_PROPOSAL": ("POST_CHANGE", "HUMAN_GATE"),
    "APPLYING": ("POST_CHANGE", "HUMAN_GATE", "APPLY"),
    "AUDITING": ("POST_CHANGE", "HUMAN_GATE", "APPLY"),
    "FIXING_IMPLEMENTATION": ("POST_CHANGE", "HUMAN_GATE", "APPLY"),
    "PUBLISHING": ("POST_CHANGE", "HUMAN_GATE", "APPLY", "PUBLISHING"),
}

HANDOFF_FIELDS = (
    "RUN_ID", "ATTEMPT_ID", "STATUS", "CHANGE", "REQUEST_ARTIFACT",
    "APPROVAL_ARTIFACT", "SUMMARY", "EVIDENCE", "BLOCKERS", "ARTIFACTS",
    "PROPOSAL_DIGEST", "PROGRESS_DIGEST", "BASE_SHA", "HEAD_SHA",
    "PUBLISH_STEP_RECEIPTS", "NEXT_STATE",
)

VALID_STATUSES = {"PASS", "FAIL", "BLOCKED", "NEEDS_HUMAN"}
PUBLISH_STEPS = ("PREFLIGHT", "ARCHIVE", "VALIDATE", "FINAL_COMMIT", "PUSH", "LINEAR_SYNC", "COMPLETE")
PUBLISH_AUTHORIZATION_FIELDS = (
    "RUN_ID", "PROJECT_REALPATH", "BRANCH", "REMOTE_URL", "CHANGE",
    "APPROVAL_ARTIFACT", "APPROVAL_DIGEST", "PROPOSAL_DIGEST", "PROGRESS_DIGEST", "BASE_SHA", "HEAD_SHA",
)
SPECIALIST_OWNERS = {
    "Explore / Proposal", "Proposal Reviewer", "Apply Executor", "Pre-Archive Auditor", "Archivist / Publisher",
}
PROPOSAL_CHANGE_EVENTS = {
    "PROPOSAL_CHANGED": None,
    "PROPOSAL_CHANGED_WITHIN_SCOPE": "WITHIN_APPROVED_SCOPE",
    "PROPOSAL_CHANGED_OUTSIDE_SCOPE": "OUTSIDE_APPROVED_SCOPE",
}
EVENT_STATUS = {
    "PASS": "PASS", "FAIL": "FAIL", "BLOCKED": "BLOCKED", "STEP_PASS": "PASS",
    "NEEDS_HUMAN": "NEEDS_HUMAN", **{event: "PASS" for event in PROPOSAL_CHANGE_EVENTS},
}
BINDING_FIELDS = (
    "CHANGE", "PROPOSAL_DIGEST", "PROGRESS_DIGEST", "BASE_SHA", "HEAD_SHA",
    "APPROVAL_ARTIFACT", "APPROVAL_DIGEST", "UNTRACKED_BASELINE",
    "EXPLORE_ARTIFACT", "EXPLORE_DIGEST",
)
OUTPUT_BINDINGS_BY_STATE = {
    "EXPLORING": {"EXPLORE_ARTIFACT", "EXPLORE_DIGEST"},
    "PROPOSING": {"PROPOSAL_DIGEST", "PROGRESS_DIGEST"},
    "REVISING_PROPOSAL": {"PROPOSAL_DIGEST", "PROGRESS_DIGEST"},
    "APPLYING": {"PROGRESS_DIGEST", "HEAD_SHA"},
    "FIXING_IMPLEMENTATION": {"PROGRESS_DIGEST", "HEAD_SHA"},
}
RECOVERABLE_STATES = ACTIVE_STATES - {"BLOCKED", "NEEDS_HUMAN"}


def fail(message):
    os.write(2, (json.dumps({"error": message}, sort_keys=True) + "\n").encode())
    return 1


def read_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, path)


def now():
    return datetime.now(timezone.utc).isoformat()


def git_output(project, *arguments):
    result = subprocess.run(
        ["git", *arguments], cwd=project, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True,
    )
    return result.stdout.strip()


def optional_git_output(project, *arguments):
    try:
        return git_output(project, *arguments)
    except subprocess.CalledProcessError:
        return ""


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def next_state(state, event):
    fixed = {
        ("NEW", "START"): "EXPLORING",
        ("EXPLORING", "PASS"): "AWAITING_EXPLORE_APPROVAL",
        ("AWAITING_EXPLORE_APPROVAL", "APPROVE"): "PROPOSING",
        ("AWAITING_EXPLORE_APPROVAL", "REVISE"): "EXPLORING",
        ("AWAITING_EXPLORE_APPROVAL", "REJECT"): "CANCELLED",
        ("PROPOSING", "PASS"): "REVIEWING_PROPOSAL",
        ("REVIEWING_PROPOSAL", "PASS"): "APPLYING",
        ("REVISING_PROPOSAL", "PASS"): "REVIEWING_PROPOSAL",
        ("APPLYING", "PASS"): "AUDITING",
        ("APPLYING", "PROPOSAL_CHANGED_WITHIN_SCOPE"): "REVIEWING_PROPOSAL",
        ("APPLYING", "PROPOSAL_CHANGED_OUTSIDE_SCOPE"): "EXPLORING",
        ("FIXING_IMPLEMENTATION", "PASS"): "AUDITING",
        ("READY_TO_PUBLISH", "AUTHORIZE_PUBLISH"): "PUBLISHING",
        ("NEEDS_HUMAN", "RETRY_PROPOSAL"): "REVISING_PROPOSAL",
        ("NEEDS_HUMAN", "RETRY_IMPLEMENTATION"): "FIXING_IMPLEMENTATION",
        ("NEEDS_HUMAN", "REVISE_DIRECTION"): "EXPLORING",
        ("NEEDS_HUMAN", "CANCEL"): "CANCELLED",
    }
    if event == "BLOCKED" and state in ACTIVE_STATES - {"BLOCKED"}:
        return "BLOCKED"
    if event == "NEEDS_HUMAN" and state in RECOVERABLE_STATES:
        return "NEEDS_HUMAN"
    if event == "RESOLVED" and state == "BLOCKED":
        return None
    if event == "RESOLVE_BLOCKER" and state == "NEEDS_HUMAN":
        return None
    if state in {"REVIEWING_PROPOSAL", "AUDITING"} and event == "FAIL":
        return None
    if state == "AUDITING" and event == "PASS":
        return None
    return fixed.get((state, event))


def failure_target(state, current):
    counter = "PROPOSAL_FAILURE_COUNT" if current == "REVIEWING_PROPOSAL" else "AUDIT_FAILURE_COUNT"
    count = state.get(counter, state.get("ATTEMPT_COUNT", 0)) + 1
    if count >= 3:
        return count, "NEEDS_HUMAN"
    return count, "REVISING_PROPOSAL" if current == "REVIEWING_PROPOSAL" else "FIXING_IMPLEMENTATION"


def validate_receipt_sequence(receipts):
    if not isinstance(receipts, list):
        raise ValueError("PUBLISH_STEP_RECEIPTS must be a list")
    if len(receipts) > len(PUBLISH_STEPS):
        raise ValueError("too many publish receipts")
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, dict) or receipt.get("STEP") != PUBLISH_STEPS[index]:
            raise ValueError("publish receipt step is out of order")


def validate_receipt_progression(existing, proposed, step):
    validate_receipt_sequence(existing)
    validate_receipt_sequence(proposed)
    if proposed == existing:
        if not existing or existing[-1].get("STEP") != step:
            raise ValueError("publish receipt progression is inconsistent")
        return
    if len(proposed) != len(existing) + 1 or proposed[:-1] != existing:
        raise ValueError("publish receipt progression is inconsistent")
    if step != PUBLISH_STEPS[len(existing)] or proposed[-1].get("STEP") != step:
        raise ValueError("publish receipt step is out of order")


def target_for(state, event, handoff=None):
    current = state.get("STATE")
    if current == "APPLYING" and event in PROPOSAL_CHANGE_EVENTS:
        alias_scope = PROPOSAL_CHANGE_EVENTS[event]
        scope = handoff.get("SCOPE") if handoff else None
        if alias_scope and scope is not None and scope != alias_scope:
            raise ValueError("SCOPE does not match proposal-change event")
        scope = scope or alias_scope
        if scope not in {"WITHIN_APPROVED_SCOPE", "OUTSIDE_APPROVED_SCOPE"}:
            raise ValueError("PROPOSAL_CHANGED requires a valid SCOPE")
        return "REVIEWING_PROPOSAL" if scope == "WITHIN_APPROVED_SCOPE" else "EXPLORING"
    if current == "PUBLISHING" and event == "STEP_PASS":
        if not handoff:
            return None
        return "DONE" if handoff.get("PUBLISH_STEP") == "COMPLETE" else "PUBLISHING"
    target = next_state(current, event)
    if current in {"BLOCKED", "NEEDS_HUMAN"} and event in {"RESOLVED", "RESOLVE_BLOCKER"}:
        return state.get("RESUME_STATE")
    if current in {"REVIEWING_PROPOSAL", "AUDITING"} and event == "FAIL":
        return failure_target(state, current)[1]
    if current == "AUDITING" and event == "PASS":
        return "PUBLISHING" if state.get("PUBLISH_AUTHORIZED") else "READY_TO_PUBLISH"
    return target


def validate_handoff(state, payload, event):
    if not isinstance(payload, dict):
        raise ValueError("handoff must be a JSON object")
    missing = [field for field in HANDOFF_FIELDS if field not in payload]
    if missing:
        raise ValueError("missing handoff fields: %s" % ",".join(missing))
    if payload.get("RUN_ID") != state.get("RUN_ID"):
        raise ValueError("wrong RUN_ID")
    if payload.get("ATTEMPT_ID") != state.get("ATTEMPT_ID"):
        raise ValueError("stale ATTEMPT_ID")
    if payload.get("STATUS") not in VALID_STATUSES:
        raise ValueError("invalid STATUS")
    if event not in EVENT_STATUS or payload.get("STATUS") != EVENT_STATUS[event]:
        raise ValueError("STATUS does not match event")
    current = state.get("STATE")
    expected_owner = OWNER_BY_STATE.get(current)
    if expected_owner is None or payload.get("OWNER") != expected_owner:
        raise ValueError("wrong owner")
    target = target_for(state, event, payload)
    if not target or payload.get("NEXT_STATE") != target:
        raise ValueError("illegal NEXT_STATE")
    for requirement in REQUIRED_BY_STATE.get(current, ()):
        if requirement == "PRE_CHANGE":
            for field in ("CHANGE", "PROPOSAL_DIGEST", "PROGRESS_DIGEST"):
                if state.get("CHANGE"):
                    if payload.get(field) != state.get(field):
                        raise ValueError("mismatched %s during re-exploration" % field)
                elif payload.get(field) is not None:
                    raise ValueError("%s must be null before Change creation" % field)
        elif requirement == "POST_CHANGE":
            for field in ("CHANGE", "PROPOSAL_DIGEST"):
                if not payload.get(field):
                    raise ValueError("missing %s" % field)
        elif requirement == "HUMAN_GATE":
            if not payload.get("APPROVAL_ARTIFACT") or not payload.get("APPROVAL_DIGEST"):
                raise ValueError("missing approval binding")
            if not state.get("APPROVAL_DIGEST") or payload["APPROVAL_DIGEST"] != state["APPROVAL_DIGEST"]:
                raise ValueError("mismatched APPROVAL_DIGEST")
        elif requirement == "APPLY":
            for field in ("BASE_SHA", "HEAD_SHA", "PROGRESS_DIGEST"):
                if not payload.get(field):
                    raise ValueError("missing %s" % field)
        elif requirement == "PUBLISHING":
            step = payload.get("PUBLISH_STEP")
            if step not in PUBLISH_STEPS:
                raise ValueError("invalid PUBLISH_STEP")
            receipts = payload.get("PUBLISH_STEP_RECEIPTS")
            if event == "STEP_PASS":
                if not receipts:
                    raise ValueError("missing PUBLISH_STEP_RECEIPTS")
                validate_receipt_progression(state.get("PUBLISH_STEP_RECEIPTS", []), receipts, step)
                if PUBLISH_STEPS.index(step) >= PUBLISH_STEPS.index("ARCHIVE") and not payload.get("ARCHIVE_DIGEST"):
                    raise ValueError("missing ARCHIVE_DIGEST")
            else:
                persisted_receipts = state.get("PUBLISH_STEP_RECEIPTS", [])
                if receipts != persisted_receipts:
                    raise ValueError("mismatched PUBLISH_STEP_RECEIPTS")
                validate_receipt_sequence(receipts)
                if len(receipts) >= len(PUBLISH_STEPS) or step != PUBLISH_STEPS[len(receipts)]:
                    raise ValueError("inconsistent PUBLISH_STEP")
                archive_index = PUBLISH_STEPS.index("ARCHIVE")
                if len(receipts) > archive_index:
                    archive_digest = payload.get("ARCHIVE_DIGEST")
                    if not archive_digest:
                        raise ValueError("missing ARCHIVE_DIGEST")
                    archived = next((receipt for receipt in receipts if receipt["STEP"] == "ARCHIVE"), None)
                    if archived is not None and archived.get("ARCHIVE_DIGEST") != archive_digest:
                        raise ValueError("mismatched ARCHIVE_DIGEST")
    if current == "EXPLORING" and event == "PASS":
        artifact = payload.get("EXPLORE_ARTIFACT")
        digest = payload.get("EXPLORE_DIGEST")
        if not artifact or not digest or not Path(artifact).is_file() or sha256_file(artifact) != digest:
            raise ValueError("missing or invalid Explore binding")
    output_bindings = OUTPUT_BINDINGS_BY_STATE.get(current, set())
    if current == "APPLYING" and event in PROPOSAL_CHANGE_EVENTS:
        output_bindings = output_bindings | {"PROPOSAL_DIGEST"}
    for field in BINDING_FIELDS:
        if field in output_bindings:
            continue
        if state.get(field) is not None and payload.get(field) is not None and payload.get(field) != state[field]:
            raise ValueError("mismatched %s" % field)
    if current == "AUDITING" and state.get("UNTRACKED_BASELINE") is not None:
        if payload.get("UNTRACKED_BASELINE") != state["UNTRACKED_BASELINE"]:
            raise ValueError("mismatched UNTRACKED_BASELINE")


def validate_handoff_command(args):
    validate_handoff(read_json(args.state), read_json(args.handoff), args.event)
    print(json.dumps({"valid": True}, sort_keys=True))


def normalize_task_checkboxes(content):
    lines = content.decode("utf-8").splitlines(keepends=True)
    normalized = []
    in_fence = False
    for line in lines:
        stripped = line.lstrip(" \t")
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            normalized.append(line)
            continue
        if not in_fence and len(stripped) >= 5 and stripped[0] in "-*+" and stripped[1:3] == " [":
            if stripped[3] in "xX" and stripped[4] == "]" and (len(stripped) == 5 or stripped[5].isspace()):
                prefix = line[:len(line) - len(stripped)]
                normalized.append(prefix + stripped[:3] + " " + stripped[4:])
                continue
        normalized.append(line)
    return "".join(normalized).encode("utf-8")


def digest_bytes(paths, tasks, normalize_tasks):
    resolved = sorted((Path(path).resolve() for path in paths), key=lambda path: str(path))
    common_parent = Path(os.path.commonpath([str(path.parent) for path in resolved]))
    digest = hashlib.sha256()
    for path in resolved:
        content = path.read_bytes()
        if normalize_tasks and path == tasks:
            content = normalize_task_checkboxes(content)
        digest.update(path.relative_to(common_parent).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def digest_command(args):
    if len(args.tasks) != 1:
        raise ValueError("exactly one --tasks is required")
    tasks = Path(args.tasks[0]).resolve()
    inputs = [Path(path).resolve() for path in args.input]
    if tasks in inputs:
        raise ValueError("--tasks must not also be an --input")
    paths = inputs + [tasks]
    print(json.dumps({
        "PROPOSAL_DIGEST": digest_bytes(paths, tasks, True),
        "PROGRESS_DIGEST": hashlib.sha256(tasks.read_bytes()).hexdigest(),
    }, sort_keys=True))


def init_command(args):
    project = Path(args.project).resolve()
    if not project.is_dir():
        raise ValueError("project does not exist")
    run_id = str(uuid.uuid4())
    state_dir = project / ".agents" / "state"
    run_dir = project / ".agents" / "runs" / run_id
    request_path = run_dir / "request.md"
    baseline = git_output(project, "ls-files", "--others", "--exclude-standard").splitlines()
    branch = git_output(project, "branch", "--show-current")
    remotes = git_output(project, "remote").splitlines()
    remote_url = optional_git_output(project, "remote", "get-url", remotes[0]) if remotes else ""
    base_sha = git_output(project, "rev-parse", "HEAD")
    run_dir.mkdir(parents=True, exist_ok=True)
    request_path.write_text(
        "# Request\n\n%s\n\nSource: %s\nProject: %s\nBranch: %s\nRemote: %s\nCreated: %s\nPublish requested: %s\n" % (
            args.request, args.source or "", project, branch, remote_url, now(), bool(args.publish),
        ), encoding="utf-8",
    )
    state_path = state_dir / (run_id + ".json")
    state = {
        "RUN_ID": run_id,
        "STATE": "NEW",
        "ATTEMPT_ID": None,
        "ATTEMPT_COUNT": 0,
        "PROJECT_REALPATH": str(project),
        "BRANCH": branch,
        "REMOTE_URL": remote_url,
        "BASE_SHA": base_sha,
        "UNTRACKED_BASELINE": baseline,
        "REQUEST_ARTIFACT": str(request_path),
        "APPROVAL_ARTIFACT": None,
        "PUBLISH_REQUESTED": bool(args.publish),
        "PUBLISH_AUTHORIZED": False,
        "PUBLISH_STEP_RECEIPTS": [],
        "CREATED_AT": now(),
    }
    atomic_write(state_path, state)
    print(json.dumps({"RUN_ID": run_id, "STATE_PATH": str(state_path)}, sort_keys=True))


def approve_command(args):
    state_path = Path(args.state)
    state = read_json(state_path)
    if state.get("STATE") != "AWAITING_EXPLORE_APPROVAL":
        raise ValueError("approval is only allowed while awaiting Explore approval")
    result_path = Path(args.explore_result)
    if not result_path.is_file():
        raise ValueError("Explore result does not exist")
    result_path = result_path.resolve()
    result_digest = sha256_file(result_path)
    if not state.get("EXPLORE_ARTIFACT") or not state.get("EXPLORE_DIGEST"):
        raise ValueError("accepted Explore binding is required")
    if Path(state["EXPLORE_ARTIFACT"]).resolve() != result_path:
        raise ValueError("Explore result path differs from reviewed artifact")
    if state["EXPLORE_DIGEST"] != result_digest:
        raise ValueError("Explore result digest differs from reviewed artifact")
    approval_path = Path(state["REQUEST_ARTIFACT"]).parent / "approval.json"
    approved = args.decision == "APPROVE"
    approval = {
        "DECISION": args.decision,
        "EXPLORE_DIGEST": state["EXPLORE_DIGEST"],
        "PROJECT_REALPATH": state["PROJECT_REALPATH"],
        "BRANCH": state["BRANCH"],
        "REMOTE_URL": state["REMOTE_URL"],
        "PUBLISH_AUTHORIZED": bool(args.publish_authorized and approved),
        "DECIDED_AT": now(),
    }
    atomic_write(approval_path, approval)
    state["APPROVAL_ARTIFACT"] = str(approval_path)
    state["APPROVAL_DIGEST"] = sha256_file(approval_path)
    state["EXPLORE_DIGEST"] = approval["EXPLORE_DIGEST"]
    state["PUBLISH_AUTHORIZED"] = approval["PUBLISH_AUTHORIZED"]
    atomic_write(state_path, state)
    print(json.dumps(state, sort_keys=True))


def publish_receipt_command(args):
    state_path = Path(args.state)
    state = read_json(state_path)
    if state.get("REMOTE_URL") == "":
        raise ValueError("publishing requires a configured remote")
    payload = read_json(args.handoff)
    proposed = payload.get("PUBLISH_STEP_RECEIPTS") if isinstance(payload, dict) else None
    validate_receipt_sequence(proposed)
    if not proposed or proposed[-1].get("STEP") != args.step:
        raise ValueError("handoff does not contain the current publish receipt")
    receipt = proposed[-1]
    result_path = Path(args.result_file).resolve()
    if not result_path.is_file():
        raise ValueError("result file does not exist")
    result_digest = sha256_file(result_path)
    receipts = state.setdefault("PUBLISH_STEP_RECEIPTS", [])
    validate_receipt_sequence(receipts)
    step = args.step
    existing = next((item for item in receipts if item["STEP"] == step), None)
    if existing:
        if receipt != existing:
            raise ValueError("inconsistent duplicate publish receipt")
        if payload not in state.get("HANDOFFS", []):
            validate_handoff(state, payload, "STEP_PASS")
        if (receipt.get("RESULT_FILE") != str(result_path)
                or receipt.get("RESULT_DIGEST") != result_digest
                or receipt.get("ARCHIVE_DIGEST") != args.archive_digest
                or receipt.get("FINAL_SHA") != args.final_sha):
            raise ValueError("publish receipt does not match result")
        print(json.dumps(state, sort_keys=True))
        return
    if state.get("STATE") != "PUBLISHING":
        raise ValueError("publish receipts require PUBLISHING")
    validate_handoff(state, payload, "STEP_PASS")
    if (receipt.get("RESULT_FILE") != str(result_path)
            or receipt.get("RESULT_DIGEST") != result_digest
            or not isinstance(receipt.get("RECORDED_AT"), str)
            or not receipt["RECORDED_AT"].strip()
            or receipt.get("INPUT_DIGESTS") != {
                "PROPOSAL_DIGEST": state.get("PROPOSAL_DIGEST"),
                "PROGRESS_DIGEST": state.get("PROGRESS_DIGEST"),
            }
            or receipt.get("ARCHIVE_DIGEST") != args.archive_digest
            or receipt.get("FINAL_SHA") != args.final_sha):
        raise ValueError("publish receipt does not match result or state")
    validate_receipt_progression(receipts, receipts + [receipt], step)
    receipts.append(receipt)
    atomic_write(state_path, state)
    print(json.dumps(state, sort_keys=True))


def authorize_publish_command(args):
    state = read_json(args.state)
    if state.get("STATE") != "READY_TO_PUBLISH":
        raise ValueError("publish authorization requires READY_TO_PUBLISH")
    if any(not state.get(field) for field in PUBLISH_AUTHORIZATION_FIELDS):
        raise ValueError("publish authorization requires approval, project, and Audit bindings")
    evidence = Path(args.evidence).resolve()
    if not evidence.is_file():
        raise ValueError("explicit publish authorization evidence is required")
    authorization = {field: state[field] for field in PUBLISH_AUTHORIZATION_FIELDS}
    authorization["EVIDENCE"] = {"PATH": str(evidence), "DIGEST": sha256_file(evidence)}
    authorization["AUTHORIZED_AT"] = now()
    state["PUBLISH_AUTHORIZATION"] = authorization
    state["PUBLISH_AUTHORIZED"] = True
    atomic_write(args.state, state)
    print(json.dumps(state, sort_keys=True))


def dispatch_command(args):
    state = read_json(args.state)
    current = state.get("STATE")
    if current == "PUBLISHING" or OWNER_BY_STATE.get(current) not in SPECIALIST_OWNERS:
        raise ValueError("dispatch requires a normal specialist stage; publishing uses receipts")
    state["ATTEMPT_ID"] = str(uuid.uuid4())
    atomic_write(args.state, state)
    print(json.dumps(state, sort_keys=True))


def validate_publish_authorization(state):
    authorization = state.get("PUBLISH_AUTHORIZATION")
    if not isinstance(authorization, dict):
        raise ValueError("missing publish authorization record")
    for field in PUBLISH_AUTHORIZATION_FIELDS:
        if authorization.get(field) != state.get(field):
            raise ValueError("publish authorization binding changed: %s" % field)


def validate_recovery(state, event, evidence_path):
    if event == "RESOLVED":
        if state.get("STATE") != "BLOCKED":
            raise ValueError("RESOLVED is only valid from BLOCKED")
    elif event == "RESOLVE_BLOCKER":
        if state.get("STATE") != "NEEDS_HUMAN":
            raise ValueError("RESOLVE_BLOCKER is only valid from NEEDS_HUMAN")
    else:
        return None
    if state.get("RESUME_STATE") not in RECOVERABLE_STATES:
        raise ValueError("invalid resume_state")
    if not evidence_path or not Path(evidence_path).is_file():
        raise ValueError("fresh blocker-resolution evidence is required")
    evidence_path = Path(evidence_path).resolve()
    return {"PATH": str(evidence_path), "DIGEST": sha256_file(evidence_path)}


def is_exact_step_pass_replay(state, handoff, event):
    if event != "STEP_PASS" or not isinstance(handoff, dict):
        return False
    if state.get("STATE") not in {"PUBLISHING", "DONE"}:
        return False
    if handoff.get("NEXT_STATE") != state.get("STATE"):
        return False
    if handoff.get("PUBLISH_STEP_RECEIPTS") != state.get("PUBLISH_STEP_RECEIPTS"):
        return False
    return handoff in state.get("HANDOFFS", [])


def transition(args):
    path = Path(args.state)
    state = read_json(path)
    current = state.get("STATE")
    event = args.event
    handoff = read_json(args.handoff) if args.handoff is not None else None
    if args.handoff is not None and is_exact_step_pass_replay(state, handoff, event):
        print(json.dumps(state, sort_keys=True))
        return
    if args.handoff is not None:
        validate_handoff(state, handoff, event)
    recovery = validate_recovery(state, event, args.evidence)
    target = target_for(state, event, handoff)
    if current == "BLOCKED" and event == "RESOLVED":
        target = state.get("RESUME_STATE")
    elif current == "NEEDS_HUMAN" and event == "RESOLVE_BLOCKER":
        target = state.get("RESUME_STATE")
    elif current in {"REVIEWING_PROPOSAL", "AUDITING"} and event == "FAIL":
        counter = "PROPOSAL_FAILURE_COUNT" if current == "REVIEWING_PROPOSAL" else "AUDIT_FAILURE_COUNT"
        count, target = failure_target(state, current)
        state[counter] = count
        state["ATTEMPT_COUNT"] = count
    elif current == "AUDITING" and event == "PASS":
        target = "PUBLISHING" if state.get("PUBLISH_AUTHORIZED") else "READY_TO_PUBLISH"
    if not target:
        raise ValueError("illegal event %s for state %s" % (event, current))
    if current == "READY_TO_PUBLISH" and event == "AUTHORIZE_PUBLISH":
        if not state.get("PUBLISH_AUTHORIZED"):
            raise ValueError("record explicit publish authorization before routing")
        validate_publish_authorization(state)
    if event in {"BLOCKED", "NEEDS_HUMAN"}:
        state["RESUME_STATE"] = current
    if recovery:
        state["RESOLUTION_EVIDENCE"] = recovery
    if args.handoff is not None:
        state.setdefault("HANDOFFS", []).append(handoff)
        for field in BINDING_FIELDS:
            if handoff.get(field) is not None:
                state[field] = handoff[field]
        if current == "PUBLISHING" and event == "STEP_PASS":
            state["PUBLISH_STEP_RECEIPTS"] = handoff["PUBLISH_STEP_RECEIPTS"]
    state["STATE"] = target
    if target == "EXPLORING" and current != "EXPLORING":
        state["APPROVAL_ARTIFACT"] = None
        state["APPROVAL_DIGEST"] = None
        state["PUBLISH_AUTHORIZED"] = False
    if current == "REVIEWING_PROPOSAL" and event == "PASS":
        state["PROPOSAL_FAILURE_COUNT"] = 0
    if current == "APPLYING" and event == "PASS":
        state["AUDIT_FAILURE_COUNT"] = 0
    if OWNER_BY_STATE.get(target) in SPECIALIST_OWNERS:
        state["ATTEMPT_ID"] = str(uuid.uuid4())
    atomic_write(path, state)
    print(json.dumps(state, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    transition_parser = commands.add_parser("transition")
    transition_parser.add_argument("--state", required=True)
    transition_parser.add_argument("--event", required=True)
    transition_parser.add_argument("--handoff")
    transition_parser.add_argument("--evidence")
    transition_parser.set_defaults(handler=transition)
    dispatch_parser = commands.add_parser("dispatch")
    dispatch_parser.add_argument("--state", required=True)
    dispatch_parser.set_defaults(handler=dispatch_command)
    handoff_parser = commands.add_parser("validate-handoff")
    handoff_parser.add_argument("--state", required=True)
    handoff_parser.add_argument("--handoff", required=True)
    handoff_parser.add_argument("--event", required=True)
    handoff_parser.set_defaults(handler=validate_handoff_command)
    digest_parser = commands.add_parser("digest")
    digest_parser.add_argument("--input", action="append", required=True)
    digest_parser.add_argument("--tasks", action="append", required=True)
    digest_parser.set_defaults(handler=digest_command)
    init_parser = commands.add_parser("init")
    init_parser.add_argument("--project", required=True)
    init_parser.add_argument("--request", required=True)
    init_parser.add_argument("--source")
    init_parser.add_argument("--publish", action="store_true")
    init_parser.set_defaults(handler=init_command)
    approval_parser = commands.add_parser("approve")
    approval_parser.add_argument("--state", required=True)
    approval_parser.add_argument("--decision", required=True, choices=("APPROVE", "REVISE", "REJECT"))
    approval_parser.add_argument("--explore-result", required=True)
    approval_parser.add_argument("--publish-authorized", action="store_true")
    approval_parser.set_defaults(handler=approve_command)
    authorization_parser = commands.add_parser("authorize-publish")
    authorization_parser.add_argument("--state", required=True)
    authorization_parser.add_argument("--evidence", required=True)
    authorization_parser.set_defaults(handler=authorize_publish_command)
    receipt_parser = commands.add_parser("publish-receipt")
    receipt_parser.add_argument("--state", required=True)
    receipt_parser.add_argument("--handoff", required=True)
    receipt_parser.add_argument("--step", required=True)
    receipt_parser.add_argument("--result-file", required=True)
    receipt_parser.add_argument("--archive-digest")
    receipt_parser.add_argument("--final-sha")
    receipt_parser.set_defaults(handler=publish_receipt_command)
    args = parser.parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        return fail(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
