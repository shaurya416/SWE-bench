"""`swebench images clean` removes the containers it is asked for.

run_instance names a container sweb.eval.<instance_id, lowercased>.<run_id>, plus
.<unix time> when a leftover container held that name. Splitting that at its last dot
misreads a run id with a dot in it (gpt-4.1) and the retry suffix, and comparing the
lowercased id to the one asked for misses any id with a capital, so the command
reported "Removed 0 container(s)." and left them running.
"""

import pytest

from swebench.harness import remove_containers

NAMES = [
    "sweb.eval.django__django-1234.gpt-4.1",
    "sweb.eval.django__django-12345.gpt-4.1",
    "sweb.eval.django__django-1234.gpt-4",
    "sweb.eval.automattic__wp-calypso-21648.run1",
    "sweb.eval.x__x-1.run1.1760000000",
    "sweb.eval.x__x-1.other",
    "unrelated-container",
]


@pytest.fixture
def removed(monkeypatch):
    gone = []

    class Container:
        def __init__(self, name):
            self.name = name

        def remove(self, force=False):
            gone.append(self.name)

    class Containers:
        def list(self, all=False):
            return [Container(n) for n in NAMES]

    class Client:
        containers = Containers()

    monkeypatch.setattr(remove_containers, "_docker_client", lambda: Client())
    return gone


def test_a_run_id_with_a_dot(removed):
    remove_containers.main(run_id="gpt-4.1")
    assert sorted(removed) == [
        "sweb.eval.django__django-1234.gpt-4.1",
        "sweb.eval.django__django-12345.gpt-4.1",
    ]


def test_a_run_id_does_not_take_a_dotted_sibling_run(removed):
    # gpt-4.1 is another run, not gpt-4 renamed after a conflict
    remove_containers.main(run_id="gpt-4")
    assert removed == ["sweb.eval.django__django-1234.gpt-4"]


def test_a_container_renamed_after_a_name_conflict(removed):
    remove_containers.main(run_id="run1")
    assert sorted(removed) == [
        "sweb.eval.automattic__wp-calypso-21648.run1",
        "sweb.eval.x__x-1.run1.1760000000",
    ]


def test_an_instance_id_with_capitals(removed):
    remove_containers.main(instance_ids=["Automattic__wp-calypso-21648"])
    assert removed == ["sweb.eval.automattic__wp-calypso-21648.run1"]


def test_an_instance_id_is_not_a_prefix_match(removed):
    remove_containers.main(instance_ids=["django__django-1234"], run_id="gpt-4.1")
    assert removed == ["sweb.eval.django__django-1234.gpt-4.1"]


def test_other_runs_are_left_alone(removed):
    remove_containers.main(instance_ids=["x__x-1"], run_id="other")
    assert removed == ["sweb.eval.x__x-1.other"]
