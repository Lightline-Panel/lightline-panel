import { useState, useEffect } from 'react';
import { useI18n } from '@/contexts/I18nContext';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Download, Upload, Globe, Moon, Sun, Info, Shield, Loader2, ShieldCheck, ShieldOff, Server } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { motion } from 'framer-motion';

export default function SettingsPage() {
  const { t, lang, setLang } = useI18n();
  const { user } = useAuth();
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'));
  const [settings, setSettings] = useState({});
  const [totpSetup, setTotpSetup] = useState(null);
  const [totpCode, setTotpCode] = useState('');
  const [totpLoading, setTotpLoading] = useState(false);
  const [disableOpen, setDisableOpen] = useState(false);
  const [disableCode, setDisableCode] = useState('');
  const [ssPort, setSsPort] = useState('8388');
  const [savingPort, setSavingPort] = useState(false);

  useEffect(() => {
    api.get('/settings').then(({ data }) => {
      setSettings(data);
      if (data.ss_port) setSsPort(data.ss_port);
    }).catch(() => {});
  }, []);

  const toggleTheme = (dark) => {
    setIsDark(dark);
    if (dark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('lightline_theme', dark ? 'dark' : 'light');
  };

  const handleBackup = async () => {
    try {
      const { data } = await api.post('/backup');
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `lightline-backup-${new Date().toISOString().split('T')[0]}.json`;
      a.click(); URL.revokeObjectURL(url);
      toast.success('Backup downloaded');
    } catch { toast.error('Backup failed'); }
  };

  const handleTotpSetup = async () => {
    setTotpLoading(true);
    try {
      const { data } = await api.post('/auth/totp/setup');
      setTotpSetup(data);
      setTotpCode('');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to setup TOTP');
    }
    setTotpLoading(false);
  };

  const handleTotpConfirm = async () => {
    if (!totpCode || totpCode.length !== 6) { toast.error('Enter a 6-digit code'); return; }
    setTotpLoading(true);
    try {
      await api.post('/auth/totp/confirm', { secret: totpSetup.secret, code: totpCode });
      toast.success('2FA enabled successfully');
      setTotpSetup(null);
      setTotpCode('');
      window.location.reload();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Invalid code');
    }
    setTotpLoading(false);
  };

  const handleTotpDisable = async () => {
    if (!disableCode || disableCode.length !== 6) { toast.error('Enter a 6-digit code'); return; }
    try {
      await api.post('/auth/totp/disable', { totp_code: disableCode });
      toast.success('2FA disabled');
      setDisableOpen(false);
      setDisableCode('');
      window.location.reload();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Invalid code');
    }
  };

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>{t('settings.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">Configure panel preferences</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Appearance */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="ll-card border-white/5">
            <CardHeader>
              <CardTitle className="text-base text-white flex items-center gap-2" style={{ fontFamily: 'Outfit' }}>
                <Moon className="w-4 h-4 text-cyan-400" /> {t('settings.theme')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label className="text-gray-300">{isDark ? t('settings.darkMode') : t('settings.lightMode')}</Label>
                  <p className="text-xs text-gray-500">Toggle between dark and light themes</p>
                </div>
                <Switch checked={isDark} onCheckedChange={toggleTheme} data-testid="theme-switch" />
              </div>

              <Separator className="bg-white/5" />

              <div className="space-y-2">
                <Label className="text-gray-400 text-xs uppercase flex items-center gap-2">
                  <Globe className="w-3.5 h-3.5" /> {t('settings.language')}
                </Label>
                <Select value={lang} onValueChange={setLang}>
                  <SelectTrigger className="bg-black/50 border-white/10 text-gray-200" data-testid="settings-language-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-950 border-white/10 text-gray-200">
                    <SelectItem value="en" className="text-gray-200 focus:text-white focus:bg-cyan-900/30">English</SelectItem>
                    <SelectItem value="ru" className="text-gray-200 focus:text-white focus:bg-cyan-900/30">Русский</SelectItem>
                    <SelectItem value="tk" className="text-gray-200 focus:text-white focus:bg-cyan-900/30">Türkmen</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Shadowsocks Port */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card className="ll-card border-white/5">
            <CardHeader>
              <CardTitle className="text-base text-white flex items-center gap-2" style={{ fontFamily: 'Outfit' }}>
                <Server className="w-4 h-4 text-cyan-400" /> Shadowsocks Port
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-gray-400">Global SS port used by all nodes. Changing this will affect new connections.</p>
              <div className="flex gap-3 items-end">
                <div className="flex-1 space-y-1.5">
                  <Label className="text-gray-400 text-xs uppercase">Port</Label>
                  <Input type="number" value={ssPort} onChange={(e) => setSsPort(e.target.value)}
                    className="bg-black/50 border-white/10 font-mono text-gray-200" data-testid="ss-port-input" />
                </div>
                <Button onClick={async () => {
                  setSavingPort(true);
                  try {
                    await api.put('/settings', { settings: { ss_port: ssPort } });
                    toast.success('SS port updated');
                  } catch { toast.error('Failed to save'); }
                  setSavingPort(false);
                }} disabled={savingPort}
                  className="bg-cyan-600 hover:bg-cyan-500 text-black font-semibold" data-testid="ss-port-save">
                  {savingPort ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Backup */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <Card className="ll-card border-white/5">
            <CardHeader>
              <CardTitle className="text-base text-white flex items-center gap-2" style={{ fontFamily: 'Outfit' }}>
                <Download className="w-4 h-4 text-cyan-400" /> {t('settings.backup')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-gray-400">Export all panel data including nodes, users, licenses, and settings.</p>
              <div className="flex gap-3">
                <Button onClick={handleBackup} className="bg-cyan-600 hover:bg-cyan-500 text-black font-semibold gap-2" data-testid="backup-button">
                  <Download className="w-4 h-4" /> {t('settings.createBackup')}
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Panel Info */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Card className="ll-card border-white/5">
            <CardHeader>
              <CardTitle className="text-base text-white flex items-center gap-2" style={{ fontFamily: 'Outfit' }}>
                <Info className="w-4 h-4 text-cyan-400" /> {t('settings.panelInfo')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">{t('settings.version')}</span>
                <span className="font-mono text-cyan-400">1.0.0</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">{t('settings.mode')}</span>
                <span className="font-mono text-amber-400">mock</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Environment</span>
                <span className="font-mono text-gray-400">development</span>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Admin Profile */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <Card className="ll-card border-white/5">
            <CardHeader>
              <CardTitle className="text-base text-white flex items-center gap-2" style={{ fontFamily: 'Outfit' }}>
                <Shield className="w-4 h-4 text-cyan-400" /> Admin Profile
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {user && (
                <>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Username</span>
                    <span className="text-gray-300">{user.username}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Role</span>
                    <span className="font-mono text-cyan-400">{user.role}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500">Created</span>
                    <span className="font-mono text-xs text-gray-500">{user.created_at ? new Date(user.created_at).toLocaleDateString() : '—'}</span>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </motion.div>

        {/* 2FA Security */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
          <Card className="ll-card border-white/5">
            <CardHeader>
              <CardTitle className="text-base text-white flex items-center gap-2" style={{ fontFamily: 'Outfit' }}>
                <ShieldCheck className="w-4 h-4 text-cyan-400" /> {t('settings.twoFactor')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-gray-400">{t('settings.twoFactorDesc')}</p>
              <div className="flex items-center justify-between">
                <div className="space-y-1">
                  <Label className="text-gray-300">{t('settings.twoFactorStatus')}</Label>
                  <p className="text-xs text-gray-500">
                    {user?.totp_enabled ? t('settings.twoFactorEnabled') : t('settings.twoFactorDisabled')}
                  </p>
                </div>
                <div className={`w-2.5 h-2.5 rounded-full ${user?.totp_enabled ? 'll-status-online' : 'll-status-offline'}`} />
              </div>
              {user?.totp_enabled ? (
                <Button variant="outline" onClick={() => { setDisableOpen(true); setDisableCode(''); }}
                  className="w-full border-red-500/20 text-red-400 hover:bg-red-500/10 gap-2" data-testid="disable-2fa-button">
                  <ShieldOff className="w-4 h-4" /> {t('settings.disable2FA')}
                </Button>
              ) : (
                <Button onClick={handleTotpSetup} disabled={totpLoading}
                  className="w-full bg-cyan-600 hover:bg-cyan-500 text-black font-semibold gap-2" data-testid="enable-2fa-button">
                  {totpLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                  {t('settings.enable2FA')}
                </Button>
              )}
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* TOTP Setup Dialog */}
      <Dialog open={!!totpSetup} onOpenChange={() => setTotpSetup(null)}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-sm mx-4">
          <DialogHeader>
            <DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>{t('settings.setup2FA')}</DialogTitle>
            <DialogDescription className="text-gray-500 text-sm">Scan this QR code with your authenticator app</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col items-center gap-4 py-4">
            {totpSetup?.qr_code && (
              <div className="rounded-xl overflow-hidden">
                <img src={totpSetup.qr_code} alt="TOTP QR Code" className="w-48 h-48" data-testid="totp-qr-code" />
              </div>
            )}
            <div className="w-full space-y-1 px-2">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider text-center">Manual Entry Key</p>
              <p className="font-mono text-xs text-cyan-400 text-center break-all bg-black/50 rounded-lg p-2 border border-white/5 select-all">
                {totpSetup?.secret}
              </p>
            </div>
            <div className="w-full space-y-2">
              <Label className="text-gray-400 text-xs uppercase">Verification Code</Label>
              <Input value={totpCode} onChange={(e) => setTotpCode(e.target.value)}
                placeholder="000000" maxLength={6}
                className="bg-black/50 border-white/10 text-gray-200 font-mono text-center text-lg tracking-[0.5em]"
                data-testid="totp-confirm-input" />
            </div>
            <div className="flex gap-3 w-full">
              <Button variant="ghost" onClick={() => setTotpSetup(null)} className="flex-1 text-gray-400">{t('common.cancel')}</Button>
              <Button onClick={handleTotpConfirm} disabled={totpLoading}
                className="flex-1 bg-cyan-600 hover:bg-cyan-500 text-black font-semibold" data-testid="totp-confirm-button">
                {totpLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : t('common.confirm')}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* Disable 2FA Dialog */}
      <Dialog open={disableOpen} onOpenChange={setDisableOpen}>
        <DialogContent className="bg-zinc-950 border-white/10 max-w-sm mx-4">
          <DialogHeader>
            <DialogTitle className="text-white" style={{ fontFamily: 'Outfit' }}>{t('settings.disable2FA')}</DialogTitle>
            <DialogDescription className="text-gray-500 text-sm">Enter your current TOTP code to disable 2FA</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            <Input value={disableCode} onChange={(e) => setDisableCode(e.target.value)}
              placeholder="000000" maxLength={6}
              className="bg-black/50 border-white/10 text-gray-200 font-mono text-center text-lg tracking-[0.5em]"
              data-testid="totp-disable-input" />
            <div className="flex gap-3">
              <Button variant="ghost" onClick={() => setDisableOpen(false)} className="flex-1 text-gray-400">{t('common.cancel')}</Button>
              <Button onClick={handleTotpDisable}
                className="flex-1 bg-red-600 hover:bg-red-500 text-white font-semibold" data-testid="totp-disable-confirm">
                {t('settings.disable2FA')}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
