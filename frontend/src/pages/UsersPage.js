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
import { Plus, MoreHorizontal, Pencil, Trash2, QrCode, ArrowLeftRight, Loader2, Copy } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import QRCode from 'react-qr-code';
import { motion } from 'framer-motion';

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
  const [form, setForm] = useState({ username: '', password: '', traffic_limit: '0', device_limit: '1', expire_date: '', assigned_node_id: '' });
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState('');
  const { t } = useI18n();

  const fetchData = async () => {
    try {
      const [u, n] = await Promise.all([api.get('/users'), api.get('/nodes')]);
      setUsers(u.data); setNodes(n.data);
    } catch {}
    setLoading(false);
  };
  useEffect(() => { fetchData(); }, []);

  const openAdd = () => { setEditing(null); setForm({ username: '', password: '', traffic_limit: '0', device_limit: '1', expire_date: '', assigned_node_id: '' }); setDialogOpen(true); };
  const openEdit = (u) => { setEditing(u); setForm({ username: u.username, password: '', traffic_limit: String(u.traffic_limit ? u.traffic_limit / 1_000_000_000 : 0), device_limit: String(u.device_limit), expire_date: u.expire_date ? u.expire_date.split('T')[0] : '', assigned_node_id: u.assigned_node_id ? String(u.assigned_node_id) : '' }); setDialogOpen(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = {
        username: form.username,
        traffic_limit: parseFloat(form.traffic_limit) * 1_000_000_000,
        device_limit: parseInt(form.device_limit),
        expire_date: form.expire_date || null,
        assigned_node_id: form.assigned_node_id ? parseInt(form.assigned_node_id) : null,
      };
      if (form.password) payload.password = form.password;
      if (editing) {
        await api.put(`/users/${editing.id}`, payload);
        toast.success('User updated');
      } else {
        payload.password = form.password || 'default123';
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
            className="bg-black/50 border-white/10 h-9 text-sm w-full sm:w-48" data-testid="user-search-input" />
          <Button onClick={openAdd} className="bg-cyan-600 hover:bg-cyan-500 text-black font-semibold gap-2 whitespace-nowrap" data-testid="add-user-button">
            <Plus className="w-4 h-4" /> {t('users.addUser')}
          </Button>
        </div>
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <Card className="ll-card border-white/5">
          <CardContent className="p-0">
            <Table data-testid="user-table">
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
                          <DropdownMenuItem onClick={() => openEdit(u)} className="text-gray-300 gap-2">
                            <Pencil className="w-3.5 h-3.5" /> {t('common.edit')}
                          </DropdownMenuItem>
                          {u.access_url && (
                            <DropdownMenuItem onClick={() => setQrUser(u)} className="text-gray-300 gap-2">
                              <QrCode className="w-3.5 h-3.5" /> {t('users.qrCode')}
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuItem onClick={() => { setSwitchUser(u); setSwitchNodeId(''); }} className="text-gray-300 gap-2">
                            <ArrowLeftRight className="w-3.5 h-3.5" /> {t('users.switchNode')}
                          </DropdownMenuItem>
                          {u.access_url && (
                            <DropdownMenuItem onClick={() => { navigator.clipboard.writeText(u.access_url); toast.success('Copied'); }} className="text-gray-300 gap-2">
                              <Copy className="w-3.5 h-3.5" /> Copy URL
                            </DropdownMenuItem>
                          )}
                          <DropdownMenuItem onClick={() => handleDelete(u)} className="text-red-400 gap-2">
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
        <DialogContent className="bg-zinc-950 border-white/10 max-w-md">
          <DialogHeader><DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>{editing ? t('users.editUser') : t('users.addUser')}</DialogTitle><DialogDescription className="text-gray-500 text-sm">Configure VPN user access</DialogDescription></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('users.username')}</Label>
              <Input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="bg-black/50 border-white/10" data-testid="user-name-input" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('users.password')}</Label>
              <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder={editing ? '(unchanged)' : ''} className="bg-black/50 border-white/10" data-testid="user-password-input" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-gray-400 text-xs uppercase">{t('users.trafficLimit')}</Label>
                <Input type="number" value={form.traffic_limit} onChange={(e) => setForm({ ...form, traffic_limit: e.target.value })} className="bg-black/50 border-white/10" data-testid="user-traffic-input" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-gray-400 text-xs uppercase">{t('users.deviceLimit')}</Label>
                <Input type="number" value={form.device_limit} onChange={(e) => setForm({ ...form, device_limit: e.target.value })} className="bg-black/50 border-white/10" data-testid="user-device-input" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('users.expireDate')}</Label>
              <Input type="date" value={form.expire_date} onChange={(e) => setForm({ ...form, expire_date: e.target.value })} className="bg-black/50 border-white/10" data-testid="user-expire-input" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('users.assignedNode')}</Label>
              <Select value={form.assigned_node_id} onValueChange={(v) => setForm({ ...form, assigned_node_id: v })}>
                <SelectTrigger className="bg-black/50 border-white/10" data-testid="user-node-select">
                  <SelectValue placeholder="Select node..." />
                </SelectTrigger>
                <SelectContent className="bg-zinc-950 border-white/10">
                  {nodes.map(n => <SelectItem key={n.id} value={String(n.id)}>{n.name} ({n.country})</SelectItem>)}
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
        <DialogContent className="bg-zinc-950 border-white/10 max-w-sm">
          <DialogHeader><DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>{t('users.qrCode')} — {qrUser?.username}</DialogTitle><DialogDescription className="text-gray-500 text-sm">Scan to connect</DialogDescription></DialogHeader>
          <div className="flex flex-col items-center gap-4 py-4">
            {qrUser?.access_url && (
              <div className="p-4 bg-white rounded-xl">
                <QRCode value={qrUser.access_url} size={200} data-testid="qr-code" />
              </div>
            )}
            <p className="font-mono text-[10px] text-gray-500 text-center break-all max-w-full px-4">{qrUser?.access_url}</p>
            <Button variant="ghost" size="sm" onClick={() => { navigator.clipboard.writeText(qrUser?.access_url || ''); toast.success('Copied'); }} className="text-cyan-400 gap-2">
              <Copy className="w-3.5 h-3.5" /> Copy Access URL
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Switch Node Dialog */}
      <Dialog open={!!switchUser} onOpenChange={() => setSwitchUser(null)}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-sm">
          <DialogHeader><DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>{t('users.switchNode')} — {switchUser?.username}</DialogTitle><DialogDescription className="text-gray-500 text-sm">Select a new server</DialogDescription></DialogHeader>
          <div className="space-y-4 mt-2">
            <Select value={switchNodeId} onValueChange={setSwitchNodeId}>
              <SelectTrigger className="bg-black/50 border-white/10" data-testid="switch-node-select">
                <SelectValue placeholder="Select target node..." />
              </SelectTrigger>
              <SelectContent className="bg-zinc-950 border-white/10">
                {nodes.filter(n => n.status === 'online').map(n => <SelectItem key={n.id} value={String(n.id)}>{n.name} ({n.country})</SelectItem>)}
              </SelectContent>
            </Select>
            <div className="flex gap-3">
              <Button variant="ghost" onClick={() => setSwitchUser(null)} className="flex-1 text-gray-400">{t('common.cancel')}</Button>
              <Button onClick={handleSwitch} disabled={!switchNodeId} className="flex-1 bg-cyan-600 hover:bg-cyan-500 text-black font-semibold" data-testid="switch-confirm-button">{t('common.confirm')}</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
