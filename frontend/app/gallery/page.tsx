'use client';

import Link from "next/link";
import { useState, useEffect, useCallback } from "react";
import { toast } from 'sonner';
import { safeDate } from '@/lib/utils';

interface ModelCard {
  token_id: number;
  current_status: string;
  created_at: string;
  model_name?: string;
  version?: string;
  developer_organization?: string;
  description?: string;
  metadata?: any;
  superseded_by?: number;
  supersedes?: number;
  relevance_score?: number;
  match_fields?: string[];
  challenges?: { total: number; open: number; split: number; resolved: number };
}

interface VersionInfo {
  version_number: number;
  version: string;
  previous_version?: string;
  timestamp: string;
  metadata_uri?: string;
  notes?: string;
}

interface SyncReport {
  total: number;
  in_sync: number;
  out_of_sync: number;
  check_failed: number;
  discrepancies: Array<{ token_id: number; chain_status: string; neo4j_status: string }> | null;
}

export default function GalleryPage() {
  const [modelCards, setModelCards] = useState<ModelCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<ModelCard[] | null>(null);
  const [searchDebounceTimer, setSearchDebounceTimer] = useState<NodeJS.Timeout | null>(null);

  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [selectedTokenId, setSelectedTokenId] = useState<number | null>(null);
  const [versionHistory, setVersionHistory] = useState<VersionInfo[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);

  const [showComparison, setShowComparison] = useState(false);
  const [selectedVersions, setSelectedVersions] = useState<number[]>([]);
  const [comparisonData, setComparisonData] = useState<any>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);

  const [syncing, setSyncing] = useState(false);
  const [showSyncReport, setShowSyncReport] = useState(false);
  const [syncReport, setSyncReport] = useState<SyncReport | null>(null);

  const [showVersionChain, setShowVersionChain] = useState(false);
  const [versionChainData, setVersionChainData] = useState<any>(null);
  const [loadingVersionChain, setLoadingVersionChain] = useState(false);

  useEffect(() => {
    fetchModelCards();
  }, [filter]);

  const fetchModelCards = async () => {
    setLoading(true);
    try {
      const url = filter === "all"
        ? 'http://localhost:8000/api/model-cards'
        : `http://localhost:8000/api/model-cards?status=${filter}`;

      const response = await fetch(url);
      const data = await response.json();

      const cards = data.model_cards?.map((item: any) => {
        const mc = item.mc || item;
        return {
          token_id: mc.token_id,
          current_status: mc.current_status || "Unknown",
          created_at: mc.created_at,
          model_name: mc.model_name,
          version: mc.version || "1.0.0",
          developer_organization: mc.developer_organization,
          description: mc.description,
          metadata: mc,
          challenges: mc.challenges,
        };
      }) || [];

      setModelCards(cards);
    } catch (error) {
      console.error('Error fetching model cards:', error);
      setModelCards([]);
    } finally {
      setLoading(false);
    }
  };

  const performSearch = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchResults(null);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    try {
      const response = await fetch('http://localhost:8000/api/model-cards/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: query.trim(),
          status: filter !== 'all' ? filter : null,
          limit: 50
        })
      });

      if (!response.ok) throw new Error('Search failed');

      const data = await response.json();
      setSearchResults(data.results || []);
    } catch (error) {
      console.error('Search error:', error);
      toast.error('Search failed. Please try again.');
      setSearchResults(null);
    } finally {
      setIsSearching(false);
    }
  }, [filter]);

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);

    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
    }

    if (value.trim()) {
      const timer = setTimeout(() => {
        performSearch(value);
      }, 300);
      setSearchDebounceTimer(timer);
    } else {
      setSearchResults(null);
    }
  };

  const clearSearch = () => {
    setSearchQuery("");
    setSearchResults(null);
    if (searchDebounceTimer) {
      clearTimeout(searchDebounceTimer);
    }
  };

  const displayCards = searchResults !== null ? searchResults : modelCards;

  const fetchVersionHistory = async (tokenId: number) => {
    setLoadingVersions(true);
    try {
      const response = await fetch(`http://localhost:8000/api/model-cards/${tokenId}/versions`);
      const data = await response.json();
      setVersionHistory(data.versions || []);
      setSelectedTokenId(tokenId);
      setShowVersionHistory(true);
      setSelectedVersions([]);
    } catch (error) {
      console.error('Error fetching version history:', error);
      setVersionHistory([]);
    } finally {
      setLoadingVersions(false);
    }
  };

  const handleVersionSelect = (index: number) => {
    if (selectedVersions.includes(index)) {
      setSelectedVersions(selectedVersions.filter(v => v !== index));
    } else if (selectedVersions.length < 2) {
      setSelectedVersions([...selectedVersions, index]);
    }
  };

  const compareVersions = async () => {
    if (selectedVersions.length !== 2 || !selectedTokenId) return;

    setLoadingComparison(true);
    try {
      const version1 = versionHistory[selectedVersions[0]];
      const version2 = versionHistory[selectedVersions[1]];

      setComparisonData({
        version1,
        version2
      });
      setShowComparison(true);
      setShowVersionHistory(false);
    } catch (error) {
      console.error('Error comparing versions:', error);
    } finally {
      setLoadingComparison(false);
    }
  };

  const checkSyncStatus = async () => {
    setSyncing(true);
    try {
      const response = await fetch('http://localhost:8000/api/model-cards/sync-report');
      if (response.ok) {
        const data = await response.json();
        setSyncReport(data);
        setShowSyncReport(true);

        if (data.out_of_sync > 0) {
          toast.warning(`${data.out_of_sync} card(s) out of sync`);
        } else {
          toast.success('All cards in sync!');
        }
      }
    } catch (error) {
      console.error('Error checking sync status:', error);
      toast.error('Failed to check sync status');
    } finally {
      setSyncing(false);
    }
  };

  const syncAllCards = async () => {
    setSyncing(true);
    try {
      const response = await fetch('http://localhost:8000/api/model-cards/sync-all', {
        method: 'POST'
      });
      if (response.ok) {
        const data = await response.json();
        toast.success(`Synced ${data.synced_count} card(s)`);
        setShowSyncReport(false);
        fetchModelCards();
      }
    } catch (error) {
      console.error('Error syncing:', error);
      toast.error('Failed to sync');
    } finally {
      setSyncing(false);
    }
  };

  const syncSingleCard = async (tokenId: number) => {
    try {
      const response = await fetch(`http://localhost:8000/api/model-cards/${tokenId}/sync`, {
        method: 'POST'
      });
      if (response.ok) {
        const data = await response.json();
        if (data.synced) {
          toast.success(`Card #${tokenId} synced: ${data.neo4j_status} -> ${data.chain_status}`);
          fetchModelCards();
        } else {
          toast.info(`Card #${tokenId} already in sync`);
        }
      }
    } catch (error) {
      console.error('Error syncing card:', error);
      toast.error('Failed to sync card');
    }
  };

  const fetchVersionChain = async (tokenId: number) => {
    setLoadingVersionChain(true);
    try {
      const response = await fetch(`http://localhost:8000/api/model-cards/${tokenId}/version-chain`);
      if (response.ok) {
        const data = await response.json();
        setVersionChainData(data);
        setShowVersionChain(true);
      }
    } catch (error) {
      console.error('Error fetching version chain:', error);
      toast.error('Failed to fetch version chain');
    } finally {
      setLoadingVersionChain(false);
    }
  };

  const statusTone = (status: string) => {
    switch (status) {
      case 'Created':         return { cls: 'pill-muted',  label: 'Draft' };
      case 'InEvaluation':    return { cls: 'pill-warn',   label: 'Under Review' };
      case 'Validated':       return { cls: 'pill-info',   label: 'Reviewed' };
      case 'Published':       return { cls: 'pill-ok',     label: 'Published' };
      case 'Rejected':        return { cls: 'pill-danger', label: 'Declined' };
      case 'RevisionRequested': return { cls: 'pill-warn', label: 'Changes Requested' };
      case 'Revised':         return { cls: 'pill-info',   label: 'Revised' };
      case 'Deprecated':      return { cls: 'pill-muted',  label: 'Archived' };
      default:                return { cls: 'pill-muted',  label: status };
    }
  };

  const filterTabs: Array<{ value: string; label: string }> = [
    { value: 'all',               label: 'All public' },
    { value: 'Published',         label: 'Published' },
    { value: 'Deprecated',        label: 'Archived' },
  ];

  return (
    <main>
      <div className="container-app py-10 lg:py-14">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between mb-10">
          <div>
            <p className="meta mb-3">Registry</p>
            <h1 className="text-3xl lg:text-4xl font-semibold tracking-tight">
              Model card registry
            </h1>
            <p className="mt-3 max-w-xl" style={{ color: 'var(--fg-muted)' }}>
              Published and archived cards are public. Drafts and cards under review
              are private to their author and assigned reviewers.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={checkSyncStatus}
              disabled={syncing}
              className="btn btn-secondary"
            >
              {syncing ? 'Checking...' : 'Sync status'}
            </button>
            <Link href="/create" className="btn btn-primary">
              New card
            </Link>
          </div>
        </div>

        <div className="surface p-4 mb-4">
          <div className="flex items-center gap-3">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => handleSearchChange(e.target.value)}
              placeholder="Search by name, organization, algorithm, or clinical indication"
              className="input flex-1 border-0 shadow-none"
              style={{ border: 'none', height: 32, padding: 0 }}
            />
            {isSearching && (
              <span className="meta">Searching...</span>
            )}
            {searchQuery && (
              <button onClick={clearSearch} className="btn btn-ghost btn-sm">
                Clear
              </button>
            )}
          </div>
          {searchResults !== null && (
            <p className="mt-3 text-sm" style={{ color: 'var(--fg-subtle)' }}>
              <span className="font-medium" style={{ color: 'var(--fg)' }}>
                {searchResults.length}
              </span>{' '}
              result{searchResults.length !== 1 ? 's' : ''} for &ldquo;{searchQuery}&rdquo;
            </p>
          )}
        </div>

        <div className="flex items-center gap-1 mb-8 overflow-x-auto pb-2">
          {filterTabs.map((tab) => {
            const active = filter === tab.value;
            return (
              <button
                key={tab.value}
                onClick={() => setFilter(tab.value)}
                className="px-3.5 py-1.5 rounded-full text-[13px] whitespace-nowrap transition-colors"
                style={{
                  background: active ? 'var(--fg)' : 'var(--bg)',
                  color: active ? 'var(--bg)' : 'var(--fg-muted)',
                  border: `1px solid ${active ? 'var(--fg)' : 'var(--border-strong)'}`,
                  fontWeight: active ? 500 : 400,
                }}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {loading && (
          <div className="grid-cards">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="surface p-6 animate-pulse">
                <div className="h-3 w-16 mb-4 rounded" style={{ background: 'var(--bg-muted)' }} />
                <div className="h-5 w-2/3 mb-3 rounded" style={{ background: 'var(--bg-muted)' }} />
                <div className="h-3 w-full mb-2 rounded" style={{ background: 'var(--bg-muted)' }} />
                <div className="h-3 w-5/6 rounded" style={{ background: 'var(--bg-muted)' }} />
              </div>
            ))}
          </div>
        )}

        {!loading && displayCards.length === 0 && (
          <div className="surface p-16 text-center">
            <p className="meta mb-3">{searchQuery ? 'No matches' : 'Empty registry'}</p>
            <h3 className="text-xl font-semibold tracking-tight mb-2">
              {searchQuery
                ? 'Nothing matches that query'
                : filter === 'all'
                  ? 'No model cards'
                  : `No cards in ${filter}`}
            </h3>
            <p className="mb-7 max-w-md mx-auto" style={{ color: 'var(--fg-muted)' }}>
              {searchQuery
                ? `Try a broader query or clear the search to see all cards.`
                : 'No cards have been published yet.'}
            </p>
            {searchQuery ? (
              <button onClick={clearSearch} className="btn btn-secondary">
                Clear search
              </button>
            ) : (
              <Link href="/create" className="btn btn-primary">
                Create the first card
              </Link>
            )}
          </div>
        )}

        {!loading && displayCards.length > 0 && (
          <>
            <p className="meta mb-5">
              {searchResults !== null
                ? `${displayCards.length} result${displayCards.length !== 1 ? 's' : ''}`
                : `${displayCards.length} card${displayCards.length !== 1 ? 's' : ''}`}
            </p>
            <div className="grid-cards">
              {displayCards.map((card) => {
                const tone = statusTone(card.current_status);
                return (
                  <article key={card.token_id} className="surface surface-hover overflow-hidden flex flex-col">
                    <Link href={`/model/${card.token_id}`} className="block p-6 flex-1">
                      <div className="flex items-baseline justify-between mb-4 gap-2 flex-wrap">
                        <span className="mono" style={{ color: 'var(--fg-faint)' }}>
                          #{card.token_id}
                        </span>
                        <div className="flex items-center gap-1.5">
                          {card.challenges && card.challenges.total > 0 && (
                            <span
                              className="pill"
                              title={
                                `${card.challenges.total} total challenge${card.challenges.total === 1 ? '' : 's'}` +
                                (card.challenges.open ? ` · ${card.challenges.open} open` : '') +
                                (card.challenges.split ? ` · ${card.challenges.split} awaiting admin` : '') +
                                (card.challenges.resolved ? ` · ${card.challenges.resolved} resolved` : '')
                              }
                              style={{
                                background: card.challenges.open || card.challenges.split
                                  ? 'rgba(180,83,9,0.15)'
                                  : 'rgba(115,115,115,0.12)',
                                color: card.challenges.open || card.challenges.split
                                  ? 'var(--warn,#b45309)'
                                  : 'var(--fg-muted)',
                                border: '1px solid currentColor',
                              }}
                            >
                              {card.challenges.total} challenge{card.challenges.total === 1 ? '' : 's'}
                              {card.challenges.open > 0 && ` · ${card.challenges.open} open`}
                            </span>
                          )}
                          <span className={`pill ${tone.cls}`}>{tone.label}</span>
                        </div>
                      </div>
                      <h3 className="text-base font-semibold tracking-tight mb-1.5 line-clamp-2">
                        {card.model_name || `Untitled card #${card.token_id}`}
                      </h3>
                      <p className="text-[13px]" style={{ color: 'var(--fg-subtle)' }}>
                        {card.developer_organization || 'Unknown organization'} ·{' '}
                        <span className="mono">v{card.version || '1.0.0'}</span>
                      </p>
                      <p className="mt-4 text-[14px] leading-[1.55] line-clamp-3" style={{ color: 'var(--fg-muted)' }}>
                        {card.description || 'No description available.'}
                      </p>
                      <div className="mt-5 flex flex-wrap items-center gap-2 text-[12px]" style={{ color: 'var(--fg-subtle)' }}>
                        {card.metadata?.superseded_by && (
                          <span>Superseded by #{card.metadata.superseded_by}</span>
                        )}
                        {card.metadata?.supersedes && (
                          <span>Supersedes #{card.metadata.supersedes}</span>
                        )}
                        {card.created_at && (
                          <span>{safeDate(card.created_at)}</span>
                        )}
                      </div>
                    </Link>
                    <div
                      className="flex items-center justify-between px-6 py-3 border-t"
                      style={{ borderColor: 'var(--border)', background: 'var(--bg-subtle)' }}
                    >
                      <div className="flex items-center gap-4 text-[12.5px]">
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            fetchVersionHistory(card.token_id);
                          }}
                          className="link-muted"
                        >
                          Versions
                        </button>
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            fetchVersionChain(card.token_id);
                          }}
                          className="link-muted"
                        >
                          Lineage
                        </button>
                      </div>
                      <Link href={`/model/${card.token_id}`} className="text-[12.5px] font-medium">
                        Open
                      </Link>
                    </div>
                  </article>
                );
              })}
            </div>
          </>
        )}
      </div>

      {showVersionHistory && (
        <Modal title="Version history" subtitle={`Card #${selectedTokenId}`} onClose={() => setShowVersionHistory(false)}>
          {versionHistory.length > 1 && (
            <p className="meta mb-4">
              Select up to 2 versions to compare ({selectedVersions.length}/2)
            </p>
          )}
          {loadingVersions ? (
            <p className="text-center py-10" style={{ color: 'var(--fg-subtle)' }}>Loading...</p>
          ) : versionHistory.length === 0 ? (
            <p className="text-center py-10" style={{ color: 'var(--fg-subtle)' }}>No version history available.</p>
          ) : (
            <ul className="space-y-3">
              {versionHistory.map((version, index) => {
                const selected = selectedVersions.includes(index);
                return (
                  <li
                    key={index}
                    className="surface p-4 transition-colors"
                    style={{ borderColor: selected ? 'var(--fg)' : 'var(--border)', background: selected ? 'var(--bg-subtle)' : 'var(--bg)' }}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-center gap-3">
                        {versionHistory.length > 1 && (
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={() => handleVersionSelect(index)}
                            className="w-4 h-4"
                          />
                        )}
                        <span className="mono text-[13px] font-semibold">v{version.version}</span>
                        {index === 0 && <span className="pill pill-ok">Latest</span>}
                      </div>
                      <span className="meta">{safeDate(version.timestamp, 'datetime')}</span>
                    </div>
                    {version.previous_version && (
                      <p className="mt-3 text-[13px]" style={{ color: 'var(--fg-subtle)' }}>
                        Previous version: <span className="mono">v{version.previous_version}</span>
                      </p>
                    )}
                    {version.notes && (
                      <p className="mt-2 text-[13.5px]" style={{ color: 'var(--fg-muted)' }}>{version.notes}</p>
                    )}
                    <div className="mt-3 flex gap-4 text-[12.5px]">
                      {version.metadata_uri && (
                        <a href={version.metadata_uri} target="_blank" rel="noopener noreferrer" className="link-muted">
                          View metadata
                        </a>
                      )}
                      {index > 0 && (
                        <button
                          onClick={() => window.open(`/model/${selectedTokenId}?version=${version.version}`, '_blank')}
                          className="link-muted"
                        >
                          Open this version
                        </button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          <ModalFooter>
            <button onClick={() => setShowVersionHistory(false)} className="btn btn-secondary">
              Close
            </button>
            {versionHistory.length > 1 && (
              <button
                onClick={compareVersions}
                disabled={selectedVersions.length !== 2}
                className="btn btn-primary"
              >
                Compare ({selectedVersions.length}/2)
              </button>
            )}
          </ModalFooter>
        </Modal>
      )}

      {showComparison && comparisonData && (
        <Modal
          title="Version comparison"
          subtitle={`v${comparisonData.version1.version} vs v${comparisonData.version2.version}`}
          width="max-w-5xl"
          onClose={() => { setShowComparison(false); setShowVersionHistory(true); }}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-px" style={{ background: 'var(--border)' }}>
            {[comparisonData.version1, comparisonData.version2].map((v: any, i: number) => (
              <div key={i} className="p-5" style={{ background: 'var(--bg)' }}>
                <p className="meta mb-2">Version {i + 1}</p>
                <h4 className="text-base font-semibold mb-1">v{v.version}</h4>
                <p className="meta mb-4">{safeDate(v.timestamp, 'datetime')}</p>
                <dl className="space-y-3 text-[13.5px]">
                  <div>
                    <dt className="meta mb-1">Previous version</dt>
                    <dd className="mono">{v.previous_version || '-'}</dd>
                  </div>
                  {v.notes && (
                    <div>
                      <dt className="meta mb-1">Revision notes</dt>
                      <dd style={{ color: 'var(--fg-muted)' }}>{v.notes}</dd>
                    </div>
                  )}
                  {v.metadata_uri && (
                    <div>
                      <dt className="meta mb-1">Metadata URI</dt>
                      <dd>
                        <a href={v.metadata_uri} target="_blank" rel="noopener noreferrer" className="link mono break-all">
                          {v.metadata_uri}
                        </a>
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
            ))}
          </div>
          <p className="mt-5 text-[13px]" style={{ color: 'var(--fg-subtle)' }}>
            Time between versions:{' '}
            {(() => {
              const ms = Math.abs(
                new Date(comparisonData.version2.timestamp).getTime() -
                  new Date(comparisonData.version1.timestamp).getTime()
              );
              const hours = ms / 3_600_000;
              return hours < 24 ? `${Math.round(hours)} hours` : `${Math.round(hours / 24)} days`;
            })()}
          </p>
          <ModalFooter>
            <button onClick={() => { setShowComparison(false); setShowVersionHistory(true); }} className="btn btn-secondary">
              Back
            </button>
          </ModalFooter>
        </Modal>
      )}

      {showSyncReport && syncReport && (
        <Modal title="Sync status" subtitle="Blockchain vs Neo4j" onClose={() => setShowSyncReport(false)}>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <Stat label="Total" value={syncReport.total} />
            <Stat label="In sync" value={syncReport.in_sync} tone="ok" />
            <Stat label="Out of sync" value={syncReport.out_of_sync} tone="danger" />
            <Stat label="Failed" value={syncReport.check_failed} tone="muted" />
          </div>
          {syncReport.discrepancies && syncReport.discrepancies.length > 0 ? (
            <div>
              <p className="meta mb-3">Discrepancies</p>
              <ul className="space-y-2">
                {syncReport.discrepancies.map((d) => (
                  <li
                    key={d.token_id}
                    className="flex items-center justify-between px-4 py-3 surface"
                  >
                    <div className="flex items-center gap-3 text-[13.5px]">
                      <span className="mono font-medium">#{d.token_id}</span>
                      <span style={{ color: 'var(--danger)' }}>{d.neo4j_status}</span>
                      <span style={{ color: 'var(--fg-faint)' }}>to</span>
                      <span style={{ color: 'var(--ok)' }}>{d.chain_status}</span>
                    </div>
                    <button
                      onClick={() => { syncSingleCard(d.token_id); setShowSyncReport(false); }}
                      className="btn btn-secondary btn-sm"
                    >
                      Sync
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-center py-8" style={{ color: 'var(--fg-subtle)' }}>
              Cards in sync.
            </p>
          )}
          <ModalFooter>
            <button onClick={() => setShowSyncReport(false)} className="btn btn-secondary">
              Close
            </button>
            {syncReport.out_of_sync > 0 && (
              <button onClick={syncAllCards} disabled={syncing} className="btn btn-primary">
                {syncing ? 'Syncing...' : `Sync all (${syncReport.out_of_sync})`}
              </button>
            )}
          </ModalFooter>
        </Modal>
      )}

      {showVersionChain && versionChainData && (
        <Modal
          title="Version lineage"
          subtitle={`${versionChainData.model_name} · ${versionChainData.organization}`}
          onClose={() => setShowVersionChain(false)}
        >
          {loadingVersionChain ? (
            <p className="text-center py-10" style={{ color: 'var(--fg-subtle)' }}>Loading...</p>
          ) : (
            <div className="space-y-5">
              <div className="surface p-4" style={{ borderColor: 'var(--fg)' }}>
                <div className="flex items-center justify-between mb-2">
                  <span className="pill" style={{ background: 'var(--fg)', color: 'var(--bg)', borderColor: 'var(--fg)' }}>
                    Current
                  </span>
                  <span className={`pill ${statusTone(versionChainData.status).cls}`}>
                    {statusTone(versionChainData.status).label}
                  </span>
                </div>
                <p className="text-base font-semibold">
                  <span className="mono" style={{ color: 'var(--fg-faint)' }}>#{versionChainData.token_id}</span>
                  <span className="mx-2">·</span>
                  <span className="mono">v{versionChainData.version}</span>
                </p>
              </div>

              {versionChainData.immediate_predecessor && (
                <ChainNode
                  label="Supersedes"
                  node={versionChainData.immediate_predecessor}
                  toneCls={statusTone(versionChainData.immediate_predecessor.status).cls}
                  toneLabel={statusTone(versionChainData.immediate_predecessor.status).label}
                />
              )}
              {versionChainData.immediate_successor && (
                <ChainNode
                  label="Superseded by"
                  node={versionChainData.immediate_successor}
                  toneCls={statusTone(versionChainData.immediate_successor.status).cls}
                  toneLabel={statusTone(versionChainData.immediate_successor.status).label}
                />
              )}

              {(versionChainData.all_predecessors?.length > 0 || versionChainData.all_successors?.length > 0) && (
                <div className="mt-2 pt-5 border-t" style={{ borderColor: 'var(--border)' }}>
                  <p className="meta mb-3">Complete chain</p>
                  <div className="flex flex-wrap items-center gap-2">
                    {versionChainData.all_predecessors?.map((p: any) => (
                      <Link key={p.token_id} href={`/model/${p.token_id}`} className="pill pill-muted">
                        #{p.token_id} v{p.version}
                      </Link>
                    ))}
                    <span className="pill" style={{ background: 'var(--fg)', color: 'var(--bg)', borderColor: 'var(--fg)' }}>
                      #{versionChainData.token_id} v{versionChainData.version}
                    </span>
                    {versionChainData.all_successors?.map((s: any) => (
                      <Link key={s.token_id} href={`/model/${s.token_id}`} className="pill pill-muted">
                        #{s.token_id} v{s.version}
                      </Link>
                    ))}
                  </div>
                </div>
              )}

              {!versionChainData.immediate_predecessor && !versionChainData.immediate_successor && (
                <p className="text-center py-6 text-[13.5px]" style={{ color: 'var(--fg-subtle)' }}>
                  This card has no supersession relationships.
                </p>
              )}
            </div>
          )}
          <ModalFooter>
            <button onClick={() => setShowVersionChain(false)} className="btn btn-secondary">
              Close
            </button>
          </ModalFooter>
        </Modal>
      )}
    </main>
  );
}

function Modal({
  title,
  subtitle,
  children,
  onClose,
  width,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  onClose: () => void;
  width?: string;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.4)' }}
      onClick={onClose}
    >
      <div
        className={`${width || 'max-w-3xl'} w-full max-h-[85vh] flex flex-col surface overflow-hidden`}
        style={{ boxShadow: 'var(--shadow-lg)' }}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <div>
            <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
            {subtitle && <p className="meta mt-1">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="btn btn-ghost btn-sm" aria-label="Close">
            Close
          </button>
        </header>
        <div className="px-6 py-5 overflow-y-auto flex-1">{children}</div>
      </div>
    </div>
  );
}

function ModalFooter({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-6 pt-5 border-t flex items-center justify-end gap-2" style={{ borderColor: 'var(--border)' }}>
      {children}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: 'ok' | 'danger' | 'muted' }) {
  const colors: Record<string, string> = {
    ok: 'var(--ok)',
    danger: 'var(--danger)',
    muted: 'var(--fg-subtle)',
  };
  return (
    <div className="surface p-4 text-center">
      <p className="text-2xl font-semibold tabular-nums" style={{ color: tone ? colors[tone] : 'var(--fg)' }}>
        {value}
      </p>
      <p className="meta mt-1">{label}</p>
    </div>
  );
}

function ChainNode({
  label,
  node,
  toneCls,
  toneLabel,
}: {
  label: string;
  node: { token_id: number; version: string; status: string };
  toneCls: string;
  toneLabel: string;
}) {
  return (
    <div className="surface p-4">
      <p className="meta mb-2">{label}</p>
      <div className="flex items-center gap-3">
        <Link href={`/model/${node.token_id}`} className="text-base font-semibold link mono">
          #{node.token_id}
        </Link>
        <span className="mono text-[13px]" style={{ color: 'var(--fg-subtle)' }}>v{node.version}</span>
        <span className={`pill ${toneCls}`}>{toneLabel}</span>
      </div>
    </div>
  );
}
