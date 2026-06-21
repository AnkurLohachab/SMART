'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  Blocks,
  Box,
  FileCheck,
  Users,
  Activity,
  Download,
  RefreshCw,
  Loader2,
  ChevronRight,
  Copy,
  CheckCheck,
  ExternalLink,
  Hash,
  Clock,
  Wallet,
  Shield,
  Code,
  Database,
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  FileJson,
  Search,
  Filter,
  Home
} from 'lucide-react';
import { toast } from 'sonner';

interface PlatformStats {
  total_users: number;
  total_accounts: number;
  total_model_cards: number;
  total_events: number;
}

interface BlockchainStats {
  block_number: number;
  chain_id: number;
  gas_price_gwei: number;
}

interface Contract {
  name: string;
  address: string;
  description: string;
  type: string;
  balance: string;
}

interface Block {
  number: number;
  hash: string;
  timestamp: number;
  transactions: number;
  gas_used: number;
  gas_limit: number;
  miner: string;
}

interface Account {
  user_uuid: string;
  eoa_address: string;
  account_address: string;
  role: string;
  created_at: string;
}

interface Transaction {
  token_id: string;
  model_name: string;
  event_type: string;
  timestamp: string;
  tx_hash: string;
  actor: string;
  new_status: string;
  previous_status: string;
}

interface RoleDistribution {
  role: string;
  count: number;
}

type TabType = 'overview' | 'blocks' | 'transactions' | 'accounts' | 'contracts';

export default function ExplorerDashboard() {
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [copiedText, setCopiedText] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const [platformStats, setPlatformStats] = useState<PlatformStats | null>(null);
  const [blockchainStats, setBlockchainStats] = useState<BlockchainStats | null>(null);
  const [roleDistribution, setRoleDistribution] = useState<RoleDistribution[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);

  const fetchAllData = useCallback(async () => {
    setRefreshing(true);
    try {
      const adminToken = localStorage.getItem('adminToken');
      const headers: Record<string, string> = {};
      if (adminToken) {
        headers['Authorization'] = `Bearer ${adminToken}`;
      }
      const [statsRes, contractsRes, blocksRes, accountsRes, txRes] = await Promise.all([
        fetch('http://localhost:8000/api/admin/explorer/stats', { headers }),
        fetch('http://localhost:8000/api/admin/explorer/contracts', { headers }),
        fetch('http://localhost:8000/api/admin/explorer/blocks?limit=20', { headers }),
        fetch('http://localhost:8000/api/admin/explorer/accounts', { headers }),
        fetch('http://localhost:8000/api/admin/explorer/transactions?limit=50', { headers })
      ]);

      if (statsRes.ok) {
        const data = await statsRes.json();
        setPlatformStats(data.platform);
        setBlockchainStats(data.blockchain);
        setRoleDistribution(data.role_distribution || []);
      }
      if (contractsRes.ok) {
        const data = await contractsRes.json();
        setContracts(data.contracts || []);
      }
      if (blocksRes.ok) {
        const data = await blocksRes.json();
        setBlocks(data.blocks || []);
      }
      if (accountsRes.ok) {
        const data = await accountsRes.json();
        setAccounts(data.accounts || []);
      }
      if (txRes.ok) {
        const data = await txRes.json();
        setTransactions(data.transactions || []);
      }
    } catch (e) {
      console.error('Error fetching data:', e);
      toast.error('Failed to fetch explorer data');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 30000);
    return () => clearInterval(interval);
  }, [fetchAllData]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(text);
    setTimeout(() => setCopiedText(null), 2000);
    toast.success('Copied to clipboard');
  };

  const shortenAddress = (address: string) => {
    if (!address) return '-';
    return `${address.slice(0, 10)}...${address.slice(-8)}`;
  };

  const shortenHash = (hash: string) => {
    if (!hash) return '-';
    return `${hash.slice(0, 14)}...${hash.slice(-10)}`;
  };

  const formatTimestamp = (timestamp: number | string) => {
    if (!timestamp) return '-';
    const date = typeof timestamp === 'number' ? new Date(timestamp * 1000) : new Date(timestamp);
    return date.toLocaleString();
  };

  const downloadCSV = async (type: 'model-cards' | 'accounts' | 'transactions') => {
    try {
      const adminToken = localStorage.getItem('adminToken');
      const headers: Record<string, string> = {};
      if (adminToken) {
        headers['Authorization'] = `Bearer ${adminToken}`;
      }
      const response = await fetch(`http://localhost:8000/api/admin/explorer/${type}/csv`, { headers });
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${type}.csv`;
        a.click();
        toast.success(`${type} exported successfully`);
      }
    } catch (e) {
      toast.error('Export failed');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-cyan-500 mx-auto mb-4" />
          <p className="text-gray-400">Loading Explorer...</p>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'overview' as TabType, label: 'Overview', icon: Activity },
    { id: 'blocks' as TabType, label: 'Blocks', icon: Box },
    { id: 'transactions' as TabType, label: 'Transactions', icon: ArrowUpRight },
    { id: 'accounts' as TabType, label: 'Accounts', icon: Wallet },
    { id: 'contracts' as TabType, label: 'Contracts', icon: Code },
  ];

  return (
    <div className="min-h-screen">
      <header className="bg-gray-800/50 backdrop-blur-xl border-b border-gray-700/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link href="/" className="p-2 hover:bg-gray-700/50 rounded-lg transition-all">
                <Home className="w-5 h-5 text-gray-400" />
              </Link>
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-gray-100 dark:bg-gray-800 rounded-xl shadow-lg shadow-cyan-500/20">
                  <Blocks className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-white">Blockchain Explorer</h1>
                  <p className="text-sm text-gray-400">SMART</p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-green-500/20 rounded-full border border-green-500/30">
                <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
                <span className="text-sm text-green-400">Live</span>
              </div>
              <div className="px-4 py-2 bg-gray-800 rounded-lg border border-gray-700">
                <span className="text-sm text-gray-400">Block #</span>
                <span className="ml-2 font-mono text-cyan-400">{blockchainStats?.block_number || '-'}</span>
              </div>
              <button
                onClick={() => fetchAllData()}
                disabled={refreshing}
                className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-all disabled:opacity-50"
              >
                <RefreshCw className={`w-5 h-5 text-gray-300 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="bg-gray-800/30 border-b border-gray-700/50">
        <div className="max-w-7xl mx-auto px-6">
          <nav className="flex gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-all border-b-2 ${
                  activeTab === tab.id
                    ? 'text-cyan-400 border-cyan-400'
                    : 'text-gray-400 border-transparent hover:text-white hover:border-gray-600'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'overview' && (
          <div className="space-y-8">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <StatCard
                icon={Box}
                label="Latest Block"
                value={blockchainStats?.block_number?.toLocaleString() || '-'}
                color="cyan"
                subtext={`Chain ID: ${blockchainStats?.chain_id || '-'}`}
              />
              <StatCard
                icon={Users}
                label="Total Accounts"
                value={platformStats?.total_accounts?.toString() || '0'}
                color="purple"
                subtext={`${platformStats?.total_users || 0} users registered`}
              />
              <StatCard
                icon={FileCheck}
                label="Model Cards"
                value={platformStats?.total_model_cards?.toString() || '0'}
                color="emerald"
                subtext={`${platformStats?.total_events || 0} lifecycle events`}
              />
              <StatCard
                icon={Activity}
                label="Gas Price"
                value={`${blockchainStats?.gas_price_gwei?.toFixed(2) || '-'}`}
                color="amber"
                subtext="Gwei"
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-gray-800/50 backdrop-blur rounded-2xl border border-gray-700 p-6">
                <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                  <Shield className="w-5 h-5 text-purple-400" />
                  Account Distribution by Role
                </h3>
                <div className="space-y-4">
                  {roleDistribution.map((r, i) => {
                    const total = roleDistribution.reduce((acc, x) => acc + x.count, 0);
                    const percentage = total > 0 ? (r.count / total) * 100 : 0;
                    const colors: Record<string, string> = {
                      'Reader': 'bg-gray-500',
                      'AIDeveloper': 'bg-blue-500',
                      'Reviewer': 'bg-purple-500',
                      'Authenticator': 'bg-purple-500',  // legacy
                      'Publisher': 'bg-emerald-500',
                      'Admin': 'bg-red-500'
                    };
                    return (
                      <div key={i} className="space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-gray-300">{r.role}</span>
                          <span className="text-white font-medium">{r.count} ({percentage.toFixed(1)}%)</span>
                        </div>
                        <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${colors[r.role as keyof typeof colors] || 'bg-gray-500'}`}
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="bg-gray-800/50 backdrop-blur rounded-2xl border border-gray-700 p-6">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                    <Box className="w-5 h-5 text-cyan-400" />
                    Recent Blocks
                  </h3>
                  <button
                    onClick={() => setActiveTab('blocks')}
                    className="text-sm text-cyan-400 hover:text-cyan-300 flex items-center gap-1"
                  >
                    View all <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
                <div className="space-y-3">
                  {blocks.slice(0, 5).map((block, i) => (
                    <div key={i} className="flex items-center justify-between p-3 bg-gray-700/30 rounded-xl hover:bg-gray-700/50 transition-all">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-cyan-500/20 rounded-lg flex items-center justify-center">
                          <Box className="w-5 h-5 text-cyan-400" />
                        </div>
                        <div>
                          <p className="text-white font-mono">#{block.number}</p>
                          <p className="text-sm text-gray-400">{block.transactions} txns</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="text-sm text-gray-400">{formatTimestamp(block.timestamp).split(',')[1]}</p>
                        <p className="text-xs text-gray-500">{((block.gas_used / block.gas_limit) * 100).toFixed(1)}% gas</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="bg-gray-800/50 backdrop-blur rounded-2xl border border-gray-700 p-6">
              <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                <Code className="w-5 h-5 text-orange-400" />
                Deployed Smart Contracts
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {contracts.map((contract, i) => (
                  <div key={i} className="p-4 bg-gray-700/30 rounded-xl border border-gray-600/50 hover:border-cyan-500/50 transition-all">
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-2 bg-orange-500/20 rounded-lg">
                        <FileJson className="w-5 h-5 text-orange-400" />
                      </div>
                      <div>
                        <p className="text-white font-medium">{contract.name}</p>
                        <p className="text-xs text-gray-400">{contract.type}</p>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400 font-mono truncate flex-1">{shortenAddress(contract.address)}</span>
                        <button
                          onClick={() => copyToClipboard(contract.address)}
                          className="p-1 hover:bg-gray-600 rounded transition-all"
                        >
                          {copiedText === contract.address ? <CheckCheck className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3 text-gray-400" />}
                        </button>
                      </div>
                      <p className="text-xs text-gray-500">{contract.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-gray-800/50 backdrop-blur rounded-2xl border border-gray-700 p-6">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Download className="w-5 h-5 text-emerald-400" />
                Export Data
              </h3>
              <p className="text-gray-400 mb-6">Download platform data for analysis</p>
              <div className="flex flex-wrap gap-4">
                <button
                  onClick={() => downloadCSV('model-cards')}
                  className="flex items-center gap-2 px-4 py-2 bg-emerald-600/20 text-emerald-400 border border-emerald-500/50 rounded-lg hover:bg-emerald-600/30 transition-all"
                >
                  <Download className="w-4 h-4" />
                  Model Cards CSV
                </button>
                <button
                  onClick={() => downloadCSV('accounts')}
                  className="flex items-center gap-2 px-4 py-2 bg-purple-600/20 text-purple-400 border border-purple-500/50 rounded-lg hover:bg-purple-600/30 transition-all"
                >
                  <Download className="w-4 h-4" />
                  Accounts CSV
                </button>
                <button
                  onClick={() => downloadCSV('transactions')}
                  className="flex items-center gap-2 px-4 py-2 bg-cyan-600/20 text-cyan-400 border border-cyan-500/50 rounded-lg hover:bg-cyan-600/30 transition-all"
                >
                  <Download className="w-4 h-4" />
                  Transactions CSV
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'blocks' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-white">Recent Blocks</h2>
              <span className="text-sm text-gray-400">{blocks.length} blocks shown</span>
            </div>
            <div className="bg-gray-800/50 backdrop-blur rounded-2xl border border-gray-700 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-700/50">
                    <tr>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Block</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Hash</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Timestamp</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Txns</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Gas Used</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Miner</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {blocks.map((block, i) => (
                      <tr key={i} className="hover:bg-gray-700/30 transition-all">
                        <td className="px-6 py-4">
                          <span className="px-3 py-1 bg-cyan-500/20 text-cyan-400 rounded-lg font-mono text-sm">
                            #{block.number}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-mono text-gray-300">{shortenHash(block.hash)}</span>
                            <button
                              onClick={() => copyToClipboard(block.hash)}
                              className="p-1 hover:bg-gray-600 rounded"
                            >
                              {copiedText === block.hash ? <CheckCheck className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3 text-gray-400" />}
                            </button>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-400">{formatTimestamp(block.timestamp)}</td>
                        <td className="px-6 py-4 text-sm text-white">{block.transactions}</td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-2 bg-gray-700 rounded-full overflow-hidden">
                              <div
                                className="h-full bg-cyan-500 rounded-full"
                                style={{ width: `${(block.gas_used / block.gas_limit) * 100}%` }}
                              />
                            </div>
                            <span className="text-xs text-gray-400">{((block.gas_used / block.gas_limit) * 100).toFixed(1)}%</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 text-sm font-mono text-gray-400">{shortenAddress(block.miner)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'transactions' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-white">Model Card Lifecycle Events</h2>
              <button
                onClick={() => downloadCSV('transactions')}
                className="flex items-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-500 transition-all"
              >
                <Download className="w-4 h-4" />
                Export CSV
              </button>
            </div>
            {transactions.length === 0 ? (
              <div className="bg-gray-800/50 backdrop-blur rounded-2xl border border-gray-700 p-12 text-center">
                <Activity className="w-16 h-16 text-gray-600 mx-auto mb-4" />
                <p className="text-xl text-white mb-2">No Transactions Yet</p>
                <p className="text-gray-400">No lifecycle events yet</p>
              </div>
            ) : (
              <div className="bg-gray-800/50 backdrop-blur rounded-2xl border border-gray-700 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-700/50">
                      <tr>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Token ID</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Model</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Event</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Status Change</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Timestamp</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Tx Hash</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700">
                      {transactions.map((tx, i) => (
                        <tr key={i} className="hover:bg-gray-700/30 transition-all">
                          <td className="px-6 py-4">
                            <Link href={`/model/${tx.token_id}`} className="px-3 py-1 bg-indigo-500/20 text-indigo-400 rounded-lg font-mono text-sm hover:bg-indigo-500/30">
                              #{tx.token_id}
                            </Link>
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-300">{tx.model_name || 'Unnamed'}</td>
                          <td className="px-6 py-4">
                            <span className={`px-2 py-1 text-xs rounded-full ${
                              tx.event_type === 'Created' ? 'bg-emerald-500/20 text-emerald-400' :
                              tx.event_type === 'Published' ? 'bg-blue-500/20 text-blue-400' :
                              'bg-gray-500/20 text-gray-400'
                            }`}>
                              {tx.event_type}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2 text-sm">
                              <span className="text-gray-500">{tx.previous_status || 'N/A'}</span>
                              <ArrowUpRight className="w-3 h-3 text-gray-600" />
                              <span className="text-cyan-400">{tx.new_status}</span>
                            </div>
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-400">{formatTimestamp(tx.timestamp)}</td>
                          <td className="px-6 py-4">
                            {tx.tx_hash ? (
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-mono text-gray-300">{shortenHash(tx.tx_hash)}</span>
                                <button
                                  onClick={() => copyToClipboard(tx.tx_hash)}
                                  className="p-1 hover:bg-gray-600 rounded"
                                >
                                  {copiedText === tx.tx_hash ? <CheckCheck className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3 text-gray-400" />}
                                </button>
                              </div>
                            ) : (
                              <span className="text-gray-500">-</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'accounts' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-white">Custom Accounts</h2>
              <button
                onClick={() => downloadCSV('accounts')}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-500 transition-all"
              >
                <Download className="w-4 h-4" />
                Export CSV
              </button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              {roleDistribution.map((r, i) => (
                <div key={i} className="bg-gray-800/50 rounded-xl border border-gray-700 p-4">
                  <p className="text-sm text-gray-400">{r.role}</p>
                  <p className="text-2xl font-bold text-white">{r.count}</p>
                </div>
              ))}
            </div>
            <div className="bg-gray-800/50 backdrop-blur rounded-2xl border border-gray-700 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-700/50">
                    <tr>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Account Address</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Role</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">EOA Address</th>
                      <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">User UUID</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {accounts.map((account, i) => (
                      <tr key={i} className="hover:bg-gray-700/30 transition-all">
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 bg-gray-100 dark:bg-gray-800 rounded-lg flex items-center justify-center">
                              <Wallet className="w-4 h-4 text-white" />
                            </div>
                            <span className="text-sm font-mono text-gray-300">{shortenAddress(account.account_address)}</span>
                            <button
                              onClick={() => copyToClipboard(account.account_address)}
                              className="p-1 hover:bg-gray-600 rounded"
                            >
                              {copiedText === account.account_address ? <CheckCheck className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3 text-gray-400" />}
                            </button>
                          </div>
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-2 py-1 text-xs rounded-full ${
                            account.role === 'AIDeveloper' ? 'bg-blue-500/20 text-blue-400' :
                            (account.role === 'Reviewer' || account.role === 'Authenticator') ? 'bg-purple-500/20 text-purple-400' :
                            account.role === 'Publisher' ? 'bg-emerald-500/20 text-emerald-400' :
                            'bg-gray-500/20 text-gray-400'
                          }`}>
                            {account.role}
                          </span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm font-mono text-gray-400">{shortenAddress(account.eoa_address)}</span>
                        </td>
                        <td className="px-6 py-4">
                          <span className="text-sm font-mono text-gray-500">{account.user_uuid.slice(0, 8)}...</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'contracts' && (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold text-white">Deployed Smart Contracts</h2>
            <div className="grid grid-cols-1 gap-6">
              {contracts.map((contract, i) => (
                <div key={i} className="bg-gray-800/50 backdrop-blur rounded-2xl border border-gray-700 p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-4">
                      <div className="p-3 bg-orange-500/20 rounded-xl">
                        <Code className="w-8 h-8 text-orange-400" />
                      </div>
                      <div>
                        <h3 className="text-xl font-semibold text-white">{contract.name}</h3>
                        <p className="text-gray-400">{contract.type}</p>
                      </div>
                    </div>
                    <span className="px-3 py-1 bg-green-500/20 text-green-400 rounded-full text-sm">Deployed</span>
                  </div>
                  <p className="text-gray-400 mb-4">{contract.description}</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-4 bg-gray-700/30 rounded-xl">
                      <p className="text-sm text-gray-400 mb-1">Contract Address</p>
                      <div className="flex items-center gap-2">
                        <code className="text-cyan-400 font-mono text-sm break-all">{contract.address}</code>
                        <button
                          onClick={() => copyToClipboard(contract.address)}
                          className="p-1 hover:bg-gray-600 rounded flex-shrink-0"
                        >
                          {copiedText === contract.address ? <CheckCheck className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4 text-gray-400" />}
                        </button>
                      </div>
                    </div>
                    <div className="p-4 bg-gray-700/30 rounded-xl">
                      <p className="text-sm text-gray-400 mb-1">Balance</p>
                      <p className="text-white font-mono">{contract.balance} ETH</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      <footer className="border-t border-gray-700/50 mt-12">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between text-sm text-gray-500">
            <p>SMART - Blockchain Explorer</p>
            <p>Chain ID: {blockchainStats?.chain_id} | Block #{blockchainStats?.block_number}</p>
          </div>
        </div>
      </footer>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
  subtext
}: {
  icon: any;
  label: string;
  value: string;
  color: string;
  subtext?: string;
}) {
  const colors = {
    cyan: 'from-cyan-500 to-cyan-600',
    purple: 'from-purple-500 to-purple-600',
    emerald: 'from-emerald-500 to-emerald-600',
    amber: 'from-amber-500 to-amber-600',
  };

  return (
    <div className="bg-gray-800/50 backdrop-blur rounded-2xl border border-gray-700 p-6">
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-xl bg-gray-100 dark:bg-gray-800`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
        <div>
          <p className="text-sm text-gray-400">{label}</p>
          <p className="text-2xl font-bold text-white">{value}</p>
          {subtext && <p className="text-xs text-gray-500">{subtext}</p>}
        </div>
      </div>
    </div>
  );
}
