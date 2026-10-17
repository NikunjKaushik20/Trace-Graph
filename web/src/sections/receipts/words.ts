const PHRASES: Record<string, string> = {
  writer_not_admitted: "written by reviewers outside the fleet",
  shares_funding_with_provider: "written by reviewers paid from the provider's own wallets",
  fails_more_than_honest: "fails more often than an honest provider would",
  quarantined: "quarantined by a fleet policy",
  new_provider: "new provider",
  reports_from_uncounted_writers: "praise from writers the guard does not count",
  reviewers_share_funding: "reviewers share funders with the provider",
  close_call: "the top two are too close to call",
};

// A reason or flag code in plain words
export function inWords(code: string): string {
  return PHRASES[code] ?? code.replaceAll("_", " ");
}

// A flag like "prov-x: new_provider" split into the provider and the plain-word reason
export function flagInWords(flag: string): { providerId: string; reason: string } {
  const [providerId, code] = flag.includes(": ") ? flag.split(": ") : ["", flag];
  return { providerId, reason: inWords(code) };
}
