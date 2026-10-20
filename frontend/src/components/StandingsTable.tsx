import React from 'react';

interface StandingsTableProps {
  children?: React.ReactNode;
}

export const StandingsTable: React.FC<StandingsTableProps> = ({ children }) => {
  return (
    <div className="w-full my-3 overflow-x-auto rounded-xl border border-slate-800 bg-turf-900/90 shadow-md">
      <table className="w-full text-left text-xs border-collapse">
        {children}
      </table>
    </div>
  );
};

export const FormPill: React.FC<{ form: string }> = ({ form }) => {
  if (!form) return null;
  const chars = form.toUpperCase().split('');
  return (
    <div className="flex items-center gap-1">
      {chars.map((c, i) => {
        let bg = 'bg-slate-700 text-slate-300';
        if (c === 'W') bg = 'bg-emerald-600 text-white font-bold';
        else if (c === 'D') bg = 'bg-amber-600 text-white font-bold';
        else if (c === 'L') bg = 'bg-rose-600 text-white font-bold';
        return (
          <span
            key={i}
            className={`w-4 h-4 flex items-center justify-center rounded-xs text-[10px] ${bg}`}
          >
            {c}
          </span>
        );
      })}
    </div>
  );
};
