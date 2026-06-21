'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Shield,
  Users,
  FileCheck,
  Clock,
  CheckCircle2,
  XCircle,
  LogOut,
  Loader2,
  BarChart3,
  AlertCircle,
  Database,
  HardDrive,
  Blocks,
  Settings,
  Home,
  ChevronRight,
  Search,
  RefreshCw,
  Eye,
  FileJson,
  Folder,
  Terminal,
  Activity,
  Trash2,
  AlertTriangle,
  Server,
  Network,
  Box,
  Link as LinkIcon,
  Hash,
  Wallet,
  Key,
  ExternalLink,
  Copy,
  CheckCheck,
  RotateCcw,
  Globe,
  Gavel,
  Award
} from 'lucide-react';
import { toast } from 'sonner';
import { IdentityDisputesTab } from '@/components/admin/IdentityDisputesTab';
import { ClaimRequestsTab } from '@/components/admin/ClaimRequestsTab';
import { SplitVotesTab } from '@/components/admin/SplitVotesTab';
import { AssignPanelTab } from '@/components/admin/AssignPanelTab';

interface RoleRequest {
  request_id: string;
  uuid: string;
  eoa_address: string;
  luceid: string;
  requested_role: string;
  reason: string;
  created_at: string;
}

interface PlatformStats {
  total_users: number;
  total_model_cards: number;
  pending_role_requests: number;
  role_distribution: Array<{ role: string; count: number }>;
}

interface User {
  uuid: string;
  eoa_address: string;
  luceid: string;
  verified: boolean;
  roles: string[];
}

interface Neo4jSchema {
  labels: string[];
  relationships: string[];
  node_counts: Record<string, number>;
}

interface MinioBucket {
  name: string;
  creation_date: string;
  object_count: number;
}

interface MinioObject {
  name: string;
  size: number;
  last_modified: string;
  content_type: string;
}

interface BlockchainStatus {
  connected: boolean;
  chain_id: number;
  block_number: number;
  gas_price: string;
  provider: string;
}

type TabType = 'dashboard' | 'users' | 'role-requests' | 'model-cards' | 'identity-disputes' | 'claim-requests' | 'assign-panel' | 'split-votes' | 'neo4j' | 'minio' | 'blockchain';

export default function AdminDashboard() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [copiedText, setCopiedText] = useState<string | null>(null);

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');

  const [requests, setRequests] = useState<RoleRequest[]>([]);
  const [failedRequests, setFailedRequests] = useState<RoleRequest[]>([]);
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [neo4jSchema, setNeo4jSchema] = useState<Neo4jSchema | null>(null);
  const [neo4jQuery, setNeo4jQuery] = useState('MATCH (n) RETURN labels(n) as labels, count(*) as count');
  const [neo4jResults, setNeo4jResults] = useState<any[]>([]);
  const [minioBuckets, setMinioBuckets] = useState<MinioBucket[]>([]);
  const [minioObjects, setMinioObjects] = useState<MinioObject[]>([]);
  const [selectedBucket, setSelectedBucket] = useState<string>('');
  const [blockchainStatus, setBlockchainStatus] = useState<BlockchainStatus | null>(null);
  const [modelCards, setModelCards] = useState<any[]>([]);
  const [selectedObjectContent, setSelectedObjectContent] = useState<any>(null);

  const predefinedQueries = [
    { label: 'All Users', query: 'MATCH (u:User) RETURN u.uuid, u.eoa_address, u.luceid, u.verified ORDER BY u.created_at DESC' },
    { label: 'Users with Roles', query: 'MATCH (u:User)-[:HAS_ROLE]->(r:Role) RETURN u.uuid, u.eoa_address, collect(r.name) as roles' },
    { label: 'All Model Cards', query: 'MATCH (mc:ModelCard) RETURN mc.token_id, mc.model_name, mc.current_status, mc.blockchain_address' },
    { label: 'Role Requests', query: 'MATCH (u:User)-[:HAS_ROLE_REQUEST]->(rr:RoleRequest) RETURN u.uuid, rr.requested_role, rr.status, rr.created_at' },
    { label: 'Custom Accounts', query: 'MATCH (u:User)-[:HAS_CUSTOM_ACCOUNT]->(ca:CustomAccount) RETURN u.uuid, ca.address, ca.role' },
    { label: 'Model Events', query: 'MATCH (mc:ModelCard)-[:HAS_EVENT]->(e:StatusEvent) RETURN mc.token_id, e.event_type, e.timestamp' },
  ];

  const isTokenValid = (token: string): boolean => {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) return false;

      const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));

      if (payload.exp && Date.now() >= payload.exp * 1000) {
        return false;
      }

      if (payload.type !== 'admin_access') {
        return false;
      }

      return true;
    } catch (e) {
      console.error('Token validation error:', e);
      return false;
    }
  };

  const getAuthHeaders = (): HeadersInit => {
    const token = localStorage.getItem('adminToken');
    return {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {})
    };
  };

  useEffect(() => {
    const token = localStorage.getItem('adminToken');
    if (token && isTokenValid(token)) {
      setIsAuthenticated(true);
      fetchAllData();
    } else if (token) {
      localStorage.removeItem('adminToken');
    }
    setLoading(false);
  }, []);

  const fetchAllData = async () => {
    await Promise.all([
      fetchStats(),
      fetchRequests(),
      fetchFailedRequests(),
      fetchUsers(),
      fetchNeo4jSchema(),
      fetchMinioBuckets(),
      fetchBlockchainStatus(),
      fetchModelCards()
    ]);
  };

  const fetchStats = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/admin/stats', {
        headers: getAuthHeaders()
      });
      if (res.ok) setStats(await res.json());
    } catch (e) { console.error('Failed to fetch stats:', e); }
  };

  const fetchRequests = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/admin/role-requests', {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setRequests(data.requests || []);
      }
    } catch (e) { console.error('Failed to fetch requests:', e); }
  };

  const fetchFailedRequests = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/admin/role-requests/failed', {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setFailedRequests(data.requests || []);
      }
    } catch (e) { console.error('Failed to fetch failed requests:', e); }
  };

  const retryRoleRequest = async (requestId: string) => {
    setActionLoading(requestId);
    try {
      const res = await fetch(`http://localhost:8000/api/admin/role-requests/${requestId}/retry`, {
        method: 'POST',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        toast.success(`Blockchain account created: ${data.account_address.slice(0, 10)}...`);
        fetchFailedRequests();
        fetchUsers();
        fetchStats();
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Retry failed');
      }
    } catch (e) {
      toast.error('Failed to retry');
    } finally {
      setActionLoading(null);
    }
  };

  const fetchUsers = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/admin/users', {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setUsers(data.users || []);
      }
    } catch (e) { console.error('Failed to fetch users:', e); }
  };

  const fetchNeo4jSchema = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/admin/neo4j/schema', {
        headers: getAuthHeaders()
      });
      if (res.ok) setNeo4jSchema(await res.json());
    } catch (e) { console.error('Failed to fetch schema:', e); }
  };

  const fetchMinioBuckets = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/admin/minio/buckets', {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setMinioBuckets(data.buckets || []);
      }
    } catch (e) { console.error('Failed to fetch buckets:', e); }
  };

  const fetchMinioObjects = async (bucket: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/admin/minio/objects/${bucket}`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setMinioObjects(data.objects || []);
      }
    } catch (e) { console.error('Failed to fetch objects:', e); }
  };

  const fetchObjectContent = async (bucket: string, path: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/admin/minio/object/${bucket}/${path}`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setSelectedObjectContent(data);
      }
    } catch (e) {
      toast.error('Failed to fetch object content');
    }
  };

  const fetchBlockchainStatus = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/admin/blockchain/status', {
        headers: getAuthHeaders()
      });
      if (res.ok) setBlockchainStatus(await res.json());
    } catch (e) { console.error('Failed to fetch blockchain status:', e); }
  };

  const fetchModelCards = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/admin/model-cards', {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setModelCards(data.model_cards || []);
      }
    } catch (e) { console.error('Failed to fetch model cards:', e); }
  };

  const runNeo4jQuery = async () => {
    setActionLoading('neo4j');
    try {
      const res = await fetch(`http://localhost:8000/api/admin/neo4j/query?query=${encodeURIComponent(neo4jQuery)}`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setNeo4jResults(data.results || []);
        toast.success(`Query returned ${data.count} results`);
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Query failed');
      }
    } catch (e) {
      toast.error('Failed to run query');
    } finally {
      setActionLoading(null);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError('');
    setLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });

      if (!response.ok) throw new Error('Invalid credentials');

      const data = await response.json();
      localStorage.setItem('adminToken', data.token);
      setIsAuthenticated(true);
      toast.success('Welcome to Admin Portal');
      fetchAllData();
    } catch (error) {
      setLoginError('Invalid username or password');
      toast.error('Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('adminToken');
    setIsAuthenticated(false);
    toast.success('Logged out');
  };

  const handleApproval = async (requestId: string, approved: boolean) => {
    setActionLoading(requestId);
    try {
      const response = await fetch(`http://localhost:8000/api/admin/role-requests/${requestId}/approve`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ request_id: requestId, approved, admin_notes: approved ? 'Approved by admin' : 'Rejected by admin' })
      });
      if (response.ok) {
        toast.success(approved ? 'Role approved and blockchain account created!' : 'Role request rejected');
        fetchRequests();
        fetchStats();
        fetchUsers();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to process request');
      }
    } catch (e) {
      toast.error('Failed to process request');
    } finally {
      setActionLoading(null);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(text);
    setTimeout(() => setCopiedText(null), 2000);
  };

  const shortenAddress = (address: string) => {
    if (!address) return '-';
    return `${address.slice(0, 8)}...${address.slice(-6)}`;
  };

  if (loading) {
    return (
      <div className="dark min-h-screen flex items-center justify-center bg-gray-950">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="dark min-h-screen flex items-center justify-center p-4 bg-gray-950 text-gray-100">
        <div className="w-full max-w-md">
          <div className="bg-gray-800/50 backdrop-blur-xl rounded-2xl shadow-2xl p-8 border border-gray-700">
            <div className="text-center mb-8">
              <div className="inline-flex items-center justify-center w-20 h-20 bg-gray-100 dark:bg-gray-800 rounded-2xl mb-4 shadow-lg">
                <Shield className="w-10 h-10 text-white" />
              </div>
              <h1 className="text-3xl font-bold text-white">Admin Portal</h1>
              <p className="text-gray-400 mt-2">Platform Management Console</p>
            </div>

            <form onSubmit={handleLogin} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  className="w-full px-4 py-3 rounded-xl border border-gray-600 bg-gray-700/50 text-white placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="********"
                  className="w-full px-4 py-3 rounded-xl border border-gray-600 bg-gray-700/50 text-white placeholder-gray-400 focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                  required
                />
              </div>

              {loginError && (
                <div className="p-3 rounded-lg bg-red-500/20 border border-red-500/50 text-red-400 text-sm flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />
                  {loginError}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 text-white font-semibold rounded-xl hover:bg-gray-700 dark:hover:bg-gray-200 transition-all shadow-lg disabled:opacity-50"
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin mx-auto" /> : 'Sign In'}
              </button>

              <div className="text-center text-sm text-gray-500">
                SMART Admin Portal - Contact system administrator for credentials
              </div>
            </form>

            <div className="mt-6 pt-6 border-t border-gray-700 text-center">
              <Link href="/" className="text-indigo-400 hover:text-indigo-300 text-sm">
                &larr; Back to Platform
              </Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const sidebarItems = [
    { id: 'dashboard' as TabType, icon: Home, label: 'Overview', desc: 'System status' },
    { id: 'users' as TabType, icon: Users, label: 'Users', desc: `${users.length} registered` },
    { id: 'role-requests' as TabType, icon: Clock, label: 'Role Requests', badge: requests.length, desc: 'Approval queue' },
    { id: 'model-cards' as TabType, icon: FileCheck, label: 'Model Cards', desc: `${modelCards.length} created` },
    { id: 'identity-disputes' as TabType, icon: Gavel, label: 'Identity Disputes', desc: 'Arbiter queue' },
    { id: 'assign-panel' as TabType, icon: Gavel, label: 'Assign Panel', desc: 'Pick Reviewer + Publisher for open disputes' },
    { id: 'split-votes' as TabType, icon: Gavel, label: 'Split Votes', desc: 'Panels that disagreed' },
    { id: 'claim-requests' as TabType, icon: Award, label: 'Claim Requests', desc: 'Institutional upgrades' },
    { id: 'neo4j' as TabType, icon: Database, label: 'Neo4j', desc: 'Graph database' },
    { id: 'minio' as TabType, icon: HardDrive, label: 'MinIO', desc: 'Object storage' },
    { id: 'blockchain' as TabType, icon: Blocks, label: 'Blockchain', desc: 'Hardhat node' },
  ];

  return (
    <div className="dark min-h-screen flex bg-gray-950 text-gray-100">
      <aside className="w-72 bg-gray-800/50 backdrop-blur-xl border-r border-gray-700 flex flex-col">
        <div className="p-6 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-gray-100 dark:bg-gray-800 rounded-xl shadow-lg shadow-indigo-500/20">
              <Shield className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white">Admin Portal</h1>
              <p className="text-xs text-gray-400">SMART</p>
            </div>
          </div>
        </div>

        <div className="px-4 py-3 mx-4 mt-4 rounded-xl bg-gray-700/30 border border-gray-600/50">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-400 uppercase font-medium">System Status</span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
              <span className="text-xs text-green-400">Online</span>
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-lg font-bold text-white">{neo4jSchema?.node_counts?.['User'] || 0}</p>
              <p className="text-[10px] text-gray-500">Neo4j Users</p>
            </div>
            <div>
              <p className="text-lg font-bold text-white">{minioBuckets.reduce((acc, b) => acc + b.object_count, 0)}</p>
              <p className="text-[10px] text-gray-500">S3 Objects</p>
            </div>
            <div>
              <p className="text-lg font-bold text-white">{blockchainStatus?.block_number || '-'}</p>
              <p className="text-[10px] text-gray-500">Block #</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-4 space-y-1 mt-2">
          {sidebarItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center justify-between px-4 py-3 rounded-xl text-left transition-all ${
                activeTab === item.id
                  ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20'
                  : 'text-gray-400 hover:bg-gray-700/50 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-3">
                <item.icon className="w-5 h-5" />
                <div>
                  <span className="font-medium block">{item.label}</span>
                  <span className="text-xs opacity-60">{item.desc}</span>
                </div>
              </div>
              {item.badge !== undefined && item.badge > 0 && (
                <span className="px-2 py-0.5 text-xs bg-red-500 text-white rounded-full animate-pulse">
                  {item.badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-gray-700">
          <Link
            href="/"
            className="flex items-center gap-3 px-4 py-3 text-gray-400 hover:text-white hover:bg-gray-700/50 rounded-xl transition-all"
          >
            <Eye className="w-5 h-5" />
            <span>View Platform</span>
          </Link>
          <Link
            href="/explorer"
            className="flex items-center gap-3 px-4 py-3 text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10 rounded-xl transition-all"
          >
            <Globe className="w-5 h-5" />
            <span>Blockchain Explorer</span>
          </Link>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-3 px-4 py-3 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-xl transition-all mt-1"
          >
            <LogOut className="w-5 h-5" />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <header className="bg-gray-800/30 backdrop-blur-xl border-b border-gray-700/50 px-8 py-4 sticky top-0 z-10">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-white capitalize">
                {activeTab === 'dashboard' ? 'Platform Overview' : activeTab.replace('-', ' ')}
              </h2>
            </div>
            <button
              onClick={fetchAllData}
              className="flex items-center gap-2 px-4 py-2 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-all"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh All
            </button>
          </div>
        </header>

        <div className="p-8">
          {activeTab === 'dashboard' && (
            <div className="space-y-8">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div
                  className="surface p-6 cursor-pointer hover:border-[var(--fg-faint)] transition-all group"
                  onClick={() => setActiveTab('neo4j')}
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="p-3 rounded-xl bg-blue-500/20">
                      <Database className="w-6 h-6 text-blue-400" />
                    </div>
                    <span className="flex items-center gap-1.5 text-xs text-green-400">
                      <span className="w-2 h-2 rounded-full bg-green-400"></span>
                      Connected
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-1">Neo4j Database</h3>
                  <p className="text-sm text-gray-400 mb-4">Graph data store</p>
                  <div className="grid grid-cols-3 gap-2 pt-4 border-t border-gray-700">
                    <div>
                      <p className="text-xl font-bold text-white">{neo4jSchema?.labels?.length || 0}</p>
                      <p className="text-xs text-gray-500">Labels</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold text-white">{neo4jSchema?.relationships?.length || 0}</p>
                      <p className="text-xs text-gray-500">Rel Types</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold text-white">{Object.values(neo4jSchema?.node_counts || {}).reduce((a, b) => a + b, 0)}</p>
                      <p className="text-xs text-gray-500">Nodes</p>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t border-gray-700">
                    <p className="text-xs text-gray-500 mb-2">Node Distribution</p>
                    <div className="flex flex-wrap gap-1">
                      {Object.entries(neo4jSchema?.node_counts || {}).slice(0, 5).map(([label, count]) => (
                        <span key={label} className="px-2 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded-full">
                          {label}: {count}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div
                  className="surface p-6 cursor-pointer hover:border-[var(--fg-faint)] transition-all group"
                  onClick={() => setActiveTab('minio')}
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="p-3 rounded-xl bg-amber-500/20">
                      <HardDrive className="w-6 h-6 text-amber-400" />
                    </div>
                    <span className="flex items-center gap-1.5 text-xs text-green-400">
                      <span className="w-2 h-2 rounded-full bg-green-400"></span>
                      Connected
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-1">MinIO Storage</h3>
                  <p className="text-sm text-gray-400 mb-4">S3-compatible storage</p>
                  <div className="grid grid-cols-2 gap-2 pt-4 border-t border-gray-700">
                    <div>
                      <p className="text-xl font-bold text-white">{minioBuckets.length}</p>
                      <p className="text-xs text-gray-500">Buckets</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold text-white">{minioBuckets.reduce((acc, b) => acc + b.object_count, 0)}</p>
                      <p className="text-xs text-gray-500">Objects</p>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t border-gray-700">
                    <p className="text-xs text-gray-500 mb-2">Buckets</p>
                    <div className="flex flex-wrap gap-1">
                      {minioBuckets.map((bucket) => (
                        <span key={bucket.name} className="px-2 py-0.5 text-xs bg-amber-500/20 text-amber-400 rounded-full">
                          {bucket.name}: {bucket.object_count}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div
                  className="surface p-6 cursor-pointer hover:border-[var(--fg-faint)] transition-all group"
                  onClick={() => setActiveTab('blockchain')}
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="p-3 rounded-xl bg-orange-500/20">
                      <Blocks className="w-6 h-6 text-orange-400" />
                    </div>
                    <span className={`flex items-center gap-1.5 text-xs ${blockchainStatus?.connected ? 'text-green-400' : 'text-red-400'}`}>
                      <span className={`w-2 h-2 rounded-full ${blockchainStatus?.connected ? 'bg-green-400' : 'bg-red-400'}`}></span>
                      {blockchainStatus?.connected ? 'Connected' : 'Disconnected'}
                    </span>
                  </div>
                  <h3 className="text-lg font-semibold text-white mb-1">Blockchain</h3>
                  <p className="text-sm text-gray-400 mb-4">Hardhat Ethereum node</p>
                  <div className="grid grid-cols-2 gap-2 pt-4 border-t border-gray-700">
                    <div>
                      <p className="text-xl font-bold text-white">{blockchainStatus?.chain_id || '-'}</p>
                      <p className="text-xs text-gray-500">Chain ID</p>
                    </div>
                    <div>
                      <p className="text-xl font-bold text-white">{blockchainStatus?.block_number || '-'}</p>
                      <p className="text-xs text-gray-500">Block #</p>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t border-gray-700">
                    <p className="text-xs text-gray-500 mb-1">Provider</p>
                    <p className="text-xs font-mono text-orange-400 truncate">{blockchainStatus?.provider || '-'}</p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <StatCard
                  icon={Users}
                  label="Registered Users"
                  value={stats?.total_users || 0}
                  color="blue"
                  onClick={() => setActiveTab('users')}
                  subtext={`${users.filter(u => u.verified).length} verified`}
                />
                <StatCard
                  icon={FileCheck}
                  label="Model Cards"
                  value={stats?.total_model_cards || 0}
                  color="green"
                  onClick={() => setActiveTab('model-cards')}
                  subtext="Total created"
                />
                <StatCard
                  icon={Clock}
                  label="Pending Requests"
                  value={requests.length}
                  color="amber"
                  onClick={() => setActiveTab('role-requests')}
                  subtext={requests.length > 0 ? 'Needs attention' : 'All processed'}
                  highlight={requests.length > 0}
                />
                <StatCard
                  icon={Activity}
                  label="Custom Accounts"
                  value={neo4jSchema?.node_counts?.['CustomAccount'] || 0}
                  color="purple"
                  subtext="Blockchain accounts"
                />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <BarChart3 className="w-5 h-5 text-indigo-400" />
                    Role Distribution
                  </h3>
                  <div className="space-y-3">
                    {stats?.role_distribution?.filter(r => r.role).map((r, i) => (
                      <div key={i} className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span className={`w-3 h-3 rounded-full ${
                            r.role === 'AIDeveloper' ? 'bg-blue-400' :
                            r.role === 'Reader' ? 'bg-gray-400' :
                            (r.role === 'Reviewer' || r.role === 'Authenticator') ? 'bg-purple-400' :
                            r.role === 'Publisher' ? 'bg-emerald-400' : 'bg-gray-400'
                          }`}></span>
                          <span className="text-gray-300">{r.role}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="w-32 h-2 bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                r.role === 'AIDeveloper' ? 'bg-blue-400' :
                                r.role === 'Reader' ? 'bg-gray-400' :
                                (r.role === 'Reviewer' || r.role === 'Authenticator') ? 'bg-purple-400' :
                                r.role === 'Publisher' ? 'bg-emerald-400' : 'bg-gray-400'
                              }`}
                              style={{ width: `${Math.min(100, (r.count / (stats?.total_users || 1)) * 100)}%` }}
                            ></div>
                          </div>
                          <span className="text-white font-medium w-8 text-right">{r.count}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                      <Clock className="w-5 h-5 text-amber-400" />
                      Pending Requests
                    </h3>
                    {requests.length > 0 && (
                      <button
                        onClick={() => setActiveTab('role-requests')}
                        className="text-sm text-indigo-400 hover:text-indigo-300"
                      >
                        View all &rarr;
                      </button>
                    )}
                  </div>
                  {requests.length === 0 ? (
                    <div className="text-center py-8">
                      <CheckCircle2 className="w-12 h-12 text-green-500 mx-auto mb-3" />
                      <p className="text-gray-400">All requests processed</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {requests.slice(0, 3).map((req) => (
                        <div key={req.request_id} className="p-3 bg-gray-700/50 rounded-xl flex items-center justify-between">
                          <div>
                            <span className={`px-2 py-0.5 text-xs rounded-full ${
                              (req.requested_role === 'Reviewer' || req.requested_role === 'Authenticator')
                                ? 'bg-purple-500/20 text-purple-400'
                                : 'bg-emerald-500/20 text-emerald-400'
                            }`}>
                              {req.requested_role}
                            </span>
                            <p className="text-sm text-gray-400 mt-1 font-mono">{shortenAddress(req.eoa_address)}</p>
                          </div>
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleApproval(req.request_id, false)}
                              className="p-2 text-red-400 hover:bg-red-500/20 rounded-lg transition-all"
                            >
                              <XCircle className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleApproval(req.request_id, true)}
                              className="p-2 text-green-400 hover:bg-green-500/20 rounded-lg transition-all"
                            >
                              <CheckCircle2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Network className="w-5 h-5 text-cyan-400" />
                  Data Relationships (Neo4j Graph)
                </h3>
                <div className="flex flex-wrap gap-4">
                  {neo4jSchema?.relationships.map((rel, i) => (
                    <div key={i} className="flex items-center gap-2 px-4 py-2 bg-gray-700/50 rounded-xl">
                      <span className="text-gray-400">(:Node)</span>
                      <span className="text-cyan-400 font-mono text-sm">-[:{rel}]-&gt;</span>
                      <span className="text-gray-400">(:Node)</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'users' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                  <p className="text-sm text-gray-400">Total Users</p>
                  <p className="text-2xl font-bold text-white">{users.length}</p>
                </div>
                <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                  <p className="text-sm text-gray-400">Verified</p>
                  <p className="text-2xl font-bold text-green-400">{users.filter(u => u.verified).length}</p>
                </div>
                <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                  <p className="text-sm text-gray-400">AI Developers</p>
                  <p className="text-2xl font-bold text-blue-400">{users.filter(u => u.roles?.includes('AIDeveloper')).length}</p>
                </div>
                <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                  <p className="text-sm text-gray-400">Reviewers</p>
                  <p className="text-2xl font-bold text-purple-400">{users.filter(u => u.roles?.includes('Reviewer') || u.roles?.includes('Authenticator')).length}</p>
                </div>
              </div>

              <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-700/50">
                      <tr>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">User</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">EOA Address</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Roles</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Status</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700">
                      {users.map((user, i) => (
                        <tr key={i} className="hover:bg-gray-700/30">
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                                <Wallet className="w-5 h-5 text-white" />
                              </div>
                              <div>
                                <p className="text-sm font-mono text-gray-300 truncate max-w-[200px]">{user.uuid.slice(0, 8)}...</p>
                                <p className="text-xs text-gray-500">UUID</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-mono text-gray-300">{shortenAddress(user.eoa_address)}</span>
                              <button
                                onClick={() => copyToClipboard(user.eoa_address)}
                                className="p-1 text-gray-500 hover:text-white transition-colors"
                              >
                                {copiedText === user.eoa_address ? <CheckCheck className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                              </button>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex flex-wrap gap-1">
                              {user.roles?.map((role, j) => (
                                <span key={j} className={`px-2 py-1 text-xs rounded-full ${
                                  role === 'AIDeveloper' ? 'bg-blue-500/20 text-blue-400' :
                                  (role === 'Reviewer' || role === 'Authenticator') ? 'bg-purple-500/20 text-purple-400' :
                                  role === 'Publisher' ? 'bg-emerald-500/20 text-emerald-400' :
                                  'bg-gray-500/20 text-gray-400'
                                }`}>
                                  {role}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`px-2 py-1 text-xs rounded-full ${user.verified ? 'bg-green-500/20 text-green-400' : 'bg-amber-500/20 text-amber-400'}`}>
                              {user.verified ? 'Verified' : 'Pending'}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <button
                              onClick={() => {
                                setNeo4jQuery(`MATCH (u:User {uuid: '${user.uuid}'})-[r]->(n) RETURN type(r) as relationship, labels(n) as connected_to, n`);
                                setActiveTab('neo4j');
                              }}
                              className="text-xs text-indigo-400 hover:text-indigo-300"
                            >
                              View in Neo4j
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'role-requests' && (
            <div className="space-y-4">
              {requests.length === 0 ? (
                <div className="bg-gray-800 rounded-2xl border border-gray-700 p-12 text-center">
                  <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
                  <p className="text-xl text-white mb-2">All Caught Up!</p>
                  <p className="text-gray-400">No pending role requests</p>
                </div>
              ) : (
                requests.map((request) => (
                  <div key={request.request_id} className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                    <div className="flex items-start justify-between gap-6">
                      <div className="flex-1 space-y-4">
                        <div className="flex items-center gap-3">
                          <span className={`px-4 py-1.5 rounded-full text-sm font-semibold ${
                            (request.requested_role === 'Reviewer' || request.requested_role === 'Authenticator')
                              ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50'
                              : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50'
                          }`}>
                            {request.requested_role}
                          </span>
                          <span className="text-sm text-gray-500">Request ID: {request.request_id.slice(0, 12)}...</span>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                          <div>
                            <p className="text-gray-500 mb-1">User UUID</p>
                            <p className="font-mono text-gray-300 truncate">{request.uuid}</p>
                          </div>
                          <div>
                            <p className="text-gray-500 mb-1">EOA Address</p>
                            <div className="flex items-center gap-2">
                              <p className="font-mono text-gray-300">{shortenAddress(request.eoa_address)}</p>
                              <button
                                onClick={() => copyToClipboard(request.eoa_address)}
                                className="p-1 text-gray-500 hover:text-white"
                              >
                                {copiedText === request.eoa_address ? <CheckCheck className="w-3 h-3 text-green-400" /> : <Copy className="w-3 h-3" />}
                              </button>
                            </div>
                          </div>
                          <div>
                            <p className="text-gray-500 mb-1">Submitted</p>
                            <p className="text-gray-300">{new Date(request.created_at).toLocaleDateString()}</p>
                          </div>
                        </div>
                        {request.reason && (
                          <div className="p-3 bg-gray-700/50 rounded-xl">
                            <p className="text-gray-500 text-xs mb-1">Reason</p>
                            <p className="text-gray-300">{request.reason}</p>
                          </div>
                        )}
                        <div className="text-xs text-gray-500">
                          Approving will create a new blockchain account with {request.requested_role} role
                        </div>
                      </div>
                      <div className="flex gap-3">
                        <button
                          onClick={() => handleApproval(request.request_id, false)}
                          disabled={actionLoading === request.request_id}
                          className="flex items-center gap-2 px-5 py-2.5 border border-red-500/50 text-red-400 rounded-xl hover:bg-red-500/10 transition-all disabled:opacity-50"
                        >
                          {actionLoading === request.request_id ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                          Reject
                        </button>
                        <button
                          onClick={() => handleApproval(request.request_id, true)}
                          disabled={actionLoading === request.request_id}
                          className="flex items-center gap-2 px-5 py-2.5 bg-green-600 text-white rounded-xl hover:bg-green-500 transition-all disabled:opacity-50"
                        >
                          {actionLoading === request.request_id ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                          Approve
                        </button>
                      </div>
                    </div>
                  </div>
                ))
              )}

              {failedRequests.length > 0 && (
                <div className="mt-8">
                  <h3 className="text-lg font-semibold text-amber-400 mb-4 flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5" />
                    Failed Blockchain Account Creation ({failedRequests.length})
                  </h3>
                  <p className="text-gray-400 text-sm mb-4">These requests were approved but blockchain account creation failed. Click retry to create the account.</p>
                  <div className="space-y-3">
                    {failedRequests.map((request) => (
                      <div key={request.request_id} className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                              (request.requested_role === 'Reviewer' || request.requested_role === 'Authenticator')
                                ? 'bg-purple-500/20 text-purple-400'
                                : 'bg-emerald-500/20 text-emerald-400'
                            }`}>
                              {request.requested_role}
                            </span>
                            <span className="text-gray-400 font-mono text-sm">{shortenAddress(request.eoa_address)}</span>
                            <span className="text-gray-500 text-sm">{request.uuid.slice(0, 8)}...</span>
                          </div>
                          <button
                            onClick={() => retryRoleRequest(request.request_id)}
                            disabled={actionLoading === request.request_id}
                            className="flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-500 transition-all disabled:opacity-50"
                          >
                            {actionLoading === request.request_id ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <RotateCcw className="w-4 h-4" />
                            )}
                            Retry
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'model-cards' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                  <p className="text-sm text-gray-400">Total Cards</p>
                  <p className="text-2xl font-bold text-white">{modelCards.length}</p>
                </div>
                <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                  <p className="text-sm text-gray-400">In Neo4j</p>
                  <p className="text-2xl font-bold text-blue-400">{neo4jSchema?.node_counts?.['ModelCard'] || 0}</p>
                </div>
                <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                  <p className="text-sm text-gray-400">In MinIO</p>
                  <p className="text-2xl font-bold text-amber-400">{minioBuckets.find(b => b.name === 'model-cards')?.object_count || 0}</p>
                </div>
              </div>

              <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-gray-700/50">
                      <tr>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Token ID</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Model Name</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Status</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Organization</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Events</th>
                        <th className="px-6 py-4 text-left text-xs font-semibold text-gray-400 uppercase">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-700">
                      {modelCards.map((mc, i) => (
                        <tr key={i} className="hover:bg-gray-700/30">
                          <td className="px-6 py-4">
                            <span className="px-3 py-1 bg-indigo-500/20 text-indigo-400 rounded-lg font-mono text-sm">
                              #{mc.token_id}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-300">{mc.model_name || 'Unnamed'}</td>
                          <td className="px-6 py-4">
                            <span className={`px-2 py-1 text-xs rounded-full ${
                              mc.status === 'Draft' ? 'bg-gray-500/20 text-gray-400' :
                              mc.status === 'Published' ? 'bg-green-500/20 text-green-400' :
                              mc.status === 'InReview' ? 'bg-amber-500/20 text-amber-400' :
                              'bg-blue-500/20 text-blue-400'
                            }`}>
                              {mc.status || 'Unknown'}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-400">{mc.organization || '-'}</td>
                          <td className="px-6 py-4 text-sm text-gray-400">{mc.event_count} events</td>
                          <td className="px-6 py-4 flex gap-2">
                            <Link
                              href={`/model/${mc.token_id}`}
                              className="text-xs text-indigo-400 hover:text-indigo-300"
                            >
                              View
                            </Link>
                            <button
                              onClick={() => {
                                setNeo4jQuery(`MATCH (mc:ModelCard {token_id: '${mc.token_id}'})-[r]->(n) RETURN mc, type(r), n`);
                                setActiveTab('neo4j');
                              }}
                              className="text-xs text-blue-400 hover:text-blue-300"
                            >
                              Neo4j
                            </button>
                            <button
                              onClick={() => {
                                setSelectedBucket('model-cards');
                                fetchMinioObjects('model-cards');
                                setActiveTab('minio');
                              }}
                              className="text-xs text-amber-400 hover:text-amber-300"
                            >
                              MinIO
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'neo4j' && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {Object.entries(neo4jSchema?.node_counts || {}).slice(0, 4).map(([label, count]) => (
                  <div key={label} className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                    <p className="text-sm text-gray-400">{label}</p>
                    <p className="text-2xl font-bold text-blue-400">{count}</p>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <Database className="w-5 h-5 text-blue-400" />
                    Node Labels ({neo4jSchema?.labels?.length || 0})
                  </h3>
                  <div className="space-y-2">
                    {neo4jSchema?.labels.map((label, i) => (
                      <button
                        key={i}
                        onClick={() => setNeo4jQuery(`MATCH (n:${label}) RETURN n LIMIT 25`)}
                        className="w-full flex items-center justify-between px-4 py-2 bg-gray-700/50 rounded-lg hover:bg-gray-700 transition-all"
                      >
                        <span className="text-gray-300">{label}</span>
                        <span className="text-blue-400 font-mono">{neo4jSchema?.node_counts[label] || 0}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <LinkIcon className="w-5 h-5 text-purple-400" />
                    Relationships ({neo4jSchema?.relationships?.length || 0})
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {neo4jSchema?.relationships.map((rel, i) => (
                      <button
                        key={i}
                        onClick={() => setNeo4jQuery(`MATCH (a)-[r:${rel}]->(b) RETURN a, r, b LIMIT 25`)}
                        className="px-3 py-1.5 bg-purple-500/20 text-purple-400 rounded-full text-sm hover:bg-purple-500/30 transition-all"
                      >
                        {rel}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                <h3 className="text-lg font-semibold text-white mb-4">Quick Queries</h3>
                <div className="flex flex-wrap gap-2">
                  {predefinedQueries.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => setNeo4jQuery(q.query)}
                      className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-all text-sm"
                    >
                      {q.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Terminal className="w-5 h-5 text-green-400" />
                  Cypher Query Console
                </h3>
                <div className="space-y-4">
                  <textarea
                    value={neo4jQuery}
                    onChange={(e) => setNeo4jQuery(e.target.value)}
                    className="w-full h-32 px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-gray-300 font-mono text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    placeholder="MATCH (n) RETURN n LIMIT 10"
                  />
                  <div className="flex items-center gap-4">
                    <button
                      onClick={runNeo4jQuery}
                      disabled={actionLoading === 'neo4j'}
                      className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-500 transition-all disabled:opacity-50"
                    >
                      {actionLoading === 'neo4j' ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                      Run Query
                    </button>
                    <span className="text-sm text-gray-500">Only MATCH queries allowed (read-only)</span>
                  </div>
                  {neo4jResults.length > 0 && (
                    <div className="mt-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm text-gray-400">{neo4jResults.length} results</span>
                        <button
                          onClick={() => copyToClipboard(JSON.stringify(neo4jResults, null, 2))}
                          className="text-sm text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                        >
                          <Copy className="w-3 h-3" /> Copy JSON
                        </button>
                      </div>
                      <div className="p-4 bg-gray-900 rounded-xl border border-gray-700 overflow-auto max-h-96">
                        <pre className="text-sm text-gray-300 font-mono">
                          {JSON.stringify(neo4jResults, null, 2)}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'minio' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {minioBuckets.map((bucket, i) => (
                  <button
                    key={i}
                    onClick={() => { setSelectedBucket(bucket.name); fetchMinioObjects(bucket.name); setSelectedObjectContent(null); }}
                    className={`p-6 bg-gray-800 rounded-2xl border transition-all text-left ${
                      selectedBucket === bucket.name ? 'border-amber-500 ring-2 ring-amber-500/20' : 'border-gray-700 hover:border-gray-600'
                    }`}
                  >
                    <div className="flex items-center gap-3 mb-3">
                      <div className="p-3 rounded-xl bg-amber-500/20">
                        <Folder className="w-6 h-6 text-amber-400" />
                      </div>
                      <div>
                        <p className="font-semibold text-white">{bucket.name}</p>
                        <p className="text-sm text-gray-400">{bucket.object_count} objects</p>
                      </div>
                    </div>
                    <p className="text-xs text-gray-500">Created: {bucket.creation_date?.split('T')[0]}</p>
                  </button>
                ))}
              </div>

              {selectedBucket && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-700 flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-white">Objects in {selectedBucket}</h3>
                      <span className="text-sm text-gray-400">{minioObjects.length} files</span>
                    </div>
                    <div className="divide-y divide-gray-700 max-h-[500px] overflow-auto">
                      {minioObjects.map((obj, i) => (
                        <button
                          key={i}
                          onClick={() => fetchObjectContent(selectedBucket, obj.name)}
                          className="w-full px-6 py-4 text-left hover:bg-gray-700/30 transition-all flex items-center justify-between"
                        >
                          <div className="flex items-center gap-3">
                            <FileJson className="w-5 h-5 text-blue-400" />
                            <div>
                              <p className="text-sm text-gray-300">{obj.name}</p>
                              <p className="text-xs text-gray-500">{formatBytes(obj.size)}</p>
                            </div>
                          </div>
                          <ChevronRight className="w-4 h-4 text-gray-500" />
                        </button>
                      ))}
                    </div>
                  </div>

                  <div className="bg-gray-800 rounded-2xl border border-gray-700 overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-700">
                      <h3 className="text-lg font-semibold text-white">Object Content</h3>
                    </div>
                    {selectedObjectContent ? (
                      <div className="p-4">
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-sm text-gray-400 font-mono">{selectedObjectContent.path}</span>
                          <button
                            onClick={() => copyToClipboard(typeof selectedObjectContent.content === 'string' ? selectedObjectContent.content : JSON.stringify(selectedObjectContent.content, null, 2))}
                            className="text-sm text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                          >
                            <Copy className="w-3 h-3" /> Copy
                          </button>
                        </div>
                        <div className="p-4 bg-gray-900 rounded-xl border border-gray-700 overflow-auto max-h-[400px]">
                          <pre className="text-sm text-gray-300 font-mono whitespace-pre-wrap">
                            {typeof selectedObjectContent.content === 'string'
                              ? selectedObjectContent.content
                              : JSON.stringify(selectedObjectContent.content, null, 2)}
                          </pre>
                        </div>
                      </div>
                    ) : (
                      <div className="p-12 text-center text-gray-500">
                        <FileJson className="w-12 h-12 mx-auto mb-3 opacity-50" />
                        <p>Select an object to view its content</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'blockchain' && (
            <div className="space-y-6">
              <div className={`p-6 rounded-2xl border ${blockchainStatus?.connected ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
                <div className="flex items-center gap-4">
                  <div className={`p-3 rounded-xl ${blockchainStatus?.connected ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
                    <Server className={`w-8 h-8 ${blockchainStatus?.connected ? 'text-green-400' : 'text-red-400'}`} />
                  </div>
                  <div>
                    <h3 className={`text-xl font-bold ${blockchainStatus?.connected ? 'text-green-400' : 'text-red-400'}`}>
                      {blockchainStatus?.connected ? 'Connected to Blockchain' : 'Disconnected'}
                    </h3>
                    <p className="text-gray-400">{blockchainStatus?.provider || 'No provider configured'}</p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 rounded-lg bg-orange-500/20">
                      <Hash className="w-5 h-5 text-orange-400" />
                    </div>
                    <span className="text-gray-400">Chain ID</span>
                  </div>
                  <p className="text-3xl font-bold text-white">{blockchainStatus?.chain_id || '-'}</p>
                  <p className="text-sm text-gray-500 mt-1">Hardhat Local</p>
                </div>

                <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 rounded-lg bg-blue-500/20">
                      <Box className="w-5 h-5 text-blue-400" />
                    </div>
                    <span className="text-gray-400">Block Number</span>
                  </div>
                  <p className="text-3xl font-bold text-white">{blockchainStatus?.block_number || '-'}</p>
                  <p className="text-sm text-gray-500 mt-1">Latest block</p>
                </div>

                <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 rounded-lg bg-purple-500/20">
                      <Activity className="w-5 h-5 text-purple-400" />
                    </div>
                    <span className="text-gray-400">Gas Price</span>
                  </div>
                  <p className="text-3xl font-bold text-white">{blockchainStatus?.gas_price ? (parseInt(blockchainStatus.gas_price) / 1e9).toFixed(2) : '-'}</p>
                  <p className="text-sm text-gray-500 mt-1">Gwei</p>
                </div>

                <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 rounded-lg bg-emerald-500/20">
                      <Wallet className="w-5 h-5 text-emerald-400" />
                    </div>
                    <span className="text-gray-400">Custom Accounts</span>
                  </div>
                  <p className="text-3xl font-bold text-white">{neo4jSchema?.node_counts?.['CustomAccount'] || 0}</p>
                  <p className="text-sm text-gray-500 mt-1">Created on-chain</p>
                </div>
              </div>

              <div className="bg-gray-800 rounded-2xl border border-gray-700 p-6">
                <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <FileCheck className="w-5 h-5 text-indigo-400" />
                  Smart Contract Information
                </h3>
                <div className="space-y-4">
                  <div className="p-4 bg-gray-700/50 rounded-xl">
                    <p className="text-sm text-gray-400 mb-1">Network</p>
                    <p className="text-white font-mono">Hardhat Local Network (Chain ID: 1337)</p>
                  </div>
                  <div className="p-4 bg-gray-700/50 rounded-xl">
                    <p className="text-sm text-gray-400 mb-1">Provider URL</p>
                    <p className="text-white font-mono">{blockchainStatus?.provider || 'http://hardhat:8545'}</p>
                  </div>
                  <div className="text-sm text-gray-500">
                    Smart contracts are deployed on the local Hardhat network. All transactions are gasless using account abstraction.
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'identity-disputes' && (
            <IdentityDisputesTab getAuthHeaders={getAuthHeaders} />
          )}

          {activeTab === 'assign-panel' && (
            <AssignPanelTab getAuthHeaders={getAuthHeaders} />
          )}

          {activeTab === 'split-votes' && (
            <SplitVotesTab getAuthHeaders={getAuthHeaders} />
          )}

          {activeTab === 'claim-requests' && (
            <ClaimRequestsTab getAuthHeaders={getAuthHeaders} />
          )}
        </div>
      </main>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  color,
  onClick,
  subtext,
  highlight = false
}: {
  icon: any;
  label: string;
  value: number;
  color: string;
  onClick?: () => void;
  subtext?: string;
  highlight?: boolean;
}) {
  const colors = {
    blue: 'from-blue-500 to-blue-600',
    green: 'from-green-500 to-green-600',
    amber: 'from-amber-500 to-amber-600',
    purple: 'from-purple-500 to-purple-600',
  };

  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      className={`bg-gray-800 rounded-2xl border ${highlight ? 'border-amber-500/50 ring-2 ring-amber-500/20' : 'border-gray-700'} p-6 text-left transition-all ${onClick ? 'hover:border-[var(--fg-faint)] cursor-pointer' : ''}`}
    >
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-xl bg-gray-100 dark:bg-gray-800`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
        <div>
          <p className="text-sm text-gray-400">{label}</p>
          <p className="text-3xl font-bold text-white">{value}</p>
          {subtext && <p className="text-xs text-gray-500 mt-1">{subtext}</p>}
        </div>
      </div>
    </button>
  );
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
