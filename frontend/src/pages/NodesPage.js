import { useState, useEffect } from 'react';
import { useI18n } from '@/contexts/I18nContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Plus, MoreHorizontal, Pencil, Trash2, RefreshCw, Loader2, Copy, Key, Wifi, WifiOff } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { motion } from 'framer-motion';
import { copyToClipboard } from '@/lib/clipboard';

export default function NodesPage() {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [tokenNode, setTokenNode] = useState(null);
  const [form, setForm] = useState({ name: '', ip: '', country: '' });
  const [saving, setSaving] = useState(false);
  const { t } = useI18n();

  const fetchNodes = () => {
    api.get('/nodes').then(({ data }) => { setNodes(data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(fetchNodes, []);

  const openAdd = () => { setEditing(null); setForm({ name: '', ip: '', country: '' }); setDialogOpen(true); };
  const openEdit = (node) => { setEditing(node); setForm({ name: node.name, ip: node.ip, country: node.country || '' }); setDialogOpen(true); };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/nodes/${editing.id}`, form);
        toast.success('Node updated');
      } else {
        await api.post('/nodes', form);
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

  const refreshAll = async () => {
    setRefreshing(true);
    try {
      const { data } = await api.post('/nodes/refresh-all');
      toast.success(data.message);
      fetchNodes();
    } catch {
      toast.error('Refresh failed');
    }
    setRefreshing(false);
  };

  return (
    <div className="space-y-6" data-testid="nodes-page">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>{t('nodes.title')}</h1>
          <p className="text-sm text-gray-500 mt-1">Manage your Shadowsocks VPN servers</p>
        </div>
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <Button onClick={refreshAll} disabled={refreshing} variant="outline"
            className="border-white/10 text-gray-300 gap-2 flex-1 sm:flex-none" data-testid="refresh-all-button">
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} /> Refresh
          </Button>
          <Button onClick={openAdd} className="bg-cyan-600 hover:bg-cyan-500 text-black font-semibold gap-2 flex-1 sm:flex-none" data-testid="add-node-button">
            <Plus className="w-4 h-4" /> {t('nodes.addNode')}
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-gray-500" /></div>
      ) : nodes.length === 0 ? (
        <Card className="ll-card border-white/5"><CardContent className="py-16 text-center text-gray-500">{t('common.noData')}</CardContent></Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {nodes.map((node, i) => (
            <motion.div key={node.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}>
              <Card className="ll-card border-white/5 relative group">
                <CardContent className="p-4 sm:p-5 space-y-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${
                        node.status === 'online' ? 'bg-emerald-500/15' : 'bg-red-500/15'
                      }`}>
                        {node.status === 'online'
                          ? <Wifi className="w-5 h-5 text-emerald-400" />
                          : <WifiOff className="w-5 h-5 text-red-400" />
                        }
                      </div>
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-white truncate">{node.name}</h3>
                        <p className="text-xs text-gray-500 font-mono truncate">{node.ip}</p>
                      </div>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-gray-500 shrink-0" data-testid={`node-actions-${node.id}`}>
                          <MoreHorizontal className="w-4 h-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="bg-zinc-950 border-white/10 text-gray-200">
                        <DropdownMenuItem onClick={() => openEdit(node)} className="text-gray-300 gap-2">
                          <Pencil className="w-3.5 h-3.5" /> {t('common.edit')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => setTokenNode(node)} className="text-gray-300 gap-2">
                          <Key className="w-3.5 h-3.5" /> Node Token
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => healthCheck(node.id)} className="text-gray-300 gap-2">
                          <RefreshCw className="w-3.5 h-3.5" /> Reconnect
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleDelete(node)} className="text-red-400 gap-2">
                          <Trash2 className="w-3.5 h-3.5" /> {t('common.delete')}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>

                  <div className="grid grid-cols-3 gap-2 pt-1">
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase">Status</p>
                      <Badge variant={node.status === 'online' ? 'default' : 'destructive'} className="text-[10px] h-5 mt-0.5">
                        {node.status}
                      </Badge>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase">{t('nodes.country')}</p>
                      <p className="text-xs text-gray-300 mt-0.5">{node.country || '—'}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase">{t('nodes.userCount')}</p>
                      <p className="text-xs text-gray-300 mt-0.5">{node.user_count}</p>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-1 border-t border-white/5">
                    <p className="text-[10px] text-gray-600">
                      Port {node.api_port || 9090} · {node.last_heartbeat ? new Date(node.last_heartbeat).toLocaleString() : 'No heartbeat'}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}

      {/* Add/Edit Dialog — only name, IP, country */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-md mx-4">
          <DialogHeader>
            <DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>
              {editing ? t('nodes.editNode') : t('nodes.addNode')}
            </DialogTitle>
            <DialogDescription className="text-gray-500 text-sm">
              {editing ? 'Update node details' : 'Add a new server node. Token and port are auto-generated.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('nodes.nodeName')}</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="e.g. Germany Node" className="bg-black/50 border-white/10 text-gray-200" data-testid="node-name-input" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('nodes.ipAddress')}</Label>
              <Input value={form.ip} onChange={(e) => setForm({ ...form, ip: e.target.value })}
                placeholder="e.g. 45.33.21.10" className="bg-black/50 border-white/10 font-mono text-sm text-gray-200" data-testid="node-ip-input" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('nodes.country')}</Label>
              <Input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })}
                placeholder="DE, US, NL..." className="bg-black/50 border-white/10 text-gray-200" data-testid="node-country-input" />
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

      {/* Node Token Dialog */}
      <Dialog open={!!tokenNode} onOpenChange={() => setTokenNode(null)}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-md mx-4">
          <DialogHeader>
            <DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>Node Token — {tokenNode?.name}</DialogTitle>
            <DialogDescription className="text-gray-500 text-sm">Use this token when setting up Lightline Node</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">Token</Label>
              <div className="p-3 rounded-lg bg-black/50 border border-white/10 font-mono text-xs text-cyan-400 break-all select-all">
                {tokenNode?.node_token || 'No token generated'}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-zinc-900/50 border border-white/5 space-y-2">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Environment Variables</p>
              <p className="font-mono text-[11px] text-gray-300 break-all">
                NODE_TOKEN={tokenNode?.node_token}<br />
                NODE_PORT={tokenNode?.api_port || 9090}
              </p>
            </div>
            <Button
              onClick={() => {
                copyToClipboard(tokenNode?.node_token || '').then(ok => {
                  if (ok) toast.success('Token copied');
                  else toast.error('Copy failed');
                });
              }}
              className="w-full bg-cyan-600 hover:bg-cyan-500 text-black font-semibold gap-2"
            >
              <Copy className="w-4 h-4" /> Copy Token
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
