import { useState, useEffect } from 'react';
import { useI18n } from '@/contexts/I18nContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Plus, MoreHorizontal, Pencil, Trash2, QrCode, ArrowLeftRight, Loader2, Copy, Users } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import QRCode from 'react-qr-code';
import { motion } from 'framer-motion';
import { copyToClipboard } from '@/lib/clipboard';

const formatBytes = (b) => {
  if (!b) return '0 B';
  const k = 1024, s = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(b) / Math.log(k));
  return parseFloat((b / Math.pow(k, i)).toFixed(1)) + ' ' + s[i];
};

export default function UsersPage() {
  const [users, setUsers] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [qrUser, setQrUser] = useState(null);
  const [switchUser, setSwitchUser] = useState(null);
  const [switchNodeId, setSwitchNodeId] = useState('');
  const [form, setForm] = useState({ username: '', traffic_limit: '0', expire_date: '', assigned_node_id: '' });
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const [bulkSwitchOpen, setBulkSwitchOpen] = useState(false);
  const [bulkNodeId, setBulkNodeId] = useState('');
  const [bulkSwitching, setBulkSwitching] = useState(false);
  const { t } = useI18n();

  const fetchData = async () => {
    try {
      const [u, n] = await Promise.all([api.get('/users'), api.get('/nodes')]);
      setUsers(u.data); setNodes(n.data);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { fetchData(); }, []);

  const openAdd = () => { setEditing(null); setForm({ username: '', traffic_limit: '0', expire_date: '', assigned_node_id: '' }); setDialogOpen(true); };
  const openEdit = (u) => { setEditing(u); setForm({ username: u.username, traffic_limit: String(u.traffic_limit ? u.traffic_limit / 1_000_000_000 : 0), expire_date: u.expire_date ? u.expire_date.split('T')[0] : '', assigned_node_id: u.assigned_node_id ? String(u.assigned_node_id) : '' }); setDialogOpen(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        username: form.username,
        traffic_limit: parseFloat(form.traffic_limit) * 1_000_000_000,
        expire_date: form.expire_date || null,
        assigned_node_id: form.assigned_node_id ? parseInt(form.assigned_node_id) : null,
      };
      if (editing) {
        await api.put(`/users/${editing.id}`, payload);
        toast.success('User updated');
      } else {
        await api.post('/users', payload);
        toast.success('User created');
      }
      setDialogOpen(false); fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    }
    setSaving(false);
  };

  const handleDelete = async (u) => {
    if (!window.confirm(t('users.deleteConfirm'))) return;
    try { await api.delete(`/users/${u.id}`); toast.success('User deleted'); fetchData(); } catch (err) { toast.error('Error'); }
  };

  const handleSwitch = async () => {
    if (!switchNodeId) return;
    try {
      const { data } = await api.post(`/users/${switchUser.id}/switch-node`, { node_id: parseInt(switchNodeId) });
      toast.success(data.message);
      setSwitchUser(null); fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
  };

  const handleBulkSwitch = async () => {
    if (!bulkNodeId) return;
    setBulkSwitching(true);
    try {
      const { data } = await api.post('/users/bulk-switch-node', { node_id: parseInt(bulkNodeId) });
      toast.success(data.message);
      setBulkSwitchOpen(false); setBulkNodeId(''); fetchData();
    } catch (err) { toast.error(err.response?.data?.detail || 'Error'); }
    setBulkSwitching(false);
  };

  const filtered = users.filter(u => u.username.toLowerCase().includes(search.toLowerCase()));

  return (
    <div className="space-y-6" data-testid="users-page">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>{t('users.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">Manage VPN access keys and users</p>
        </div>
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <Input placeholder={t('common.search')} value={search} onChange={(e) => setSearch(e.target.value)}
            className="bg-black/50 border-white/10 h-9 text-sm text-gray-200 w-full sm:w-48" data-testid="user-search-input" />
          <Button variant="outline" onClick={() => { setBulkSwitchOpen(true); setBulkNodeId(''); }}
            className="border-white/10 text-gray-300 gap-2 whitespace-nowrap" data-testid="bulk-switch-button">
            <Users className="w-4 h-4" /> Switch All
          </Button>
          <Button onClick={openAdd} className="bg-cyan-600 hover:bg-cyan-500 text-black font-semibold gap-2 whitespace-nowrap" data-testid="add-user-button">
            <Plus className="w-4 h-4" /> {t('users.addUser')}
          </Button>
        </div>
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <Card className="ll-card border-white/5">
          <CardContent className="p-0 overflow-x-auto">
            <Table data-testid="user-table" className="min-w-[640px]">
              <TableHeader>
                <TableRow className="border-white/5 hover:bg-transparent">
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('users.username')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('common.status')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('users.assignedNode')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('users.trafficUsed')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('users.expireDate')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider text-right">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow><TableCell colSpan={6} className="text-center py-12"><Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-500" /></TableCell></TableRow>
                ) : filtered.length === 0 ? (
                  <TableRow><TableCell colSpan={6} className="text-center py-12 text-gray-500">{t('common.noData')}</TableCell></TableRow>
                ) : filtered.map((u) => (
                  <TableRow key={u.id} className="border-white/5 hover:bg-white/[0.02]">
                    <TableCell className="text-gray-200 font-medium">{u.username}</TableCell>
                    <TableCell>
                      <Badge variant={u.status === 'active' ? 'default' : 'destructive'} className="text-[10px] h-5">
                        {u.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-gray-400 text-sm">{u.node_name || '—'}</TableCell>
                    <TableCell className="font-mono text-xs text-gray-400">
                      {formatBytes(u.traffic_used)}{u.traffic_limit > 0 && ` / ${formatBytes(u.traffic_limit)}`}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-gray-500">
                      {u.expire_date ? new Date(u.expire_date).toLocaleDateString() : '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-gray-500" data-testid={`user-actions-${u.id}`}>
                            <MoreHorizontal className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="bg-zinc-950 border-white/10">
                          <DropdownMenuItem onClick={() => openEdit(u)} className="text-gray-300 gap-2 min-h-[44px]">
                            <Pencil className="w-3.5 h-3.5" /> {t('common.edit')}
                          </DropdownMenuItem>
                          {u.access_url && (
                            <DropdownMenuItem onClick={() => setQrUser(u)} className="text-gray-300 gap-2 min-h-[44px]">
                              <QrCode className="w-3.5 h-3.5" /> {t('users.qrCode')}
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuItem onClick={() => { setSwitchUser(u); setSwitchNodeId(''); }} className="text-gray-300 gap-2 min-h-[44px]">
                            <ArrowLeftRight className="w-3.5 h-3.5" /> {t('users.switchNode')}
                          </DropdownMenuItem>
                          {u.access_url && (
                            <DropdownMenuItem
                              onSelect={async (e) => {
                                e.preventDefault();
                                const ok = await copyToClipboard(u.access_url);
                                if (ok) toast.success('SS URL copied');
                                else toast.error('Copy failed');
                              }}
                              className="text-gray-300 gap-2 min-h-[44px]"
                            >
                              <Copy className="w-4 h-4" /> Copy SS URL
                            </DropdownMenuItem>
                          )}
                          {u.sub_url && (
                            <DropdownMenuItem
                              onSelect={async (e) => {
                                e.preventDefault();
                                const ok = await copyToClipboard(`ssconf://${window.location.host}${u.sub_url}`);
                                if (ok) toast.success('Sub URL copied');
                                else toast.error('Copy failed');
                              }}
                              className="text-gray-300 gap-2 min-h-[44px]"
                            >
                              <Copy className="w-4 h-4" /> Copy Sub URL
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuItem onClick={() => handleDelete(u)} className="text-red-400 gap-2 min-h-[44px]">
                            <Trash2 className="w-3.5 h-3.5" /> {t('common.delete')}
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </motion.div>

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-md mx-4">
          <DialogHeader><DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>{editing ? t('users.editUser') : t('users.addUser')}</DialogTitle><DialogDescription className="text-gray-500 text-sm">Configure VPN user access</DialogDescription></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('users.username')}</Label>
              <Input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="bg-black/50 border-white/10 text-gray-200" data-testid="user-name-input" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('users.trafficLimit')} (GB)</Label>
              <Input type="number" value={form.traffic_limit} onChange={(e) => setForm({ ...form, traffic_limit: e.target.value })} placeholder="0 = unlimited" className="bg-black/50 border-white/10 text-gray-200" data-testid="user-traffic-input" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('users.expireDate')}</Label>
              <Input type="date" value={form.expire_date} onChange={(e) => setForm({ ...form, expire_date: e.target.value })} className="bg-black/50 border-white/10 text-gray-200" data-testid="user-expire-input" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('users.assignedNode')}</Label>
              <Select value={form.assigned_node_id} onValueChange={(v) => setForm({ ...form, assigned_node_id: v })}>
                <SelectTrigger className="bg-black/50 border-white/10 text-gray-200" data-testid="user-node-select">
                  <SelectValue placeholder="Select node..." />
                </SelectTrigger>
                <SelectContent className="bg-zinc-950 border-white/10 text-gray-200">
                  {nodes.map(n => <SelectItem key={n.id} value={String(n.id)} className="text-gray-200 focus:text-white focus:bg-cyan-900/30">{n.name} ({n.country})</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-3 pt-2">
              <Button variant="ghost" onClick={() => setDialogOpen(false)} className="flex-1 text-gray-400">{t('common.cancel')}</Button>
              <Button onClick={handleSave} disabled={saving} className="flex-1 bg-cyan-600 hover:bg-cyan-500 text-black font-semibold" data-testid="user-save-button">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : t('common.save')}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* QR Code Dialog */}
      <Dialog open={!!qrUser} onOpenChange={() => setQrUser(null)}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-sm mx-4">
          <DialogHeader><DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>{t('users.qrCode')} — {qrUser?.username}</DialogTitle><DialogDescription className="text-gray-500 text-sm">Scan to connect</DialogDescription></DialogHeader>
          <div className="flex flex-col items-center gap-4 py-4">
            {qrUser?.access_url && (
              <div className="p-4 bg-white rounded-xl">
                <QRCode value={qrUser.access_url} size={200} data-testid="qr-code" />
              </div>
            )}
            <div className="w-full space-y-2 px-2">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider text-center">Shadowsocks Access Key</p>
              <p className="font-mono text-[10px] text-cyan-400 text-center break-all max-w-full bg-black/50 rounded-lg p-2 border border-white/5">{qrUser?.access_url}</p>
            </div>
            <div className="flex flex-col sm:flex-row gap-2 w-full px-2">
              <Button
                variant="outline"
                onClick={async () => {
                  const ok = await copyToClipboard(qrUser?.access_url || '');
                  if (ok) toast.success('SS URL copied');
                  else toast.error('Copy failed — long-press the URL above to copy manually');
                }}
                className="text-cyan-400 border-cyan-400/20 gap-2 min-h-[48px] flex-1 active:scale-95 transition-transform touch-manipulation"
              >
                <Copy className="w-4 h-4" /> Copy SS URL
              </Button>
              {qrUser?.sub_url && (
                <Button
                  variant="outline"
                  onClick={async () => {
                    const ok = await copyToClipboard(`ssconf://${window.location.host}${qrUser.sub_url}`);
                    if (ok) toast.success('Sub URL copied');
                    else toast.error('Copy failed — long-press the URL above to copy manually');
                  }}
                  className="text-emerald-400 border-emerald-400/20 gap-2 min-h-[48px] flex-1 active:scale-95 transition-transform touch-manipulation"
                >
                  <Copy className="w-4 h-4" /> Copy Sub URL
                </Button>
              )}
            </div>
            {qrUser?.sub_url && (
              <div className="w-full space-y-1 px-2">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider text-center">Subscription URL (auto-updates)</p>
                <p className="font-mono text-[10px] text-emerald-400 text-center break-all max-w-full bg-black/50 rounded-lg p-2 border border-white/5">
                  ssconf://{window.location.host}{qrUser.sub_url}
                </p>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Switch Node Dialog */}
      <Dialog open={!!switchUser} onOpenChange={() => setSwitchUser(null)}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-sm mx-4">
          <DialogHeader><DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>{t('users.switchNode')} — {switchUser?.username}</DialogTitle><DialogDescription className="text-gray-500 text-sm">Select a new server</DialogDescription></DialogHeader>
          <div className="space-y-4 mt-2">
            <Select value={switchNodeId} onValueChange={setSwitchNodeId}>
              <SelectTrigger className="bg-black/50 border-white/10 text-gray-200" data-testid="switch-node-select">
                <SelectValue placeholder="Select target node..." />
              </SelectTrigger>
              <SelectContent className="bg-zinc-950 border-white/10 text-gray-200">
                {nodes.filter(n => n.status === 'online').map(n => <SelectItem key={n.id} value={String(n.id)} className="text-gray-200 focus:text-white focus:bg-cyan-900/30">{n.name} ({n.country})</SelectItem>)}
              </SelectContent>
            </Select>
            <div className="flex gap-3">
              <Button variant="ghost" onClick={() => setSwitchUser(null)} className="flex-1 text-gray-400">{t('common.cancel')}</Button>
              <Button onClick={handleSwitch} disabled={!switchNodeId} className="flex-1 bg-cyan-600 hover:bg-cyan-500 text-black font-semibold" data-testid="switch-confirm-button">{t('common.confirm')}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Bulk Switch Node Dialog */}
      <Dialog open={bulkSwitchOpen} onOpenChange={setBulkSwitchOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-sm mx-4">
          <DialogHeader>
            <DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>Switch All Users</DialogTitle>
            <DialogDescription className="text-gray-500 text-sm">
              Move all active users to a different node. New ss:// access URLs will be generated.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <p className="text-xs text-amber-400">This will switch {users.filter(u => u.status === 'active' && u.assigned_node_id).length} active users to the selected node.</p>
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">Target Node</Label>
              <Select value={bulkNodeId} onValueChange={setBulkNodeId}>
                <SelectTrigger className="bg-black/50 border-white/10 text-gray-200" data-testid="bulk-switch-node-select">
                  <SelectValue placeholder="Select target node..." />
                </SelectTrigger>
                <SelectContent className="bg-zinc-950 border-white/10 text-gray-200">
                  {nodes.filter(n => n.status === 'online').map(n => (
                    <SelectItem key={n.id} value={String(n.id)} className="text-gray-200 focus:text-white focus:bg-cyan-900/30">{n.name} ({n.country}) — {n.user_count} users</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-3">
              <Button variant="ghost" onClick={() => setBulkSwitchOpen(false)} className="flex-1 text-gray-400">{t('common.cancel')}</Button>
              <Button onClick={handleBulkSwitch} disabled={!bulkNodeId || bulkSwitching}
                className="flex-1 bg-cyan-600 hover:bg-cyan-500 text-black font-semibold" data-testid="bulk-switch-confirm-button">
                {bulkSwitching ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Switch All'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
