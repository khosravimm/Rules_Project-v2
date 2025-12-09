import { PatternMeta } from "../../types/domain";
import { useAppStore } from "../../store/useAppStore";

type Props = {
  patterns: PatternMeta[];
};

const PatternListTable = ({ patterns }: Props) => {
  const setSelectedPatternId = useAppStore((s) => s.setSelectedPatternId);
  return (
    <div className="glass-panel p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="section-title">Pattern KB</p>
        <p className="text-slate-300 text-sm">{patterns.length} patterns</p>
      </div>
      <div className="max-h-80 overflow-y-auto pr-2">
        <table className="w-full text-sm text-slate-100">
          <thead className="text-slate-300">
            <tr>
              <th className="text-left pb-2">ID</th>
              <th className="text-left pb-2">Type</th>
              <th className="text-left pb-2">Strength</th>
              <th className="text-left pb-2">Status</th>
            </tr>
          </thead>
          <tbody>
            {patterns.map((p) => (
              <tr
                key={p.pattern_id}
                className="hover:bg-white/5 cursor-pointer"
                onClick={() => setSelectedPatternId(p.pattern_id)}
              >
                <td className="py-1">{p.pattern_id}</td>
                <td className="py-1">{p.pattern_type}</td>
                <td className="py-1">{p.strength_level}</td>
                <td className="py-1">{p.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default PatternListTable;
