import { useState, useEffect } from 'react';
import { useI18n } from '@/contexts/I18nContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Plus, MoreHorizontal, Pencil, Trash2, RefreshCw, Loader2, Copy, Wifi, WifiOff, ShieldCheck, Smartphone, ArrowUpDown } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { motion } from 'framer-motion';
import { copyToClipboard } from '@/lib/clipboard';

const formatBytes = (b) => {
  if (!b) return '0 B';
  const k = 1024, s = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(b) / Math.log(k));
  return parseFloat((b / Math.pow(k, i)).toFixed(1)) + ' ' + s[i];
};

export default function NodesPage() {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [certDialogOpen, setCertDialogOpen] = useState(false);
  const [certificate, setCertificate] = useState('');
  const [form, setForm] = useState({ name: '', ip: '', port: 62050, country: '' });
  const [saving, setSaving] = useState(false);
  const { t } = useI18n();

  const fetchNodes = () => {
    api.get('/nodes').then(({ data }) => { setNodes(data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(fetchNodes, []);

  const openAdd = () => { setEditing(null); setForm({ name: '', ip: '', port: 62050, country: '' }); setDialogOpen(true); };
  const openEdit = (node) => { setEditing(node); setForm({ name: node.name, ip: node.ip, port: node.port || 62050, country: node.country || '' }); setDialogOpen(true); };

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

  const regenerateUrls = async () => {
    try {
      const { data } = await api.post('/nodes/regenerate-urls');
      toast.success(data.message);
    } catch {
      toast.error('URL regeneration failed');
    }
  };

  const showCertificate = async () => {
    try {
      const { data } = await api.get('/nodes/certificate');
      setCertificate(data.certificate);
      setCertDialogOpen(true);
    } catch {
      toast.error('Failed to load certificate');
    }
  };

  return (
    <div className="space-y-6" data-testid="nodes-page">
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl sm:text-3xl font-bold text-white truncate" style={{ fontFamily: 'Outfit' }}>{t('nodes.title')}</h1>
            <p className="text-sm text-gray-500 mt-1 hidden sm:block">{t('nodes.subtitle')}</p>
          </div>
          <Button onClick={openAdd} className="bg-cyan-600 hover:bg-cyan-500 text-black font-semibold gap-2 shrink-0" data-testid="add-node-button">
            <Plus className="w-4 h-4" /> <span className="hidden sm:inline">{t('nodes.addNode')}</span><span className="sm:hidden">{t('common.add')}</span>
          </Button>
        </div>
        <div className="flex items-center gap-2 overflow-x-auto pb-1 -mb-1">
          <Button onClick={refreshAll} disabled={refreshing} variant="outline"
            className="border-white/10 text-gray-300 gap-2 shrink-0 h-9 text-xs" data-testid="refresh-all-button">
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} /> {t('nodes.refresh')}
          </Button>
          <Button onClick={regenerateUrls} variant="outline"
            className="border-white/10 text-gray-300 gap-2 shrink-0 h-9 text-xs">
            <RefreshCw className="w-3.5 h-3.5" /> {t('nodes.regenUrls')}
          </Button>
          <Button onClick={showCertificate} variant="outline"
            className="border-white/10 text-gray-300 gap-2 shrink-0 h-9 text-xs">
            <ShieldCheck className="w-3.5 h-3.5" /> {t('nodes.certificate')}
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
                        <DropdownMenuItem onClick={() => openEdit(node)} className="text-gray-300 gap-2 min-h-[44px]">
                          <Pencil className="w-3.5 h-3.5" /> {t('common.edit')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={showCertificate} className="text-gray-300 gap-2 min-h-[44px]">
                          <ShieldCheck className="w-3.5 h-3.5" /> {t('nodes.showCertificate')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => healthCheck(node.id)} className="text-gray-300 gap-2 min-h-[44px]">
                          <RefreshCw className="w-3.5 h-3.5" /> {t('nodes.reconnect')}
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleDelete(node)} className="text-red-400 gap-2 min-h-[44px]">
                          <Trash2 className="w-3.5 h-3.5" /> {t('common.delete')}
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-1">
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase">{t('nodes.status')}</p>
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
                    <div>
                      <p className="text-[10px] text-gray-500 uppercase">{t('nodes.devices')}</p>
                      <div className="flex items-center gap-1 mt-0.5">
                        <Smartphone className="w-3 h-3 text-gray-500" />
                        <p className="text-xs text-gray-300">{node.connected_devices || 0}</p>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-1 border-t border-white/5">
                    <div className="flex items-center gap-1.5">
                      <ArrowUpDown className="w-3 h-3 text-gray-600" />
                      <p className="text-[10px] text-gray-600">
                        {formatBytes((node.traffic_upload || 0) + (node.traffic_download || 0))}
                      </p>
                    </div>
                    <p className="text-[10px] text-gray-600">
                      {t('nodes.port')}: {node.port || 62050} · {node.last_heartbeat ? new Date(node.last_heartbeat).toLocaleString('en-GB') : t('nodes.noHeartbeat')}
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
              {editing ? 'Update node details' : 'Add a new Lightline Node server'}
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
              <Label className="text-gray-400 text-xs uppercase">{t('nodes.port')}</Label>
              <Input type="number" value={form.port} onChange={(e) => setForm({ ...form, port: parseInt(e.target.value) || 62050 })}
                placeholder="62050" className="bg-black/50 border-white/10 font-mono text-sm text-gray-200" data-testid="node-port-input" />
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

      {/* Certificate Dialog (Marzban-style) */}
      <Dialog open={certDialogOpen} onOpenChange={setCertDialogOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-lg mx-4">
          <DialogHeader>
            <DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>{t('nodes.certDialogTitle')}</DialogTitle>
            <DialogDescription className="text-gray-500 text-sm">
              {t('nodes.certDialogDesc')} — <span className="font-mono text-cyan-400">ssl_client_cert.pem</span>
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="p-3 rounded-lg bg-black/50 border border-white/10 font-mono text-[10px] text-cyan-400 break-all select-all max-h-48 overflow-y-auto whitespace-pre-wrap">
              {certificate || 'Loading...'}
            </div>
            <div className="p-3 rounded-lg bg-zinc-900/50 border border-white/5 space-y-2">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">Setup Instructions</p>
              <p className="text-[11px] text-gray-300 leading-relaxed">
                1. Install Lightline Node on your server<br />
                2. Copy this certificate and paste it into:<br />
                <span className="font-mono text-cyan-400 text-[10px]">/var/lib/lightline-node/ssl_client_cert.pem</span><br />
                3. Run <span className="font-mono text-cyan-400 text-[10px]">docker compose up -d</span>
              </p>
            </div>
            <Button
              onClick={async () => {
                const ok = await copyToClipboard(certificate);
                if (ok) toast.success('Certificate copied');
                else toast.error('Copy failed — long-press the text above to copy manually');
              }}
              className="w-full bg-cyan-600 hover:bg-cyan-500 text-black font-semibold gap-2 min-h-[48px] active:scale-95 transition-transform touch-manipulation"
            >
              <Copy className="w-4 h-4" /> {t('nodes.copyCertificate')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
