import { useState, useEffect } from 'react';
import { useI18n } from '@/contexts/I18nContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Plus, MoreHorizontal, Pencil, Trash2, Heart, RefreshCw, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { motion } from 'framer-motion';

export default function NodesPage() {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: '', ip: '', api_port: '', api_key: '', country: '' });
  const [saving, setSaving] = useState(false);
  const { t } = useI18n();

  const fetchNodes = () => {
    api.get('/nodes').then(({ data }) => { setNodes(data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(fetchNodes, []);

  const openAdd = () => { setEditing(null); setForm({ name: '', ip: '', api_port: '', api_key: '', country: '' }); setDialogOpen(true); };
  const openEdit = (node) => { setEditing(node); setForm({ name: node.name, ip: node.ip, api_port: String(node.api_port), api_key: '', country: node.country || '' }); setDialogOpen(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = { ...form, api_port: parseInt(form.api_port) };
      if (!payload.api_key && editing) delete payload.api_key;
      if (editing) {
        await api.put(`/nodes/${editing.id}`, payload);
        toast.success('Node updated');
      } else {
        await api.post('/nodes', payload);
        toast.success('Node created');
      }
      setDialogOpen(false);
      fetchNodes();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    }
    setSaving(false);
  };

  const handleDelete = async (node) => {
    if (!window.confirm(t('nodes.deleteConfirm'))) return;
    try {
      await api.delete(`/nodes/${node.id}`);
      toast.success('Node deleted');
      fetchNodes();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Error');
    }
  };

  const healthCheck = async (nodeId) => {
    try {
      const { data } = await api.post(`/nodes/${nodeId}/health-check`);
      toast.success(`Status: ${data.status}`);
      fetchNodes();
    } catch {
      toast.error('Health check failed');
    }
  };

  return (
    <div className="space-y-6" data-testid="nodes-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>{t('nodes.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">Manage your Outline VPN servers</p>
        </div>
        <Button onClick={openAdd} className="bg-cyan-600 hover:bg-cyan-500 text-black font-semibold gap-2" data-testid="add-node-button">
          <Plus className="w-4 h-4" /> {t('nodes.addNode')}
        </Button>
      </div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="ll-card border-white/5">
          <CardContent className="p-0">
            <Table data-testid="node-table">
              <TableHeader>
                <TableRow className="border-white/5 hover:bg-transparent">
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('common.status')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('common.name')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('nodes.ipAddress')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('nodes.country')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('nodes.userCount')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('nodes.lastHeartbeat')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider text-right">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow><TableCell colSpan={7} className="text-center py-12 text-gray-500"><Loader2 className="w-5 h-5 animate-spin mx-auto" /></TableCell></TableRow>
                ) : nodes.length === 0 ? (
                  <TableRow><TableCell colSpan={7} className="text-center py-12 text-gray-500">{t('common.noData')}</TableCell></TableRow>
                ) : nodes.map((node) => (
                  <TableRow key={node.id} className="border-white/5 hover:bg-white/[0.02]">
                    <TableCell>
                      <div className={`w-2.5 h-2.5 rounded-full ${node.status === 'online' ? 'll-status-online' : node.status === 'offline' ? 'll-status-offline' : 'll-status-unknown'}`} />
                    </TableCell>
                    <TableCell className="text-gray-200 font-medium">{node.name}</TableCell>
                    <TableCell className="font-mono text-xs text-gray-400">{node.ip}:{node.api_port}</TableCell>
                    <TableCell className="text-gray-400">{node.country || '—'}</TableCell>
                    <TableCell className="text-gray-400">{node.user_count}</TableCell>
                    <TableCell className="font-mono text-xs text-gray-500">
                      {node.last_heartbeat ? new Date(node.last_heartbeat).toLocaleString() : '—'}
                    </TableCell>
                    <TableCell className="text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8 text-gray-500" data-testid={`node-actions-${node.id}`}>
                            <MoreHorizontal className="w-4 h-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="bg-zinc-950 border-white/10">
                          <DropdownMenuItem onClick={() => openEdit(node)} className="text-gray-300 gap-2">
                            <Pencil className="w-3.5 h-3.5" /> {t('common.edit')}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => healthCheck(node.id)} className="text-gray-300 gap-2">
                            <Heart className="w-3.5 h-3.5" /> {t('nodes.healthCheck')}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => handleDelete(node)} className="text-red-400 gap-2">
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

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-md">
          <DialogHeader>
            <DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>
              {editing ? t('nodes.editNode') : t('nodes.addNode')}
            </DialogTitle>
            <DialogDescription className="text-gray-500 text-sm">Configure Outline VPN server connection</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('nodes.nodeName')}</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="bg-black/50 border-white/10" data-testid="node-name-input" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-gray-400 text-xs uppercase">{t('nodes.ipAddress')}</Label>
                <Input value={form.ip} onChange={(e) => setForm({ ...form, ip: e.target.value })}
                  className="bg-black/50 border-white/10 font-mono text-xs" data-testid="node-ip-input" />
              </div>
              <div className="space-y-1.5">
                <Label className="text-gray-400 text-xs uppercase">{t('nodes.apiPort')}</Label>
                <Input type="number" value={form.api_port} onChange={(e) => setForm({ ...form, api_port: e.target.value })}
                  className="bg-black/50 border-white/10 font-mono text-xs" data-testid="node-port-input" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('nodes.apiKey')}</Label>
              <Input value={form.api_key} onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                placeholder={editing ? '(unchanged)' : ''} className="bg-black/50 border-white/10 font-mono text-xs" data-testid="node-key-input" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('nodes.country')}</Label>
              <Input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })}
                placeholder="DE, US, NL..." className="bg-black/50 border-white/10" data-testid="node-country-input" />
            </div>
            <div className="flex gap-3 pt-2">
              <Button variant="ghost" onClick={() => setDialogOpen(false)} className="flex-1 text-gray-400">
                {t('common.cancel')}
              </Button>
              <Button onClick={handleSave} disabled={saving} className="flex-1 bg-cyan-600 hover:bg-cyan-500 text-black font-semibold" data-testid="node-save-button">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : t('common.save')}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
