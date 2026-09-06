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
SPECIALIST_OWNERS = {
    "Explore / Proposal", "Proposal Reviewer", "Apply Executor", "Pre-Archive Auditor", "Archivist / Publisher",
}


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
    if event == "RESOLVED" and state == "BLOCKED":
        return None
    if event == "RESOLVE_BLOCKER" and state == "NEEDS_HUMAN":
        return None
    if state in {"REVIEWING_PROPOSAL", "AUDITING"} and event == "FAIL":
        return None
    if state == "AUDITING" and event == "PASS":
        return None
    return fixed.get((state, event))


def target_for(state, event):
    current = state.get("STATE")
    target = next_state(current, event)
    if current in {"BLOCKED", "NEEDS_HUMAN"} and event in {"RESOLVED", "RESOLVE_BLOCKER"}:
        return state.get("RESUME_STATE")
    if current in {"REVIEWING_PROPOSAL", "AUDITING"} and event == "FAIL":
        count = state.get("ATTEMPT_COUNT", 0) + 1
        if count >= 3:
            return "NEEDS_HUMAN"
        return "REVISING_PROPOSAL" if current == "REVIEWING_PROPOSAL" else "FIXING_IMPLEMENTATION"
    if current == "AUDITING" and event == "PASS":
        return "PUBLISHING" if state.get("PUBLISH_AUTHORIZED") else "READY_TO_PUBLISH"
    return target


def validate_handoff(state, payload, event):
    missing = [field for field in HANDOFF_FIELDS if field not in payload]
    if missing:
        raise ValueError("missing handoff fields: %s" % ",".join(missing))
    if payload.get("RUN_ID") != state.get("RUN_ID"):
        raise ValueError("wrong RUN_ID")
    if payload.get("ATTEMPT_ID") != state.get("ATTEMPT_ID"):
        raise ValueError("stale ATTEMPT_ID")
    if payload.get("STATUS") not in VALID_STATUSES:
        raise ValueError("invalid STATUS")
    current = state.get("STATE")
    expected_owner = OWNER_BY_STATE.get(current)
    if expected_owner is None or payload.get("OWNER") != expected_owner:
        raise ValueError("wrong owner")
    target = target_for(state, event)
    if not target or payload.get("NEXT_STATE") != target:
        raise ValueError("illegal NEXT_STATE")
    for requirement in REQUIRED_BY_STATE.get(current, ()):
        if requirement == "PRE_CHANGE":
            for field in ("CHANGE", "PROPOSAL_DIGEST", "PROGRESS_DIGEST"):
                if payload.get(field) is not None:
                    raise ValueError("%s must be null before Change creation" % field)
        elif requirement == "POST_CHANGE":
            for field in ("CHANGE", "PROPOSAL_DIGEST"):
                if not payload.get(field):
                    raise ValueError("missing %s" % field)
        elif requirement == "HUMAN_GATE":
            if not payload.get("APPROVAL_ARTIFACT"):
                raise ValueError("missing approval binding")
        elif requirement == "APPLY":
            for field in ("BASE_SHA", "HEAD_SHA", "PROGRESS_DIGEST"):
                if not payload.get(field):
                    raise ValueError("missing %s" % field)
        elif requirement == "PUBLISHING":
            for field in ("PUBLISH_STEP", "ARCHIVE_DIGEST"):
                if not payload.get(field):
                    raise ValueError("missing %s" % field)
            if not payload.get("PUBLISH_STEP_RECEIPTS"):
                raise ValueError("missing PUBLISH_STEP_RECEIPTS")


def validate_handoff_command(args):
    validate_handoff(read_json(args.state), read_json(args.handoff), args.event)
    print(json.dumps({"valid": True}, sort_keys=True))


def digest_bytes(paths, tasks, normalize_tasks):
    resolved = sorted((Path(path).resolve() for path in paths), key=lambda path: str(path))
    common_parent = Path(os.path.commonpath([str(path.parent) for path in resolved]))
    digest = hashlib.sha256()
    for path in resolved:
        content = path.read_bytes()
        if normalize_tasks and path == tasks:
            content = content.replace(b"- [x]", b"- [ ]").replace(b"- [X]", b"- [ ]")
        digest.update(path.relative_to(common_parent).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def digest_command(args):
    tasks = Path(args.tasks).resolve()
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
    remote_url = git_output(project, "remote", "get-url", "origin")
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
    approval_path = Path(state["REQUEST_ARTIFACT"]).parent / "approval.json"
    approved = args.decision == "APPROVE"
    approval = {
        "DECISION": args.decision,
        "EXPLORE_DIGEST": sha256_file(result_path),
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
    result_path = Path(args.result_file).resolve()
    if not result_path.is_file():
        raise ValueError("result file does not exist")
    result_digest = sha256_file(result_path)
    receipts = state.setdefault("PUBLISH_STEP_RECEIPTS", [])
    step = args.step
    existing = next((item for item in receipts if item["STEP"] == step), None)
    if existing:
        same = (
            existing["RESULT_FILE"] == str(result_path)
            and existing["RESULT_DIGEST"] == result_digest
            and existing.get("ARCHIVE_DIGEST") == args.archive_digest
            and existing.get("FINAL_SHA") == args.final_sha
        )
        if not same:
            raise ValueError("inconsistent duplicate publish receipt")
        atomic_write(state_path, state)
        print(json.dumps(state, sort_keys=True))
        return
    if state.get("STATE") != "PUBLISHING":
        raise ValueError("publish receipts require PUBLISHING")
    if step not in PUBLISH_STEPS or len(receipts) >= len(PUBLISH_STEPS) or step != PUBLISH_STEPS[len(receipts)]:
        raise ValueError("publish receipt step is out of order")
    receipt = {
        "STEP": step,
        "RESULT_FILE": str(result_path),
        "RESULT_DIGEST": result_digest,
        "RECORDED_AT": now(),
        "INPUT_DIGESTS": {
            "PROPOSAL_DIGEST": state.get("PROPOSAL_DIGEST"),
            "PROGRESS_DIGEST": state.get("PROGRESS_DIGEST"),
        },
    }
    if args.archive_digest:
        receipt["ARCHIVE_DIGEST"] = args.archive_digest
    if args.final_sha:
        receipt["FINAL_SHA"] = args.final_sha
    receipts.append(receipt)
    if step == "COMPLETE":
        state["STATE"] = "DONE"
    atomic_write(state_path, state)
    print(json.dumps(state, sort_keys=True))


def transition(args):
    path = Path(args.state)
    state = read_json(path)
    current = state.get("STATE")
    event = args.event
    handoff = read_json(args.handoff) if args.handoff else None
    if handoff:
        validate_handoff(state, handoff, event)
    target = target_for(state, event)
    if current == "BLOCKED" and event == "RESOLVED":
        target = state.get("RESUME_STATE")
    elif current == "NEEDS_HUMAN" and event == "RESOLVE_BLOCKER":
        target = state.get("RESUME_STATE")
    elif current in {"REVIEWING_PROPOSAL", "AUDITING"} and event == "FAIL":
        count = state.get("ATTEMPT_COUNT", 0) + 1
        state["ATTEMPT_COUNT"] = count
        target = "NEEDS_HUMAN" if count >= 3 else (
            "REVISING_PROPOSAL" if current == "REVIEWING_PROPOSAL" else "FIXING_IMPLEMENTATION"
        )
    elif current == "AUDITING" and event == "PASS":
        target = "PUBLISHING" if state.get("PUBLISH_AUTHORIZED") else "READY_TO_PUBLISH"
    if not target:
        raise ValueError("illegal event %s for state %s" % (event, current))
    if event == "BLOCKED":
        state["RESUME_STATE"] = current
    if handoff:
        state.setdefault("HANDOFFS", []).append(handoff)
    state["STATE"] = target
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
    transition_parser.set_defaults(handler=transition)
    handoff_parser = commands.add_parser("validate-handoff")
    handoff_parser.add_argument("--state", required=True)
    handoff_parser.add_argument("--handoff", required=True)
    handoff_parser.add_argument("--event", required=True)
    handoff_parser.set_defaults(handler=validate_handoff_command)
    digest_parser = commands.add_parser("digest")
    digest_parser.add_argument("--input", action="append", required=True)
    digest_parser.add_argument("--tasks", required=True)
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
    receipt_parser = commands.add_parser("publish-receipt")
    receipt_parser.add_argument("--state", required=True)
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
