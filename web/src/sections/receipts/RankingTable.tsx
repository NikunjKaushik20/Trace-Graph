import type { RankedProvider } from "../../api/types";
import { useNameOf } from "../../graph/names";

interface Props {
  ranked: RankedProvider[];
  chosen: string | null;
}

// TRACE's ranking for one decision: utility as a bar, with its lower confidence bound and risk
export function RankingTable({ ranked, chosen }: Props) {
  const nameOf = useNameOf();
  const ordered = [...ranked].sort((a, b) => a.position - b.position);
  const widest = Math.max(0.01, ...ordered.map((row) => Math.abs(row.utility)));
  return (
    <table className="ranking">
      <caption className="visually-hidden">TRACE ranking</caption>
      <thead>
        <tr>
          <th scope="col">Provider</th>
          <th scope="col">Utility</th>
          <th scope="col" className="is-number">
            Worst case
          </th>
          <th scope="col" className="is-number">
            Risk
          </th>
        </tr>
      </thead>
      <tbody>
        {ordered.map((row) => (
          <tr key={row.provider_id} className={row.provider_id === chosen ? "is-chosen" : ""}>
            <th scope="row">
              <span className="ranking-cell">
                <span className="ranking-position tabular">{row.position}</span>
                <span title={row.provider_id}>{nameOf(row.provider_id)}</span>
                {row.provider_id === chosen && <span className="ranking-chosen">Hired</span>}
              </span>
            </th>
            <td className="ranking-utility">
              <span className="ranking-cell">
                <span className="ranking-bar">
                  <i
                    className={row.utility < 0 ? "is-negative" : ""}
                    style={{ width: `${(Math.abs(row.utility) / widest) * 100}%` }}
                  />
                </span>
                <span className="tabular">{row.utility.toFixed(3)}</span>
              </span>
            </td>
            <td className="is-number tabular">{row.lcb.toFixed(3)}</td>
            <td className="is-number tabular">{row.risk.toFixed(2)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
