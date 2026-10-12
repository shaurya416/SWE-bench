import json
import re
from argparse import ArgumentParser

from swebench.harness.run_evaluation import _docker_client

"""
Script for removing containers associated with specified instance IDs.
"""

PREFIX = "sweb.eval."


def _matches(name: str, instance_ids: set[str], run_id: str | None) -> bool:
    """Whether a container belongs to the instances and run asked for.

    run_instance names a container sweb.eval.<instance_id, lowercased>.<run_id>, plus
    .<unix time> when a leftover container already held that name. Instance ids and
    run ids can both contain dots (mrdoob__three.js-1, gpt-4.1), so the name is matched
    against what was asked for rather than split at a dot. The suffix is the ten-digit
    time, not any number, so gpt-4 does not also take the containers of a gpt-4.1 run.
    """
    if not name.startswith(PREFIX):
        return False
    rest = name[len(PREFIX) :]
    ids = {iid.lower() for iid in instance_ids}
    if run_id:
        match = re.fullmatch(rf"(.+)\.{re.escape(run_id)}(?:\.\d{{10}})?", rest)
        return bool(match) and (not ids or match.group(1) in ids)
    return any(rest == iid or rest.startswith(f"{iid}.") for iid in ids)


def main(instance_ids=None, predictions_path=None, run_id=None):
    all_ids = set()
    if predictions_path:
        with open(predictions_path, "r") as f:
            predictions = json.loads(f.read())
            for pred in predictions:
                all_ids.add(pred["instance_id"])

    if instance_ids:
        all_ids |= set(instance_ids)

    if not all_ids and not run_id:
        print("Provide --instance_ids, --predictions_path or --run_id, exiting.")
        return

    client = _docker_client()
    removed = 0
    for container in client.containers.list(all=True):
        name = container.name
        if not _matches(name, all_ids, run_id):
            continue
        try:
            container.remove(force=True)
            print(f"Removed container {name}")
            removed += 1
        except Exception as e:
            print(f"Error removing container {name}: {e}")
    print(f"Removed {removed} container(s).")


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument(
        "--instance_ids",
        nargs="+",
        type=str,
        help="Instance IDs to remove containers for",
    )
    parser.add_argument("--predictions_path", type=str, help="Path to predictions file")
    parser.add_argument(
        "--run_id", type=str, help="Only remove containers from this run"
    )
    args = parser.parse_args()
    main(**vars(args))
