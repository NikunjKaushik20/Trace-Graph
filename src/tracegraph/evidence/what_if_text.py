from tracegraph.evidence.what_if import ProviderShift, WhatIf

GUARD_WORDS = {
    "closed": "With only the fleet's own reports counted",
    "open": "With outside reports counted unless the money links them",
    "unguarded": "With the guard off",
}


# The what-if in plain words: whether the pick changes, who moves most, and what came after
def what_if_sentence(result: WhatIf) -> str:
    setting = GUARD_WORDS.get(result.guard_tried, f"With guard mode {result.guard_tried}")
    if result.changed:
        lead = (
            f"{setting}, TRACE would have ranked {result.top_tried or 'nobody'} first "
            f"instead of {result.top_used or 'nobody'}."
        )
    else:
        lead = (
            f"{setting}, TRACE would still rank {result.top_used or 'nobody'} first, "
            "so the guard did not change this pick."
        )
    parts = [lead]
    mover = biggest_gain(result.shifts)
    if mover is not None:
        parts.append(shift_sentence(mover))
        parts.extend(since_sentences(mover))
    if not result.replay_matches_record:
        parts.append(
            "Replaying the guard that was used did not give back the stored ranking exactly, "
            "so read this as approximate."
        )
    return " ".join(parts)


# The provider that gains most from the reports the other guard would count
def biggest_gain(shifts: list[ProviderShift]) -> ProviderShift | None:
    gainers = [shift for shift in shifts if shift.reports_counted_now > 0]
    return max(gainers, key=lambda s: s.utility_after - s.utility_before, default=None)


# How many more reports one provider would count, from whom, and how its score moves
def shift_sentence(shift: ProviderShift) -> str:
    if shift.shared_funders:
        source = f"from writers that share funders with it ({', '.join(shift.shared_funders)})"
    else:
        source = "from writers outside the fleet"
    return (
        f"{shift.provider_id} would count {shift.reports_counted_now} more reports {source}, "
        f"moving its score from {shift.utility_before:.2f} to {shift.utility_after:.2f}."
    )


# What the graph recorded about a provider after the decision
def since_sentences(shift: ProviderShift) -> list[str]:
    sentences = []
    if shift.policies_since:
        sentences.append(f"It has since been quarantined ({', '.join(shift.policies_since)}).")
    paid = shift.released_since + shift.failed_since
    if shift.failed_since:
        sentences.append(f"Since then, {shift.failed_since} of its {paid} paid jobs failed.")
    return sentences
