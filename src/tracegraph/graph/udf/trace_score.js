// Lower end of a Wilson interval for a success share out of n trials
function wilsonLowerBound(successes, trials, z) {
  if (trials <= 0) {
    return 0;
  }
  const share = successes / trials;
  const zSquared = z * z;
  const centre = share + zSquared / (2 * trials);
  const margin = z * Math.sqrt((share * (1 - share)) / trials + zSquared / (4 * trials * trials));
  const lower = (centre - margin) / (1 + zSquared / trials);
  return Math.min(1, Math.max(0, lower));
}

// TRACE's Bayesian LCB: completion rate under a Beta(1,3) prior, 95% lower bound
function bayesianLcb(successes, failures, settings) {
  const alpha = successes + settings.prior_successes;
  const beta = failures + settings.prior_failures;
  return wilsonLowerBound(alpha, alpha + beta, settings.lcb_z);
}

// Exponentially smoothed default probability over outcomes in time order
function smoothedDefaultRate(outcomes, settings) {
  let rate = 0;
  for (const succeeded of outcomes) {
    const failed = succeeded ? 0 : 1;
    rate = (1 - settings.risk_smoothing) * rate + settings.risk_smoothing * failed;
  }
  return rate;
}

// CUSUM statistic that grows on failures and shrinks on successes
function cusumStatistic(outcomes, settings) {
  let statistic = 0;
  for (const succeeded of outcomes) {
    const failed = succeeded ? 0 : 1;
    statistic = Math.max(0, statistic + failed - (1 - settings.cusum_reference));
  }
  return statistic;
}

// Reason a provider is excluded before ranking, or null if it may be picked
function exclusionReason(provider, outcomes, settings) {
  if (provider.quarantined) {
    return "quarantined";
  }
  if (cusumStatistic(outcomes, settings) > settings.cusum_threshold) {
    return "cusum_alarm";
  }
  const successes = outcomes.filter((succeeded) => succeeded).length;
  const failures = outcomes.length - successes;
  const failureBound = wilsonLowerBound(failures, successes + failures, settings.failure_bound_z);
  if (failureBound > settings.honest_failure_rate) {
    return "fails_more_than_honest";
  }
  return null;
}

// Personalized PageRank over writer-provider success edges, restarting at the seed writers
function personalizedPagerank(successEdges, seedWriters, settings) {
  const neighbours = new Map();
  for (const [writer, provider] of successEdges) {
    addNeighbour(neighbours, writer, provider);
    addNeighbour(neighbours, provider, writer);
  }
  const seeds = seedWriters.filter((writer) => neighbours.has(writer));
  const rank = new Map();
  if (seeds.length === 0) {
    return rank;
  }
  const restart = new Map();
  for (const node of neighbours.keys()) {
    restart.set(node, seeds.includes(node) ? 1 / seeds.length : 0);
    rank.set(node, restart.get(node));
  }
  for (let step = 0; step < settings.ppr_iterations; step++) {
    const spread = new Map([...neighbours.keys()].map((node) => [node, 0]));
    for (const [node, nodeRank] of rank) {
      const links = neighbours.get(node);
      for (const neighbour of links) {
        spread.set(neighbour, spread.get(neighbour) + nodeRank / links.length);
      }
    }
    for (const node of neighbours.keys()) {
      const restarted = settings.ppr_restart * restart.get(node);
      rank.set(node, restarted + (1 - settings.ppr_restart) * spread.get(node));
    }
  }
  return rank;
}

// Appends one entry to a node's adjacency list
function addNeighbour(neighbours, node, neighbour) {
  if (!neighbours.has(node)) {
    neighbours.set(node, []);
  }
  neighbours.get(node).push(neighbour);
}

// Shannon entropy of who reported a provider's successes, scaled to 0..1 by the seed count
function counterpartyEntropy(successCountsByWriter, seedCount) {
  const counts = Object.values(successCountsByWriter);
  const total = counts.reduce((sum, count) => sum + count, 0);
  if (total === 0 || seedCount < 2) {
    return 0;
  }
  let entropy = 0;
  for (const count of counts) {
    if (count > 0) {
      const share = count / total;
      entropy -= share * Math.log2(share);
    }
  }
  return Math.min(1, entropy / Math.log2(seedCount));
}

// Edge-to-job Sybil signal: the share of a provider's reports not backed by a paid job
function sybilRatio(reportsReceived, paidJobs) {
  if (reportsReceived === 0) {
    return 0;
  }
  return 1 - Math.min(1, paidJobs / reportsReceived);
}

// Clique signal: share of reviewer pairs that share a funder, or 1 if tied to a quarantined ring
function cliqueScore(reviewerFunders, contaminated) {
  if (contaminated) {
    return 1;
  }
  const funderSets = Object.values(reviewerFunders);
  let pairs = 0;
  let coordinated = 0;
  for (let first = 0; first < funderSets.length; first++) {
    for (let second = first + 1; second < funderSets.length; second++) {
      pairs += 1;
      if (funderSets[first].some((funder) => funderSets[second].includes(funder))) {
        coordinated += 1;
      }
    }
  }
  return pairs ? coordinated / pairs : 0;
}

// Orders reports by time, then writer, then job, so both scorers see the same sequence
function compareReports(first, second) {
  if (first.t !== second.t) {
    return first.t - second.t;
  }
  if (first.writer_id !== second.writer_id) {
    return first.writer_id < second.writer_id ? -1 : 1;
  }
  const firstJob = first.job_id || "";
  const secondJob = second.job_id || "";
  if (firstJob === secondJob) {
    return 0;
  }
  return firstJob < secondJob ? -1 : 1;
}

// True when the write guard let this report count
function isCounted(report) {
  return report.ignored_because === null || report.ignored_because === undefined;
}

// Groups sorted guarded reports, activity and reviewer funders into one record per provider
function assembleEvidence(sortedReports, providers, reviewerFunders) {
  const evidence = new Map();
  for (const provider of providers) {
    evidence.set(provider.provider_id, {
      provider,
      outcomes: [],
      successCountsByWriter: {},
      reviewerFunders: {},
      ignoredClaims: 0,
    });
  }
  for (const report of sortedReports) {
    const record = evidence.get(report.provider_id);
    if (record === undefined) {
      continue;
    }
    if (!isCounted(report)) {
      record.ignoredClaims += 1;
      continue;
    }
    record.outcomes.push(report.ok);
    if (report.ok) {
      const counts = record.successCountsByWriter;
      counts[report.writer_id] = (counts[report.writer_id] || 0) + 1;
    }
  }
  for (const row of reviewerFunders) {
    const record = evidence.get(row.provider_id);
    if (record !== undefined && row.writer_id !== null) {
      record.reviewerFunders[row.writer_id] = row.funders || [];
    }
  }
  return evidence;
}

// Scores one provider with TRACE's seven-term utility from its counted evidence
function scoreProvider(record, pprDistance, seedCount, settings) {
  const weights = settings.weights;
  const provider = record.provider;
  const successes = record.outcomes.filter((succeeded) => succeeded).length;
  const failures = record.outcomes.length - successes;
  const lcb = bayesianLcb(successes, failures, settings);
  const risk = smoothedDefaultRate(record.outcomes, settings);
  const entropy = counterpartyEntropy(record.successCountsByWriter, seedCount);
  const capability = 1;
  const sybil = sybilRatio(provider.reports_received, provider.paid_jobs);
  const clique = cliqueScore(record.reviewerFunders, provider.contaminated);
  const utility =
    weights.trace * lcb -
    weights.risk * risk -
    weights.ppr_distance * pprDistance +
    weights.entropy * entropy +
    weights.capability * capability -
    weights.sybil * sybil -
    weights.clique * clique;
  return {
    provider_id: provider.provider_id,
    utility,
    lcb,
    risk,
    ppr_distance: pprDistance,
    entropy,
    capability,
    sybil,
    clique,
    cusum: cusumStatistic(record.outcomes, settings),
    successes,
    failures,
    ignored_claims: record.ignoredClaims,
    excluded_because: exclusionReason(provider, record.outcomes, settings),
  };
}

// Runs TRACE on every candidate: guard results in, one score per provider out
function scoreCandidates(providers, reports, reviewerFunders, seedWriters, settings) {
  const sortedReports = [...reports].sort(compareReports);
  const evidence = assembleEvidence(sortedReports, providers, reviewerFunders);
  const successEdges = sortedReports
    .filter((report) => report.ok && isCounted(report))
    .map((report) => [report.writer_id, report.provider_id]);
  const rank = personalizedPagerank(successEdges, seedWriters, settings);
  let best = 0;
  for (const providerId of evidence.keys()) {
    best = Math.max(best, rank.get(providerId) || 0);
  }
  const scores = [];
  for (const [providerId, record] of evidence) {
    const distance = best > 0 ? 1 - (rank.get(providerId) || 0) / best : 1;
    scores.push(scoreProvider(record, distance, seedWriters.length, settings));
  }
  return scores;
}

falkor.register("scoreCandidates", scoreCandidates);
