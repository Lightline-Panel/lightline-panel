import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { useI18n } from '@/contexts/I18nContext';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Shield, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { motion } from 'framer-motion';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [setupMode, setSetupMode] = useState(false);
  const [checking, setChecking] = useState(true);
  const { login, user } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();

  useEffect(() => {
    if (user) navigate('/');
    api.get('/auth/check-setup').then(({ data }) => {
      setSetupMode(data.setup_required);
      setChecking(false);
    }).catch(() => setChecking(false));
  }, [user, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      if (setupMode) {
        await api.post('/auth/setup', { username, password });
        toast.success('Admin account created');
        setSetupMode(false);
      }
      await login(username, password);
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
            <p className="text-sm text-gray-500">{setupMode ? t('login.setupDesc') : t('login.subtitle')}</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-gray-400 text-xs uppercase tracking-wider">
                {t('login.username')}
              </Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                className="bg-black/50 border-white/10 focus:border-cyan-500/50 h-11"
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
                className="bg-black/50 border-white/10 focus:border-cyan-500/50 h-11"
                data-testid="login-password-input"
                required
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 bg-cyan-600 hover:bg-cyan-500 text-black font-semibold shadow-[0_0_20px_rgba(6,182,212,0.3)] hover:shadow-[0_0_30px_rgba(6,182,212,0.5)] transition-shadow duration-300"
              data-testid="login-submit-button"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : (setupMode ? t('login.setup') : t('login.submit'))}
            </Button>
          </form>

          <p className="text-center text-[11px] text-gray-600">
            Lightline v1.0.0 — Secure VPN Management
          </p>
        </div>
      </motion.div>
    </div>
  );
}
