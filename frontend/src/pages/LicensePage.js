import { useState, useEffect } from 'react';
import { useI18n } from '@/contexts/I18nContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Plus, Key, Trash2, Loader2, Copy, ShieldCheck } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { motion } from 'framer-motion';
import { copyToClipboard } from '@/lib/clipboard';

export default function LicensePage() {
  const [licenses, setLicenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [validateOpen, setValidateOpen] = useState(false);
  const [form, setForm] = useState({ expire_days: '30', max_servers: '1' });
  const [validateKey, setValidateKey] = useState('');
  const [validateResult, setValidateResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const { t } = useI18n();

  const fetchLicenses = () => {
    api.get('/licenses').then(({ data }) => { setLicenses(data); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(fetchLicenses, []);

  const handleCreate = async () => {
    setSaving(true);
    try {
      const { data } = await api.post('/licenses', { expire_days: parseInt(form.expire_days), max_servers: parseInt(form.max_servers) });
      toast.success(`License created: ${data.license_key}`);
      setCreateOpen(false); fetchLicenses();
    } catch (err) { toast.error('Error creating license'); }
    setSaving(false);
  };

  const handleRevoke = async (id) => {
    if (!window.confirm('Revoke this license?')) return;
    try { await api.delete(`/licenses/${id}`); toast.success('License revoked'); fetchLicenses(); } catch { toast.error('Error'); }
  };

  const handleValidate = async () => {
    try {
      const { data } = await api.post('/licenses/validate', { license_key: validateKey });
      setValidateResult(data);
    } catch { toast.error('Error validating'); }
  };

  const statusColor = (s) => {
    if (s === 'active') return 'default';
    if (s === 'revoked') return 'destructive';
    return 'secondary';
  };

  return (
    <div className="space-y-6" data-testid="license-page">
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-2xl sm:text-3xl font-bold text-white truncate" style={{ fontFamily: 'Outfit' }}>{t('licenses.title')}</h1>
            <p className="text-sm text-gray-500 mt-1 hidden sm:block">{t('licenses.subtitle')}</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button variant="outline" onClick={() => { setValidateOpen(true); setValidateResult(null); setValidateKey(''); }}
              className="border-white/10 text-gray-300 gap-2" data-testid="validate-license-button">
              <ShieldCheck className="w-4 h-4" /> <span className="hidden sm:inline">{t('licenses.validate')}</span>
            </Button>
            <Button onClick={() => setCreateOpen(true)} className="bg-cyan-600 hover:bg-cyan-500 text-black font-semibold gap-2" data-testid="create-license-button">
              <Plus className="w-4 h-4" /> <span className="hidden sm:inline">{t('licenses.createLicense')}</span><span className="sm:hidden">{t('common.add')}</span>
            </Button>
          </div>
        </div>
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <Card className="ll-card border-white/5 hidden md:block">
          <CardContent className="p-0 overflow-x-auto">
            <Table data-testid="license-table">
              <TableHeader>
                <TableRow className="border-white/5 hover:bg-transparent">
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('licenses.licenseKey')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('common.status')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('licenses.expireDays')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('licenses.maxServers')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('licenses.activatedServers')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider text-right">{t('common.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow><TableCell colSpan={6} className="text-center py-12"><Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-500" /></TableCell></TableRow>
                ) : licenses.length === 0 ? (
                  <TableRow><TableCell colSpan={6} className="text-center py-12 text-gray-500">{t('common.noData')}</TableCell></TableRow>
                ) : licenses.map((lic) => (
                  <TableRow key={lic.id} className="border-white/5 hover:bg-white/[0.02]">
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Key className="w-3.5 h-3.5 text-cyan-400" />
                        <span className="font-mono text-xs text-gray-300">{lic.license_key}</span>
                        <Button variant="ghost" size="icon" className="h-8 w-8 min-w-[32px] text-gray-500 touch-manipulation"
                          onClick={async () => { const ok = await copyToClipboard(lic.license_key); ok ? toast.success('Copied') : toast.error('Copy failed'); }}>
                          <Copy className="w-3.5 h-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                    <TableCell><Badge variant={statusColor(lic.status)} className="text-[10px] h-5">{lic.status}</Badge></TableCell>
                    <TableCell className="text-gray-400">{lic.expire_days} {t('licenses.days')}</TableCell>
                    <TableCell className="text-gray-400">{lic.max_servers}</TableCell>
                    <TableCell className="text-gray-400">{lic.activated_servers}</TableCell>
                    <TableCell className="text-right">
                      {lic.status === 'active' && (
                        <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-300 gap-1 h-7 text-xs"
                          onClick={() => handleRevoke(lic.id)} data-testid={`revoke-license-${lic.id}`}>
                          <Trash2 className="w-3 h-3" /> {t('licenses.revoke')}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Mobile card list */}
        <div className="md:hidden space-y-3">
          {loading ? (
            <div className="flex items-center justify-center py-12"><Loader2 className="w-5 h-5 animate-spin text-gray-500" /></div>
          ) : licenses.length === 0 ? (
            <p className="text-center py-12 text-gray-500">{t('common.noData')}</p>
          ) : licenses.map((lic) => (
            <Card key={lic.id} className="ll-card border-white/5">
              <CardContent className="p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <Badge variant={statusColor(lic.status)} className="text-[10px] h-5">{lic.status}</Badge>
                  {lic.status === 'active' && (
                    <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-300 gap-1 h-8 text-xs touch-manipulation"
                      onClick={() => handleRevoke(lic.id)}>
                      <Trash2 className="w-3 h-3" /> {t('licenses.revoke')}
                    </Button>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <p className="font-mono text-[11px] text-gray-300 truncate flex-1">{lic.license_key}</p>
                  <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0 text-gray-500 touch-manipulation"
                    onClick={async () => { const ok = await copyToClipboard(lic.license_key); ok ? toast.success('Copied') : toast.error('Copy failed'); }}>
                    <Copy className="w-3.5 h-3.5" />
                  </Button>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <p className="text-gray-500 uppercase text-[10px]">{t('users.expires')}</p>
                    <p className="text-gray-400">{lic.expire_days}d</p>
                  </div>
                  <div>
                    <p className="text-gray-500 uppercase text-[10px]">{t('licenses.max')}</p>
                    <p className="text-gray-400">{lic.max_servers}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 uppercase text-[10px]">{t('licenses.active')}</p>
                    <p className="text-gray-400">{lic.activated_servers}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </motion.div>

      {/* Create License Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-sm">
          <DialogHeader><DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>{t('licenses.createLicense')}</DialogTitle><DialogDescription className="text-gray-500 text-sm">{t('licenses.generateNew')}</DialogDescription></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('licenses.expireDays')}</Label>
              <Input type="number" value={form.expire_days} onChange={(e) => setForm({ ...form, expire_days: e.target.value })}
                className="bg-black/50 border-white/10 text-gray-200" data-testid="license-days-input" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('licenses.maxServers')}</Label>
              <Input type="number" value={form.max_servers} onChange={(e) => setForm({ ...form, max_servers: e.target.value })}
                className="bg-black/50 border-white/10 text-gray-200" data-testid="license-servers-input" />
            </div>
            <div className="flex gap-3 pt-2">
              <Button variant="ghost" onClick={() => setCreateOpen(false)} className="flex-1 text-gray-400">{t('common.cancel')}</Button>
              <Button onClick={handleCreate} disabled={saving} className="flex-1 bg-cyan-600 hover:bg-cyan-500 text-black font-semibold" data-testid="license-create-confirm">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : t('licenses.createLicense')}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Validate License Dialog */}
      <Dialog open={validateOpen} onOpenChange={setValidateOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-sm">
          <DialogHeader><DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>{t('licenses.validate')}</DialogTitle><DialogDescription className="text-gray-500 text-sm">{t('licenses.checkValidity')}</DialogDescription></DialogHeader>
          <div className="space-y-4 mt-2">
            <div className="space-y-1.5">
              <Label className="text-gray-400 text-xs uppercase">{t('licenses.licenseKey')}</Label>
              <Input value={validateKey} onChange={(e) => setValidateKey(e.target.value)} placeholder="LL-XXXX-XXXX-XXXX-XXXX"
                className="bg-black/50 border-white/10 font-mono text-xs text-gray-200" data-testid="validate-key-input" />
            </div>
            <Button onClick={handleValidate} className="w-full bg-cyan-600 hover:bg-cyan-500 text-black font-semibold" data-testid="validate-submit">{t('licenses.validate')}</Button>
            {validateResult && (
              <div className={`p-4 rounded-lg border ${validateResult.valid ? 'border-emerald-500/30 bg-emerald-500/10' : 'border-red-500/30 bg-red-500/10'}`}>
                <p className={`text-sm font-semibold ${validateResult.valid ? 'text-emerald-400' : 'text-red-400'}`}>
                  {validateResult.valid ? t('licenses.valid') : t('licenses.invalid')}
                </p>
                {validateResult.valid && <p className="text-xs text-gray-400 mt-1">{t('licenses.expiresIn')} {validateResult.expires_in_days} {t('licenses.days')}</p>}
                {validateResult.reason && <p className="text-xs text-gray-400 mt-1">{validateResult.reason}</p>}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
