import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useI18n } from '@/contexts/I18nContext';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Shield, Loader2, Terminal, KeyRound, CheckCircle2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { motion } from 'framer-motion';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [needsTotp, setNeedsTotp] = useState(false);
  const [loading, setLoading] = useState(false);
  const [setupRequired, setSetupRequired] = useState(false);
  const [noLicense, setNoLicense] = useState(false);
  const [licenseInfo, setLicenseInfo] = useState(null);
  const [licenseKey, setLicenseKey] = useState('');
  const [activatingLicense, setActivatingLicense] = useState(false);
  const [checking, setChecking] = useState(true);
  const { login, user } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();

  const checkSetup = () => {
    api.get('/auth/check-setup').then(({ data }) => {
      setSetupRequired(data.setup_required);
      setNoLicense(!data.license_active);
      setLicenseInfo(data.license_info);
      setChecking(false);
    }).catch(() => setChecking(false));
  };

  useEffect(() => {
    if (user) navigate('/');
    checkSetup();
  }, [user, navigate]);

  const handleActivateLicense = async (e) => {
    e.preventDefault();
    if (!licenseKey.trim()) return;
    setActivatingLicense(true);
    try {
      const { data } = await api.post('/licenses/activate', { license_key: licenseKey.trim() });
      if (data.activated) {
        toast.success(`License activated! Expires in ${data.expires_in_days} days`);
        setNoLicense(false);
        setLicenseKey('');
        checkSetup();
      } else {
        toast.error(data.reason || 'Activation failed');
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Activation failed');
    }
    setActivatingLicense(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const result = await login(username, password, totpCode || undefined);
      if (result?.requires_totp) {
        setNeedsTotp(true);
        setLoading(false);
        return;
      }
      navigate('/');
    } catch (err) {
      toast.error(err.response?.data?.detail || t('login.error'));
    }
    setLoading(false);
  };

  if (checking) return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center">
      <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
    </div>
  );

  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute inset-0 ll-grid-bg" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-cyan-500/5 blur-3xl pointer-events-none" />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="relative w-full max-w-md"
      >
        <div className="ll-card p-8 space-y-8">
          <div className="text-center space-y-3">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center ll-glow">
              <Shield className="w-8 h-8 text-cyan-400" strokeWidth={1.5} />
            </div>
            <h1 className="text-3xl font-bold tracking-wide text-white" style={{ fontFamily: 'Outfit' }}>
              {t('login.title')}
            </h1>
            <p className="text-sm text-gray-500">{t('login.subtitle')}</p>
          </div>

          {/* License activation gate */}
          {noLicense && (
            <div className="space-y-4">
              <div className="p-4 rounded-lg border border-amber-500/20 bg-amber-500/5">
                <div className="flex items-start gap-3">
                  <KeyRound className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-sm font-medium text-amber-400">License Required</p>
                    <p className="text-xs text-gray-400 mt-1">Enter your license key to activate this panel</p>
                  </div>
                </div>
              </div>
              <form onSubmit={handleActivateLicense} className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-gray-400 text-xs uppercase tracking-wider">License Key</Label>
                  <Input
                    value={licenseKey}
                    onChange={(e) => setLicenseKey(e.target.value)}
                    placeholder="LL-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX"
                    className="bg-black/50 border-white/10 focus:border-cyan-500/50 h-11 text-gray-200 font-mono text-xs"
                    data-testid="license-key-input"
                    required
                  />
                </div>
                <Button
                  type="submit"
                  disabled={activatingLicense}
                  className="w-full h-11 bg-cyan-600 hover:bg-cyan-500 text-black font-semibold"
                  data-testid="license-activate-button"
                >
                  {activatingLicense ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Activate License'}
                </Button>
              </form>
            </div>
          )}

          {/* License active badge */}
          {!noLicense && licenseInfo && (
            <div className="p-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 flex items-center gap-3">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-emerald-400 font-medium">License Active</p>
                <p className="text-[10px] text-gray-500 font-mono truncate">{licenseInfo.key} — {licenseInfo.expires_in_days} days left</p>
              </div>
            </div>
          )}

          {/* Setup required notice */}
          {!noLicense && setupRequired && (
            <div className="p-4 rounded-lg border border-amber-500/20 bg-amber-500/5">
              <div className="flex items-start gap-3">
                <Terminal className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-amber-400">No admin account</p>
                  <p className="text-xs text-gray-400 mt-1 font-mono">docker exec -it lightline-backend python cli.py admin create</p>
                </div>
              </div>
            </div>
          )}

          {/* Login form — only shown when license is active and admin exists */}
          {!noLicense && !setupRequired && (
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <Label htmlFor="username" className="text-gray-400 text-xs uppercase tracking-wider">
                  {t('login.username')}
                </Label>
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="bg-black/50 border-white/10 focus:border-cyan-500/50 h-11 text-gray-200"
                  data-testid="login-username-input"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password" className="text-gray-400 text-xs uppercase tracking-wider">
                  {t('login.password')}
                </Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="bg-black/50 border-white/10 focus:border-cyan-500/50 h-11 text-gray-200"
                  data-testid="login-password-input"
                  required
                />
              </div>
              {needsTotp && (
                <div className="space-y-2">
                  <Label htmlFor="totp" className="text-gray-400 text-xs uppercase tracking-wider">
                    {t('login.totpCode')}
                  </Label>
                  <Input
                    id="totp"
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value)}
                    placeholder="000000"
                    maxLength={6}
                    className="bg-black/50 border-white/10 focus:border-cyan-500/50 h-11 text-gray-200 font-mono text-center text-lg tracking-[0.5em]"
                    data-testid="login-totp-input"
                    autoFocus
                    required
                  />
                  <p className="text-xs text-gray-500 text-center">Enter the 6-digit code from your authenticator app</p>
                </div>
              )}
              <Button
                type="submit"
                disabled={loading}
                className="w-full h-11 bg-cyan-600 hover:bg-cyan-500 text-black font-semibold shadow-[0_0_20px_rgba(6,182,212,0.3)] hover:shadow-[0_0_30px_rgba(6,182,212,0.5)] transition-shadow duration-300"
                data-testid="login-submit-button"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : t('login.submit')}
              </Button>
            </form>
          )}

          <p className="text-center text-[11px] text-gray-600">
            Lightline v1.0.0 — Secure VPN Management
          </p>
        </div>
      </motion.div>
    </div>
  );
}
