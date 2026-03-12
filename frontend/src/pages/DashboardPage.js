import { useState, useEffect } from 'react';
import { useI18n } from '@/contexts/I18nContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Server, Users, Activity, Key, ArrowUpRight, ArrowDownRight, Smartphone } from 'lucide-react';
import api from '@/lib/api';
import { motion } from 'framer-motion';

const formatBytes = (bytes) => {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
};

const StatCard = ({ icon: Icon, label, value, sub, color, delay }) => (
  <motion.div
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.3, delay }}
  >
    <Card className="ll-card border-white/5 hover:border-white/10 transition-colors duration-300" data-testid={`stat-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <CardContent className="p-3 sm:p-5">
        <div className="flex items-center gap-3 sm:flex-col sm:items-start sm:gap-0">
          <div className={`w-8 h-8 sm:w-9 sm:h-9 rounded-lg flex items-center justify-center shrink-0 sm:mb-3 ${color}`}>
            <Icon className="w-4 h-4 sm:w-[18px] sm:h-[18px]" strokeWidth={1.5} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-[10px] sm:text-xs uppercase tracking-wider text-gray-500 font-medium truncate">{label}</p>
            <p className="text-xl sm:text-2xl lg:text-3xl font-bold text-white leading-tight" style={{ fontFamily: 'Outfit' }}>{value}</p>
            {sub && <p className="text-[10px] sm:text-xs text-gray-500 truncate mt-0.5">{sub}</p>}
          </div>
        </div>
      </CardContent>
    </Card>
  </motion.div>
);

export default function DashboardPage() {
  const [data, setData] = useState(null);
  const { t } = useI18n();

  useEffect(() => {
    api.get('/dashboard').then(({ data }) => setData(data)).catch(console.error);
  }, []);

  if (!data) return (
    <div className="space-y-4 animate-pulse">
      <div className="h-7 w-36 bg-white/5 rounded" />
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 sm:gap-4">
        {[...Array(5)].map((_, i) => <div key={i} className="h-20 sm:h-28 bg-white/5 rounded-xl" />)}
      </div>
    </div>
  );

  return (
    <div className="space-y-5 sm:space-y-8" data-testid="dashboard-page">
      <div>
        <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>
          {t('dashboard.title')}
        </h1>
        <p className="text-xs sm:text-sm text-gray-500 mt-0.5">{t('dashboard.overview')}</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5 sm:gap-4">
        <StatCard icon={Server} label={t('dashboard.totalNodes')} value={data.nodes.total}
          sub={`${data.nodes.online} online / ${data.nodes.offline} off`}
          color="bg-cyan-500/10 text-cyan-400" delay={0} />
        <StatCard icon={Users} label={t('dashboard.totalUsers')} value={data.users.total}
          sub={`${data.users.active} ${t('common.active')}`}
          color="bg-indigo-500/10 text-indigo-400" delay={0.05} />
        <StatCard icon={Activity} label={t('dashboard.trafficToday')} value={formatBytes(data.traffic.today)}
          sub={`Total: ${formatBytes(data.traffic.total)}`}
          color="bg-emerald-500/10 text-emerald-400" delay={0.1} />
        <StatCard icon={Smartphone} label={t('dashboard.connectedDevices')} value={data.connected_devices || 0}
          sub={data.connected_ips?.length ? `${data.connected_ips.length} IPs` : 'No connections'}
          color="bg-purple-500/10 text-purple-400" delay={0.15} />
        <StatCard icon={Key} label={t('dashboard.licenseStatus')} value={data.license.active ? t('common.active') : 'N/A'}
          sub={data.license.key ? (data.license.days_left !== null ? `${data.license.days_left}d left` : '✓') : 'No license'}
          color={data.license.days_left !== null && data.license.days_left <= 7 ? "bg-red-500/10 text-red-400" : "bg-amber-500/10 text-amber-400"} delay={0.2} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 sm:gap-4 lg:gap-6">
        {/* Node Health */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25 }}>
          <Card className="ll-card border-white/5" data-testid="node-health-card">
            <CardHeader className="px-3 sm:px-6 py-3 pb-2">
              <CardTitle className="text-sm sm:text-base font-semibold text-white" style={{ fontFamily: 'Outfit' }}>
                {t('dashboard.nodeHealth')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-3 sm:px-6 pb-3 space-y-1">
              {data.node_health.length === 0 ? (
                <p className="text-xs sm:text-sm text-gray-500 py-2">{t('common.noData')}</p>
              ) : data.node_health.map((node) => (
                <div key={node.id} className="flex items-center justify-between py-1.5 sm:py-2 px-2 sm:px-3 rounded-lg hover:bg-white/[0.02] transition-colors">
                  <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                    <div className={`w-1.5 h-1.5 sm:w-2 sm:h-2 rounded-full shrink-0 ${node.status === 'online' ? 'll-status-online' : node.status === 'offline' ? 'll-status-offline' : 'll-status-unknown'}`} />
                    <span className="text-xs sm:text-sm text-gray-300 truncate">{node.name}</span>
                    {node.country && <span className="text-[10px] sm:text-xs text-gray-600 font-mono shrink-0">{node.country}</span>}
                  </div>
                  <Badge variant={node.status === 'online' ? 'default' : 'destructive'} className="text-[9px] sm:text-[10px] h-4 sm:h-5 shrink-0 ml-2">
                    {node.status === 'online' ? (
                      <><ArrowUpRight className="w-2.5 h-2.5 sm:w-3 sm:h-3 mr-0.5" />{t('common.online')}</>
                    ) : (
                      <><ArrowDownRight className="w-2.5 h-2.5 sm:w-3 sm:h-3 mr-0.5" />{t('common.offline')}</>
                    )}
                  </Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>

        {/* Recent Activity */}
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <Card className="ll-card border-white/5" data-testid="recent-activity-card">
            <CardHeader className="px-3 sm:px-6 py-3 pb-2">
              <CardTitle className="text-sm sm:text-base font-semibold text-white" style={{ fontFamily: 'Outfit' }}>
                {t('dashboard.recentActivity')}
              </CardTitle>
            </CardHeader>
            <CardContent className="px-3 sm:px-6 pb-3 space-y-0.5">
              {data.recent_activity.length === 0 ? (
                <p className="text-xs sm:text-sm text-gray-500 py-2">{t('common.noData')}</p>
              ) : data.recent_activity.map((log) => (
                <div key={log.id} className="flex items-center justify-between py-1.5 sm:py-2 px-2 sm:px-3 rounded-lg hover:bg-white/[0.02] transition-colors gap-2">
                  <div className="flex items-center gap-2 sm:gap-3 min-w-0">
                    <div className="w-1 h-1 sm:w-1.5 sm:h-1.5 rounded-full bg-cyan-500/50 shrink-0" />
                    <div className="min-w-0">
                      <span className="text-xs sm:text-sm text-gray-300 block truncate">{log.action.replace(/_/g, ' ')}</span>
                      {log.details && <p className="text-[10px] sm:text-xs text-gray-600 truncate">{log.details}</p>}
                    </div>
                  </div>
                  <span className="text-[9px] sm:text-[10px] text-gray-600 font-mono whitespace-nowrap shrink-0">
                    {new Date(log.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
