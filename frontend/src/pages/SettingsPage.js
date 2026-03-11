import { useState, useEffect } from 'react';
import { useI18n } from '@/contexts/I18nContext';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Download, Upload, Globe, Moon, Sun, Info, Shield } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { motion } from 'framer-motion';

export default function SettingsPage() {
  const { t, lang, setLang } = useI18n();
  const { user } = useAuth();
  const [isDark, setIsDark] = useState(() => document.documentElement.classList.contains('dark'));
  const [settings, setSettings] = useState({});

  useEffect(() => {
    api.get('/settings').then(({ data }) => setSettings(data)).catch(() => {});
  }, []);

  const toggleTheme = (dark) => {
    setIsDark(dark);
    if (dark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
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
                  <SelectTrigger className="bg-black/50 border-white/10" data-testid="settings-language-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-950 border-white/10">
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="ru">Русский</SelectItem>
                    <SelectItem value="tk">Türkmen</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Backup */}
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
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
      </div>
    </div>
  );
}
