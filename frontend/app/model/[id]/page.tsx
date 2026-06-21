'use client';

import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import { useParams } from "next/navigation";
import { toast } from 'sonner';
import { useAuth } from '@/contexts/AuthContext';
import { displayStatus } from '@/lib/utils';
import {
  IdentityAttribution,
  ActionList,
  ChallengeModal,
  type GovernancePayload,
  type ActionRecord,
} from '@/components/Governance';
import {
  LineageTree,
  ChallengeEnvelopeModal,
  type LinePayload,
  type VersionRecord,
} from '@/components/Lineage';
import { TrustPanel } from '@/components/TrustPanel';
import { RevisionDialogue } from '@/components/RevisionDialogue';

interface ModelCardDetails {
  token_id: number;
  on_chain: {
    status: string;
    creator: string;
    metadata_uri: string;
    blockchain_synced?: boolean;
  };
  history: any[];
  current_status: string;
  blockchain_synced: boolean;
  metadata: any;
  model_name: string;
  version: string;
  description: string;
  developer_organization: string;
  created_at: any;
  governance?: GovernancePayload;
}

interface VersionChain {
  token_id: number;
  model_name: string;
  version: string;
  status: string;
  organization: string;
  immediate_predecessor: {
    token_id: number;
    version: string;
    status: string;
  } | null;
  immediate_successor: {
    token_id: number;
    version: string;
    status: string;
  } | null;
  all_predecessors: Array<{token_id: number; version: string; status: string}>;
  all_successors: Array<{token_id: number; version: string; status: string}>;
}

function Section({ title, children, defaultOpen = false }: {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-6 py-4 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition"
      >
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        <svg
          className={`w-5 h-5 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isOpen && (
        <div className="px-6 py-4 border-t border-gray-200">
          {children}
        </div>
      )}
    </div>
  );
}

function Field({ label, value, mono = false }: { label: string; value: any; mono?: boolean }) {
  if (value === null || value === undefined || value === '') return null;

  const displayValue = typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);

  return (
    <div className="py-2 border-b border-gray-100 last:border-0">
      <dt className="text-sm font-medium text-gray-500">{label}</dt>
      <dd className={`mt-1 text-sm text-gray-900 ${mono ? 'font-mono' : ''} whitespace-pre-wrap`}>
        {displayValue}
      </dd>
    </div>
  );
}

function ChartGrid({ charts }: { charts: Record<string, { image: string; title: string }> | undefined }) {
  if (!charts || Object.keys(charts).length === 0) return null;
  return (
    <div className="mt-5 mb-2 grid grid-cols-1 md:grid-cols-2 gap-4">
      {Object.entries(charts).map(([key, v]) => (
        <figure key={key} className="rounded-lg border border-gray-200 dark:border-gray-700 p-3 bg-white dark:bg-gray-900">
          <figcaption className="meta mb-2">{v.title}</figcaption>
          <img
            src={v.image.startsWith('data:') ? v.image : `data:image/png;base64,${v.image}`}
            alt={v.title}
            className="w-full h-auto rounded"
          />
        </figure>
      ))}
    </div>
  );
}

function DataTable({ data, columns }: { data: any[]; columns: { key: string; label: string }[] }) {
  if (!data || data.length === 0) return <p className="text-gray-500 text-sm">No data available</p>;

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {columns.map(col => (
              <th key={col.key} className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {data.map((row, idx) => (
            <tr key={idx}>
              {columns.map(col => (
                <td key={col.key} className="px-4 py-2 text-sm text-gray-900">
                  {typeof row[col.key] === 'object' ? JSON.stringify(row[col.key]) : row[col.key] ?? '-'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ModelDetailPage() {
  const params = useParams();
  const tokenId = params.id;
  const { getWalletAddress } = useAuth();

  const [modelCard, setModelCard] = useState<ModelCardDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [versionChain, setVersionChain] = useState<VersionChain | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [challengeTarget, setChallengeTarget] = useState<ActionRecord | null>(null);
  const [vizBySection, setVizBySection] = useState<Record<string, Record<string, { image: string; title: string }>>>({});
  const [versionRecord, setVersionRecord] = useState<VersionRecord | null>(null);
  const [linePayload, setLinePayload] = useState<LinePayload | null>(null);
  const [envelopeChallengeTarget, setEnvelopeChallengeTarget] = useState<VersionRecord | null>(null);
  const [downloadingPng, setDownloadingPng] = useState(false);
  const captureRef = useRef<HTMLDivElement>(null);

  const downloadPng = async () => {
    if (!captureRef.current) return;
    setDownloadingPng(true);
    try {
      const html2canvas = (await import('html2canvas')).default;
      const canvas = await html2canvas(captureRef.current, {
        backgroundColor: '#ffffff',
        scale: 2,
        useCORS: true,
        logging: false,
      });
      const data = canvas.toDataURL('image/png');
      const a = document.createElement('a');
      a.href = data;
      a.download = `model-card-${tokenId}.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err: any) {
      toast.error(err?.message || 'PNG capture failed');
    } finally {
      setDownloadingPng(false);
    }
  };

  useEffect(() => {
    if (tokenId) {
      fetchModelCard();
      fetchVersionChain();
      fetchVisualizations();
      fetchLineage();
    }
  }, [tokenId]);

  const fetchLineage = async () => {
    try {
      const vr = await fetch(`http://localhost:8000/api/versions/${tokenId}`);
      if (!vr.ok) return;
      const v = await vr.json();
      if (!v || !v.token_id) return;
      setVersionRecord(v as VersionRecord);
    } catch (_) {}
  };

  useEffect(() => {
    if (!modelCard || !versionRecord) return;
    const guessedName = (modelCard.metadata?.["1. Model Details"]?.["Model Name"]
      || modelCard.model_name
      || "")
      .trim().toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
    if (!guessedName) return;
    fetch(`http://localhost:8000/api/lines/${encodeURIComponent(guessedName)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d && d.has_name_record) setLinePayload(d as LinePayload); })
      .catch(() => {});
  }, [modelCard, versionRecord]);

  const fetchVisualizations = async () => {
    try {
      const r = await fetch(`http://localhost:8000/api/model-cards/${tokenId}/visualizations`);
      if (r.ok) {
        const d = await r.json();
        setVizBySection(d.visualizations || {});
      }
    } catch (_) {}
  };

  const fetchModelCard = async () => {
    setLoading(true);
    setError(null);
    try {
      const wallet = getWalletAddress();
      const url = wallet
        ? `http://localhost:8000/api/model-cards/${tokenId}?actor=${encodeURIComponent(wallet)}`
        : `http://localhost:8000/api/model-cards/${tokenId}`;
      const response = await fetch(url);
      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Model card not found');
      }
      const data = await response.json();
      setModelCard(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load model card');
    } finally {
      setLoading(false);
    }
  };

  const fetchVersionChain = async () => {
    try {
      const response = await fetch(`http://localhost:8000/api/model-cards/${tokenId}/version-chain`);
      if (response.ok) {
        const data = await response.json();
        setVersionChain(data);
      }
    } catch (err) {
      console.error('Error fetching version chain:', err);
    }
  };

  const syncCard = async () => {
    setSyncing(true);
    try {
      const response = await fetch(`http://localhost:8000/api/model-cards/${tokenId}/sync`, {
        method: 'POST'
      });
      if (response.ok) {
        const data = await response.json();
        if (data.synced) {
          toast.success(`Synced: ${data.neo4j_status} -> ${data.chain_status}`);
          fetchModelCard();
        } else {
          toast.info('Already in sync');
        }
      }
    } catch (err) {
      toast.error('Sync failed');
    } finally {
      setSyncing(false);
    }
  };

  const getStatusColor = (status: string) => {
    const statusColors: Record<string, string> = {
      'Created': 'bg-gray-100 text-gray-800 border-gray-300',
      'InEvaluation': 'bg-yellow-100 text-yellow-800 border-yellow-300',
      'Validated': 'bg-green-100 text-green-800 border-green-300',
      'Published': 'bg-blue-100 text-blue-800 border-blue-300',
      'Rejected': 'bg-red-100 text-red-800 border-red-300',
      'RevisionRequested': 'bg-orange-100 text-orange-800 border-orange-300',
      'Revised': 'bg-purple-100 text-purple-800 border-purple-300',
      'Deprecated': 'bg-gray-100 text-gray-500 border-gray-300'
    };
    return statusColors[status] || 'bg-gray-100 text-gray-800 border-gray-300';
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="flex justify-center items-center py-20">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          </div>
        </div>
      </main>
    );
  }

  if (error || !modelCard) {
    return (
      <main className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Link href="/gallery" className="text-blue-600 hover:text-blue-800 flex items-center mb-4">
            &larr; Back to Registry
          </Link>
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <div className="text-6xl mb-4">&#x274C;</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">Model Card Not Found</h3>
            <p className="text-gray-600 mb-6">{error || 'The requested model card does not exist.'}</p>
            <Link
              href="/gallery"
              className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition"
            >
              Back to Registry
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const metadata = modelCard.metadata || {};
  const modelDetails = metadata["1. Model Details"] || {};
  const intendedUse = metadata["2. Intended Use and Clinical Context"] || {};
  const dataFactors = metadata["3. Data & Factors"] || {};
  const featuresOutputs = metadata["4. Features & Outputs"] || {};
  const performance = metadata["5. Performance & Validation"] || {};
  const methodology = metadata["6. Methodology & Explainability"] || {};
  const additionalInfo = metadata["7. Additional Information"] || {};

  return (
    <main>
      <div className="container-app py-10 lg:py-14">
        <Link href="/gallery" className="text-[13px] link-muted">
          Back to registry
        </Link>

        <header className="mt-6 mb-10 grid grid-cols-1 lg:grid-cols-12 gap-8">
          <div className="lg:col-span-9">
            <p className="meta mb-3">
              <span className="mono">#{tokenId}</span> ·{' '}
              {modelDetails["Developer / Organization"] || modelCard.developer_organization || 'Unknown organization'} ·{' '}
              <span className="mono">v{modelDetails["Version"] || modelCard.version || '1.0.0'}</span>
            </p>
            <h1 className="text-3xl lg:text-4xl font-semibold tracking-tight">
              {modelDetails["Model Name"] || modelCard.model_name || `Model card #${tokenId}`}
            </h1>
            <p className="mt-4 text-[15.5px] leading-[1.6] max-w-3xl" style={{ color: 'var(--fg-muted)' }}>
              {modelDetails["Description"] || modelCard.description || 'No description available.'}
            </p>
          </div>
          <div className="lg:col-span-3 flex flex-col items-start lg:items-end gap-2">
            <span className={`px-3 py-1 rounded-md text-[12.5px] font-medium border ${getStatusColor(modelCard.current_status)}`}>
              {displayStatus(modelCard.current_status)}
            </span>
            {(() => {
              const acts = (modelCard.governance?.actions || []) as any[];
              const total = acts.filter((a) =>
                ['Disputed', 'ResolvedValid', 'ResolvedInvalid'].includes(a.identity_status),
              ).length;
              const open = acts.filter((a) => a.identity_status === 'Disputed').length;
              if (total === 0) return null;
              const isHot = open > 0;
              return (
                <span
                  className="px-2.5 py-0.5 rounded-md text-[12px] font-medium border"
                  style={{
                    background: isHot ? 'rgba(180,83,9,0.10)' : 'rgba(115,115,115,0.10)',
                    color: isHot ? 'var(--warn,#b45309)' : 'var(--fg-muted)',
                    borderColor: isHot ? 'var(--warn,#b45309)' : 'var(--border)',
                  }}
                  title={`${total} total challenge${total === 1 ? '' : 's'}${open ? ` · ${open} open` : ''}`}
                >
                  {total} challenge{total === 1 ? '' : 's'}
                  {open > 0 && ` · ${open} open`}
                </span>
              );
            })()}
            {!modelCard.blockchain_synced && (
              <span className="meta" style={{ color: 'var(--warn)' }}>
                Blockchain not synced
              </span>
            )}
          </div>
        </header>

        {linePayload && (linePayload.versions || []).length > 1 && (
          <LineageTree line={linePayload} currentTokenId={Number(tokenId)} />
        )}

        <RevisionDialogue tokenId={Number(tokenId)} />

        <div className="mb-8 flex items-center gap-2 flex-wrap">
          <span className="meta">Download:</span>
          <a
            href={`http://localhost:8000/api/model-cards/${tokenId}/export?format=json`}
            className="btn btn-secondary btn-sm"
            download
          >
            JSON
          </a>
          <a
            href={`http://localhost:8000/api/model-cards/${tokenId}/export?format=md`}
            className="btn btn-secondary btn-sm"
            download
          >
            Markdown
          </a>
          <a
            href={`http://localhost:8000/api/model-cards/${tokenId}/export?format=html`}
            className="btn btn-secondary btn-sm"
            download
          >
            HTML
          </a>
          <button
            onClick={downloadPng}
            className="btn btn-secondary btn-sm"
            disabled={downloadingPng}
          >
            {downloadingPng ? 'Capturing…' : 'PNG'}
          </button>
        </div>

        <div ref={captureRef} className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="lg:col-span-3 space-y-4">

            <Section title="1. Model Details" defaultOpen={true}>
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
                <Field label="Model Name" value={modelDetails["Model Name"]} />
                <Field label="Version" value={modelDetails["Version"]} />
                <Field label="Developer / Organization" value={modelDetails["Developer / Organization"]} />
                <Field label="Release Date" value={modelDetails["Release Date"]} />
                <Field label="Clinical Function" value={modelDetails["Clinical Function"]} />
                <Field label="Intended Purpose" value={modelDetails["Intended Purpose"]} />
                <Field label="Algorithm(s) Used" value={modelDetails["Algorithm(s) Used"]} />
                <Field label="GMDN Code" value={modelDetails["GMDN Code"]} />
                <Field label="Licensing" value={modelDetails["Licensing"]} />
                <Field label="Support Contact" value={modelDetails["Support Contact"]} />
              </dl>
              <div className="mt-4">
                <Field label="Description" value={modelDetails["Description"]} />
              </div>
              {modelDetails["Literature References"]?.length > 0 && (
                <div className="mt-4">
                  <dt className="text-sm font-medium text-gray-500 mb-2">Literature References</dt>
                  <ul className="list-disc list-inside text-sm text-gray-900">
                    {modelDetails["Literature References"].map((ref: string, i: number) => (
                      <li key={i}>{ref}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Section>

            <Section title="2. Intended Use and Clinical Context" defaultOpen={true}>
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
                <Field label="Primary Intended Users" value={intendedUse["Primary Intended Users"]} />
                <Field label="Intended Use Environment" value={intendedUse["Intended Use Environment"]} />
                <Field label="Clinical Indications" value={intendedUse["Clinical Indications"]} />
                <Field label="Patient Target Group" value={intendedUse["Patient target group"]} />
                <Field label="Contraindications" value={intendedUse["Contraindications"]} />
                <Field label="Out of Scope Applications" value={intendedUse["Out of Scope Applications"]} />
              </dl>
              {intendedUse["Warnings"] && (
                <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <dt className="text-sm font-medium text-yellow-800 mb-1">&#x26A0;&#xFE0F; Warnings</dt>
                  <dd className="text-sm text-yellow-700">{intendedUse["Warnings"]}</dd>
                </div>
              )}
            </Section>

            <Section title="3. Data & Factors">
              <Field label="Data Distribution Summary" value={dataFactors["Data Distribution Summary"]} />
              <Field label="Data Representativeness" value={dataFactors["Data Representativeness"]} />
              <Field label="Data Governance" value={dataFactors["Data Governance"]} />

              <ChartGrid charts={vizBySection.section_3} />

              {dataFactors["Source Datasets"]?.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Source Datasets</h4>
                  {dataFactors["Source Datasets"].map((dataset: any, idx: number) => (
                    <div key={idx} className="mb-4 p-4 bg-gray-50 rounded-lg border">
                      <h5 className="font-medium text-gray-900 mb-2">{dataset.name}</h5>
                      <dl className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                        <div><span className="text-gray-500">Origin:</span> {dataset.origin}</div>
                        <div><span className="text-gray-500">Size:</span> {dataset.size} records</div>
                        <div><span className="text-gray-500">Collection Period:</span> {dataset.collection_period}</div>
                      </dl>
                      {dataset.demographics && (
                        <div className="mt-2 text-sm">
                          <span className="text-gray-500">Demographics:</span>
                          <div className="ml-2 text-gray-700">
                            <div>Age: {dataset.demographics.age}</div>
                            <div>Gender: {dataset.demographics.gender}</div>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {dataFactors["Concept Sets"]?.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">OMOP Concept Sets</h4>
                  {dataFactors["Concept Sets"].map((cs: any, idx: number) => (
                    <div key={idx} className="mb-3 p-3 bg-gray-50 rounded-lg border text-sm">
                      <div className="font-medium text-gray-900">{cs.name || `Concept set ${idx + 1}`}</div>
                      {cs.vocabulary && <div className="text-gray-500 text-xs mt-1">Vocabulary: {cs.vocabulary}</div>}
                      {cs.description && <div className="mt-1 text-gray-700">{cs.description}</div>}
                      {Array.isArray(cs.concept_ids) && cs.concept_ids.length > 0 && (
                        <div className="mt-2 font-mono text-xs text-gray-600">
                          IDs: {cs.concept_ids.slice(0, 8).join(', ')}
                          {cs.concept_ids.length > 8 && `, +${cs.concept_ids.length - 8} more`}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {dataFactors["Primary Cohort Criteria"] && typeof dataFactors["Primary Cohort Criteria"] === 'object' && (
                <div className="mt-4 p-4 bg-gray-50 rounded-lg border text-sm">
                  <h4 className="font-medium text-gray-900 mb-2">Primary Cohort Criteria</h4>
                  {dataFactors["Primary Cohort Criteria"].inclusion_rules?.length > 0 && (
                    <div className="mb-2">
                      <div className="text-gray-500 text-xs">Inclusion</div>
                      <ul className="list-disc list-inside text-gray-800">
                        {dataFactors["Primary Cohort Criteria"].inclusion_rules.map((r: string, i: number) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {dataFactors["Primary Cohort Criteria"].exclusion_rules?.length > 0 && (
                    <div className="mb-2">
                      <div className="text-gray-500 text-xs">Exclusion</div>
                      <ul className="list-disc list-inside text-gray-800">
                        {dataFactors["Primary Cohort Criteria"].exclusion_rules.map((r: string, i: number) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {dataFactors["Primary Cohort Criteria"].observation_window && (
                    <div>
                      <span className="text-gray-500 text-xs">Observation window: </span>
                      <span className="text-gray-800">{dataFactors["Primary Cohort Criteria"].observation_window}</span>
                    </div>
                  )}
                </div>
              )}
            </Section>

            <Section title="4. Features & Outputs">
              <Field label="Feature Type Distribution" value={featuresOutputs["Feature Type Distribution"]} />
              <Field label="Uncertainty Quantification" value={featuresOutputs["Uncertainty Quantification"]} />
              <Field label="Output Interpretability" value={featuresOutputs["Output Interpretability"]} />

              {featuresOutputs["Input Features"]?.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Input Features</h4>
                  <DataTable
                    data={featuresOutputs["Input Features"]}
                    columns={[
                      { key: 'name', label: 'Name' },
                      { key: 'data_type', label: 'Type' },
                      { key: 'required', label: 'Required' },
                      { key: 'clinical_domain', label: 'Domain' }
                    ]}
                  />
                </div>
              )}

              {featuresOutputs["Output Features"]?.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Output Features</h4>
                  <DataTable
                    data={featuresOutputs["Output Features"]}
                    columns={[
                      { key: 'name', label: 'Name' },
                      { key: 'type', label: 'Type' },
                      { key: 'units', label: 'Units' },
                      { key: 'value_range', label: 'Range' }
                    ]}
                  />
                </div>
              )}
            </Section>

            <Section title="5. Performance & Validation" defaultOpen={true}>
              <Field label="Metric Validation Status" value={performance["Metric Validation Status"]} />
              <Field label="Calibration Analysis" value={performance["Calibration Analysis"]} />
              <Field label="Fairness Assessment" value={performance["Fairness Assessment"]} />

              <ChartGrid charts={vizBySection.section_5} />

              {performance["Claimed Metrics"]?.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Performance Metrics</h4>
                  <DataTable
                    data={performance["Claimed Metrics"]}
                    columns={[
                      { key: 'metric_name', label: 'Metric' },
                      { key: 'value', label: 'Value' },
                      { key: 'validation_status', label: 'Status' },
                      { key: 'subgroup', label: 'Subgroup' }
                    ]}
                  />
                </div>
              )}

              {performance["Validation Dataset(s)"]?.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Validation Datasets</h4>
                  <DataTable
                    data={performance["Validation Dataset(s)"]}
                    columns={[
                      { key: 'name', label: 'Name' },
                      { key: 'source_institution', label: 'Institution' },
                      { key: 'validation_type', label: 'Type' }
                    ]}
                  />
                </div>
              )}

              {performance["Validated Metrics"]?.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Validated Metrics</h4>
                  <DataTable
                    data={performance["Validated Metrics"]}
                    columns={[
                      { key: 'metric_name', label: 'Metric' },
                      { key: 'value', label: 'Value' },
                      { key: 'validation_status', label: 'Status' },
                      { key: 'subgroup', label: 'Subgroup' }
                    ]}
                  />
                </div>
              )}
            </Section>

            <Section title="6. Methodology & Explainability">
              <Field label="Model Development Workflow" value={methodology["Model Development Workflow"]} />
              <Field label="Training Procedure" value={methodology["Training Procedure"]} />
              <Field label="Data Preprocessing" value={methodology["Data Preprocessing"]} />
              <Field label="Synthetic Data Usage" value={methodology["Synthetic Data Usage"]} />
              <Field label="Explainable AI Method" value={methodology["Explainable AI Method"]} />
              <Field label="Global vs. Local Interpretability" value={methodology["Global vs. Local Interpretability"]} />
            </Section>

            <Section title="7. Additional Information">
              <Field label="Benefit-Risk Summary" value={additionalInfo["Benefit–Risk Summary"]} />
              <Field label="Ethical Considerations" value={additionalInfo["Ethical Considerations"]} />
              <Field label="Caveats & Limitations" value={additionalInfo["Caveats & Limitations"]} />
              <Field label="Recommendations for Safe Use" value={additionalInfo["Recommendations for Safe Use"]} />
              <Field label="Post-Market Surveillance Plan" value={additionalInfo["Post-Market Surveillance Plan"]} />
              <Field label="Explainability Recommendations" value={additionalInfo["Explainability Recommendations"]} />

              {Array.isArray(additionalInfo["Supporting Documents"]) && additionalInfo["Supporting Documents"].length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Supporting Documents</h4>
                  <ul className="list-disc list-inside text-sm">
                    {additionalInfo["Supporting Documents"].map((doc: string, idx: number) => (
                      <li key={idx}>
                        {doc.startsWith('http') ? (
                          <a href={doc} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline break-all">{doc}</a>
                        ) : (
                          <span className="text-gray-700">{doc}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Section>

            <Section title="Blockchain Information">
              <dl className="space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-start gap-1">
                  <dt className="text-sm font-medium text-gray-500 sm:w-32">Creator:</dt>
                  <dd className="text-sm text-gray-900 font-mono break-all">{modelCard.on_chain.creator}</dd>
                </div>
                <div className="flex flex-col sm:flex-row sm:items-start gap-1">
                  <dt className="text-sm font-medium text-gray-500 sm:w-32">Status:</dt>
                  <dd className={`inline-flex px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(modelCard.on_chain.status)}`}>
                    {displayStatus(modelCard.on_chain.status)}
                  </dd>
                </div>
                {modelCard.on_chain.metadata_uri && (
                  <div className="flex flex-col sm:flex-row sm:items-start gap-1">
                    <dt className="text-sm font-medium text-gray-500 sm:w-32">Metadata URI:</dt>
                    <dd className="text-sm">
                      <a href={modelCard.on_chain.metadata_uri} target="_blank" rel="noopener noreferrer"
                         className="text-blue-600 hover:text-blue-800 break-all">
                        {modelCard.on_chain.metadata_uri}
                      </a>
                    </dd>
                  </div>
                )}
                <div className="flex flex-col sm:flex-row sm:items-start gap-1">
                  <dt className="text-sm font-medium text-gray-500 sm:w-32">Synced:</dt>
                  <dd className={`text-sm ${modelCard.blockchain_synced ? 'text-green-600' : 'text-yellow-600'}`}>
                    {modelCard.blockchain_synced ? 'Yes - On-chain data verified' : 'No - Using cached data'}
                  </dd>
                </div>
              </dl>
            </Section>

            <Section title="Action history & identity binding">
              {modelCard.governance && modelCard.governance.actions.length > 0 ? (
                <>
                  <div className="space-y-1 mb-4">
                    {modelCard.governance.actions.map((a) => (
                      <IdentityAttribution key={a.action_id} action={a} />
                    ))}
                  </div>
                  <details>
                    <summary className="text-[13px] cursor-pointer" style={{ color: 'var(--fg-subtle)' }}>
                      Full audit detail (claim refs, block numbers)
                    </summary>
                    <div className="mt-3">
                      <ActionList
                        actions={modelCard.governance.actions}
                        onChallenge={(a) => setChallengeTarget(a)}
                      />
                    </div>
                  </details>
                </>
              ) : (
                <p className="text-[13.5px]" style={{ color: 'var(--fg-subtle)' }}>
                  No on-chain actions recorded for this card.
                </p>
              )}
            </Section>
          </div>

          <div className="space-y-4">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Actions</h3>
              <div className="space-y-2">
                <Link
                  href={`/workflow?tokenId=${tokenId}`}
                  className="block w-full px-4 py-2 bg-blue-600 text-white text-center rounded-lg text-sm font-medium hover:bg-blue-700 transition"
                >
                  Manage Lifecycle
                </Link>
                <button
                  onClick={syncCard}
                  disabled={syncing}
                  className="block w-full px-4 py-2 bg-amber-500 text-white text-center rounded-lg text-sm font-medium hover:bg-amber-600 transition disabled:opacity-50"
                >
                  {syncing ? 'Syncing...' : 'Sync Status'}
                </button>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">Quick Stats</h3>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-gray-500">Token ID</dt>
                  <dd className="font-mono font-medium">#{tokenId}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Status</dt>
                  <dd className="font-medium">{displayStatus(modelCard.current_status)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Lifecycle steps</dt>
                  <dd className="font-medium">{modelCard.history?.length || 0}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-gray-500">Version</dt>
                  <dd className="font-medium">{modelDetails["Version"] || modelCard.version || "1.0"}</dd>
                </div>
              </dl>
            </div>

            {versionChain && (versionChain.immediate_predecessor || versionChain.immediate_successor) && (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-purple-900 mb-3 flex items-center gap-2">
                  <span>&#x1F517;</span> Version Lineage
                </h3>

                {versionChain.immediate_predecessor && (
                  <div className="mb-3">
                    <p className="text-xs text-purple-600 mb-1">Supersedes:</p>
                    <Link
                      href={`/model/${versionChain.immediate_predecessor.token_id}`}
                      className="flex items-center justify-between p-2 bg-white rounded border border-purple-200 hover:border-purple-400 transition"
                    >
                      <div>
                        <span className="font-mono text-purple-700 font-medium">
                          #{versionChain.immediate_predecessor.token_id}
                        </span>
                        <span className="text-gray-500 ml-2 text-sm">
                          v{versionChain.immediate_predecessor.version}
                        </span>
                      </div>
                      <span className={`text-xs px-2 py-0.5 rounded ${getStatusColor(versionChain.immediate_predecessor.status)}`}>
                        {versionChain.immediate_predecessor.status}
                      </span>
                    </Link>
                  </div>
                )}

                {versionChain.immediate_successor && (
                  <div>
                    <p className="text-xs text-green-600 mb-1">Superseded by:</p>
                    <Link
                      href={`/model/${versionChain.immediate_successor.token_id}`}
                      className="flex items-center justify-between p-2 bg-white rounded border border-green-200 hover:border-green-400 transition"
                    >
                      <div>
                        <span className="font-mono text-green-700 font-medium">
                          #{versionChain.immediate_successor.token_id}
                        </span>
                        <span className="text-gray-500 ml-2 text-sm">
                          v{versionChain.immediate_successor.version}
                        </span>
                      </div>
                      <span className={`text-xs px-2 py-0.5 rounded ${getStatusColor(versionChain.immediate_successor.status)}`}>
                        {versionChain.immediate_successor.status}
                      </span>
                    </Link>
                  </div>
                )}

                {(versionChain.all_predecessors?.length > 1 || versionChain.all_successors?.length > 1) && (
                  <div className="mt-3 pt-3 border-t border-purple-200">
                    <p className="text-xs text-gray-500 mb-2">Full chain:</p>
                    <div className="flex flex-wrap gap-1">
                      {versionChain.all_predecessors?.map(p => (
                        <Link
                          key={p.token_id}
                          href={`/model/${p.token_id}`}
                          className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded"
                        >
                          #{p.token_id}
                        </Link>
                      ))}
                      <span className="text-xs px-2 py-1 bg-purple-200 text-purple-700 rounded font-semibold">
                        #{tokenId}
                      </span>
                      {versionChain.all_successors?.map(s => (
                        <Link
                          key={s.token_id}
                          href={`/model/${s.token_id}`}
                          className="text-xs px-2 py-1 bg-green-100 hover:bg-green-200 rounded"
                        >
                          #{s.token_id}
                        </Link>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {modelCard.current_status === 'Deprecated' && versionChain?.immediate_successor && (
              <div className="bg-amber-50 border border-amber-300 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-amber-900 mb-2 flex items-center gap-2">
                  Archived
                </h3>
                <p className="text-sm text-amber-700 mb-2">
                  This model card has been archived and superseded by a newer version.
                </p>
                <Link
                  href={`/model/${versionChain.immediate_successor.token_id}`}
                  className="inline-block px-3 py-1.5 bg-amber-600 text-white text-sm rounded hover:bg-amber-700 transition"
                >
                  View New Version
                </Link>
              </div>
            )}

            {modelDetails["Clinical Function"] && (
              <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-indigo-900 mb-1">Clinical Function</h3>
                <p className="text-sm text-indigo-700 capitalize">
                  {modelDetails["Clinical Function"].replace(/_/g, ' ')}
                </p>
              </div>
            )}

            {modelDetails["Intended Purpose"] && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-blue-900 mb-1">Intended Purpose</h3>
                <p className="text-sm text-blue-700 capitalize">
                  {modelDetails["Intended Purpose"].replace(/_/g, ' ')}
                </p>
              </div>
            )}

            {modelDetails["Licensing"] && (
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-gray-900 mb-1">License</h3>
                <p className="text-sm text-gray-700">{modelDetails["Licensing"]}</p>
              </div>
            )}

            {modelDetails["Support Contact"] && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <h3 className="text-sm font-semibold text-green-900 mb-1">Support</h3>
                <a href={`mailto:${modelDetails["Support Contact"]}`} className="text-sm text-green-700 hover:underline">
                  {modelDetails["Support Contact"]}
                </a>
              </div>
            )}

            <TrustPanel
              governance={modelCard.governance}
              line={linePayload}
              version={versionRecord}
            />

            {versionRecord && versionRecord.within_envelope && versionRecord.envelope_status === 'Asserted' && (
              <button
                onClick={() => setEnvelopeChallengeTarget(versionRecord)}
                className="w-full text-[12.5px] text-amber-700 hover:underline text-left"
              >
                Challenge change-plan claim
              </button>
            )}
          </div>
        </div>
      </div>
      <ChallengeModal
        action={challengeTarget}
        onClose={() => setChallengeTarget(null)}
        onSuccess={() => {
          toast.success('Challenge submitted');
          fetchModelCard();
        }}
      />
      <ChallengeEnvelopeModal
        version={envelopeChallengeTarget}
        onClose={() => setEnvelopeChallengeTarget(null)}
        onSuccess={() => {
          toast.success('Envelope challenge submitted');
          fetchLineage();
        }}
      />
    </main>
  );
}
