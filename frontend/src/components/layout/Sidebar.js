import { NavLink, useLocation } from 'react-router-dom';
import { useI18n } from '@/contexts/I18nContext';
import { useAuth } from '@/contexts/AuthContext';
import {
  LayoutDashboard, Server, Users, BarChart3, Key,
  Settings, FileText, LogOut, Shield
} from 'lucide-react';
import { Button } from '@/components/ui/button';

const navItems = [
  { path: '/', key: 'dashboard', icon: LayoutDashboard },
  { path: '/users', key: 'users', icon: Users },
  { path: '/nodes', key: 'nodes', icon: Server },
  { path: '/traffic', key: 'traffic', icon: BarChart3 },
  { path: '/settings', key: 'settings', icon: Settings },
  { path: '/audit-logs', key: 'audit', icon: FileText },
];

export const Sidebar = ({ mobile, onClose }) => {
  const { t } = useI18n();
  const { logout } = useAuth();
  const location = useLocation();

  return (
    <aside
      className={`${
        mobile ? 'w-full' : 'fixed left-0 top-0 h-full w-64 hidden md:flex'
      } bg-black/90 border-r border-white/10 flex-col z-50`}
      data-testid="sidebar"
    >
      <div className="p-6 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-cyan-500/20 flex items-center justify-center">
            <Shield className="w-5 h-5 text-cyan-400" strokeWidth={1.5} />
          </div>
          <div>
            <h1 className="text-lg font-bold tracking-wide text-white" style={{ fontFamily: 'Outfit' }}>
              LIGHTLINE
            </h1>
            <p className="text-[10px] uppercase tracking-[0.2em] text-gray-500">VPN Panel</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
        {navItems.map(({ path, key, icon: Icon }) => {
          const isActive = location.pathname === path || (path !== '/' && location.pathname.startsWith(path));
          return (
            <NavLink
              key={path}
              to={path}
              onClick={onClose}
              data-testid={`sidebar-nav-${key}`}
              className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors duration-200 ${
                isActive
                  ? 'text-cyan-400 bg-cyan-950/40 border-r-2 border-cyan-500'
                  : 'text-gray-400 hover:text-cyan-400 hover:bg-cyan-950/20'
              }`}
            >
              <Icon className="w-[18px] h-[18px]" strokeWidth={1.5} />
              {t(`nav.${key}`)}
            </NavLink>
          );
        })}
      </nav>

      <div className="p-4 border-t border-white/10">
        <Button
          variant="ghost"
          className="w-full justify-start gap-3 text-gray-400 hover:text-red-400 hover:bg-red-950/20"
          onClick={() => { logout(); onClose?.(); }}
          data-testid="logout-button"
        >
          <LogOut className="w-[18px] h-[18px]" strokeWidth={1.5} />
          {t('common.logout')}
        </Button>
      </div>
    </aside>
  );
};
