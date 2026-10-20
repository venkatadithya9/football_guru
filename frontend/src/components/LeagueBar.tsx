import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Zap, ShieldCheck, Trophy, Sparkles } from 'lucide-react';

interface LeagueItem {
  id: number;
  key: string;
  name: string;
  country: string;
  flag: string;
  logo: string;
}

interface ClubItem {
  id: number;
  name: string;
  logo: string;
  league: string;
}

const DEFAULT_LEAGUES: LeagueItem[] = [
  {
    id: 39,
    key: 'pl',
    name: 'Premier League',
    country: 'England',
    flag: 'https://media.api-sports.io/flags/gb.svg',
    logo: 'https://media.api-sports.io/football/leagues/39.png',
  },
  {
    id: 140,
    key: 'laliga',
    name: 'La Liga',
    country: 'Spain',
    flag: 'https://media.api-sports.io/flags/es.svg',
    logo: 'https://media.api-sports.io/football/leagues/140.png',
  },
  {
    id: 78,
    key: 'bundesliga',
    name: 'Bundesliga',
    country: 'Germany',
    flag: 'https://media.api-sports.io/flags/de.svg',
    logo: 'https://media.api-sports.io/football/leagues/78.png',
  },
  {
    id: 135,
    key: 'serie_a',
    name: 'Serie A',
    country: 'Italy',
    flag: 'https://media.api-sports.io/flags/it.svg',
    logo: 'https://media.api-sports.io/football/leagues/135.png',
  },
  {
    id: 61,
    key: 'ligue1',
    name: 'Ligue 1',
    country: 'France',
    flag: 'https://media.api-sports.io/flags/fr.svg',
    logo: 'https://media.api-sports.io/football/leagues/61.png',
  },
];

const FEATURED_CLUBS: ClubItem[] = [
  { id: 42, name: 'Arsenal', logo: 'https://media.api-sports.io/football/teams/42.png', league: 'pl' },
  { id: 541, name: 'Real Madrid', logo: 'https://media.api-sports.io/football/teams/541.png', league: 'laliga' },
  { id: 529, name: 'Barcelona', logo: 'https://media.api-sports.io/football/teams/529.png', league: 'laliga' },
  { id: 50, name: 'Man City', logo: 'https://media.api-sports.io/football/teams/50.png', league: 'pl' },
  { id: 157, name: 'Bayern Munich', logo: 'https://media.api-sports.io/football/teams/157.png', league: 'bundesliga' },
  { id: 505, name: 'Inter', logo: 'https://media.api-sports.io/football/teams/505.png', league: 'serie_a' },
  { id: 85, name: 'PSG', logo: 'https://media.api-sports.io/football/teams/85.png', league: 'ligue1' },
];

interface LeagueBarProps {
  onSelectPrompt: (prompt: string) => void;
  disabled: boolean;
}

export const LeagueBar: React.FC<LeagueBarProps> = ({ onSelectPrompt, disabled }) => {
  const [leagues, setLeagues] = useState<LeagueItem[]>(DEFAULT_LEAGUES);

  useEffect(() => {
    // Optionally fetch dynamic leagues & clubs from API
    fetch('/api/leagues')
      .then(res => res.json())
      .then(data => {
        if (data.leagues && data.leagues.length > 0) {
          setLeagues(data.leagues);
        }
      })
      .catch(() => {
        // Fall back to DEFAULT_LEAGUES
      });
  }, []);

  return (
    <div className="w-full py-2.5 overflow-x-auto no-scrollbar border-b border-pitch-border/50 bg-turf-950/60 backdrop-blur-sm">
      <div className="flex items-center gap-2 min-w-max px-4 sm:px-6">
        {/* League Badges */}
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5 mr-1 select-none">
          <Trophy className="w-3.5 h-3.5 text-golden" />
          <span className="hidden sm:inline">Top Leagues:</span>
        </span>

        {leagues.map(l => (
          <motion.button
            key={l.key}
            whileHover={{ scale: disabled ? 1 : 1.05 }}
            whileTap={{ scale: disabled ? 1 : 0.95 }}
            disabled={disabled}
            onClick={() => onSelectPrompt(`Show me the ${l.name} 2024 standings table, top teams, and key stats.`)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-turf-850/90 hover:bg-turf-800 border border-slate-700/60 hover:border-pitch-green/50 text-slate-200 hover:text-white transition-all shadow-sm group disabled:opacity-40 disabled:cursor-not-allowed"
            title={`View ${l.name} standings`}
          >
            <img
              src={l.logo}
              alt={l.name}
              className="w-4 h-4 object-contain group-hover:scale-110 transition-transform"
              onError={(e) => {
                // Fallback to flag if league badge fails
                (e.target as HTMLElement).style.display = 'none';
              }}
            />
            {l.flag && (
              <img
                src={l.flag}
                alt={l.country}
                className="w-3.5 h-2.5 object-cover rounded-xs border border-white/20"
              />
            )}
            <span>{l.name}</span>
          </motion.button>
        ))}

        <div className="h-4 w-px bg-slate-700/60 mx-1" />

        {/* Featured Club Crests */}
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1 mr-1 select-none">
          <Sparkles className="w-3.5 h-3.5 text-pitch-light" />
          <span className="hidden md:inline">Clubs:</span>
        </span>

        {FEATURED_CLUBS.map(club => (
          <motion.button
            key={club.id}
            whileHover={{ scale: disabled ? 1 : 1.08 }}
            whileTap={{ scale: disabled ? 1 : 0.95 }}
            disabled={disabled}
            onClick={() => onSelectPrompt(`Give me a detailed tactical analysis and season stats for ${club.name} in 2024.`)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-turf-850/70 hover:bg-turf-800 border border-slate-700/50 hover:border-pitch-green/40 text-slate-200 hover:text-white transition-all shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
            title={`Analyze ${club.name}`}
          >
            <img
              src={club.logo}
              alt={club.name}
              className="w-4 h-4 object-contain"
              loading="lazy"
            />
            <span>{club.name}</span>
          </motion.button>
        ))}

        <div className="h-4 w-px bg-slate-700/60 mx-1" />

        {/* Live Match Pulse */}
        <motion.button
          whileHover={{ scale: disabled ? 1 : 1.05 }}
          whileTap={{ scale: disabled ? 1 : 0.95 }}
          disabled={disabled}
          onClick={() => onSelectPrompt('Are there any live matches currently in play across the top 5 leagues?')}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-950/40 hover:bg-amber-900/60 border border-amber-500/40 text-amber-200 transition-all shadow-sm shadow-amber-500/10 disabled:opacity-40 disabled:cursor-not-allowed"
          title="Scan live matches"
        >
          <Zap className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
          <span>Live Scores</span>
        </motion.button>
      </div>
    </div>
  );
};
