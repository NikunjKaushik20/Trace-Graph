from tracegraph.investigation.funding import FundingPath
from tracegraph.investigation.rings import ring_id_for, split_by_label, top_wallet


def test_members_are_split_by_label() -> None:
    members = [
        {"id": "p-2", "labels": ["Provider"]},
        {"id": "root-x", "labels": ["Wallet", "Root"]},
        {"id": "sybil-1", "labels": ["Writer"]},
        {"id": "p-1", "labels": ["Provider"]},
    ]
    assert split_by_label(members) == (["p-1", "p-2"], ["sybil-1"], ["root-x"])


def test_top_wallet_skips_non_wallets() -> None:
    rows = [{"id": "p-1", "score": 0.9}, {"id": "root-x", "score": 0.5}]
    assert top_wallet(rows, ["root-x"]) == "root-x"
    assert top_wallet(rows, []) is None


def test_ring_id_does_not_depend_on_member_order() -> None:
    assert ring_id_for(["a", "b", "c"]) == ring_id_for(["c", "a", "b"])
    assert ring_id_for(["a", "b"]) != ring_id_for(["a", "c"])


def test_funding_path_reports_hops_and_shared_funders() -> None:
    path = FundingPath(
        "sybil-1",
        "p-ring",
        ["sybil-1", "wallet-promo", "root-hub", "wallet-ops", "p-ring"],
        [["Writer"], ["Wallet"], ["Wallet", "Root"], ["Wallet"], ["Provider"]],
    )
    assert path.found
    assert path.hops == 4
    assert path.shared_funders == ["wallet-promo", "root-hub", "wallet-ops"]
    assert not FundingPath("w", "p", [], []).found
