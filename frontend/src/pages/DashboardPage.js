import { useState, useEffect } from 'react';
import { useI18n } from '@/contexts/I18nContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Server, Users, Activity, Key, ArrowUpRight, ArrowDownRight } from 'lucide-react';
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
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.4, delay }}
  >
    <Card className="ll-card border-white/5 hover:border-white/10 transition-colors duration-300 group" data-testid={`stat-${label.toLowerCase().replace(/\s/g, '-')}`}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-wider text-gray-500 font-medium">{label}</p>
            <p className="text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>{value}</p>
            {sub && <p className="text-xs text-gray-500">{sub}</p>}
          </div>
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
            <Icon className="w-5 h-5" strokeWidth={1.5} />
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
    <div className="space-y-6 animate-pulse">
      <div className="h-8 w-48 bg-white/5 rounded" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <div key={i} className="h-32 bg-white/5 rounded-xl" />)}
      </div>
    </div>
  );

  return (
    <div className="space-y-8" data-testid="dashboard-page">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>
          {t('dashboard.title')}
        </h1>
        <p className="text-sm text-gray-500 mt-1">Lightline VPN Panel Overview</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
        <StatCard icon={Server} label={t('dashboard.totalNodes')} value={data.nodes.total}
          sub={`${data.nodes.online} ${t('common.online')} / ${data.nodes.offline} ${t('common.offline')}`}
          color="bg-cyan-500/10 text-cyan-400" delay={0} />
        <StatCard icon={Users} label={t('dashboard.totalUsers')} value={data.users.total}
          sub={`${data.users.active} ${t('common.active')}`}
          color="bg-indigo-500/10 text-indigo-400" delay={0.1} />
        <StatCard icon={Activity} label={t('dashboard.trafficToday')} value={formatBytes(data.traffic.today)}
          sub={`${t('dashboard.trafficTotal')}: ${formatBytes(data.traffic.total)}`}
          color="bg-emerald-500/10 text-emerald-400" delay={0.2} />
        <StatCard icon={Key} label={t('dashboard.licenseStatus')} value={data.license.active ? t('common.active') : 'N/A'}
          sub={data.license.key || 'No license'}
          color="bg-amber-500/10 text-amber-400" delay={0.3} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-6">
        {/* Node Health */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}>
          <Card className="ll-card border-white/5" data-testid="node-health-card">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-white" style={{ fontFamily: 'Outfit' }}>
                {t('dashboard.nodeHealth')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {data.node_health.length === 0 ? (
                <p className="text-sm text-gray-500">{t('common.noData')}</p>
              ) : data.node_health.map((node) => (
                <div key={node.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-white/[0.02] transition-colors">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${node.status === 'online' ? 'll-status-online' : node.status === 'offline' ? 'll-status-offline' : 'll-status-unknown'}`} />
                    <span className="text-sm text-gray-300">{node.name}</span>
                    {node.country && <span className="text-xs text-gray-600 font-mono">{node.country}</span>}
                  </div>
                  <Badge variant={node.status === 'online' ? 'default' : 'destructive'} className="text-[10px] h-5">
                    {node.status === 'online' ? (
                      <><ArrowUpRight className="w-3 h-3 mr-1" />{t('common.online')}</>
                    ) : (
                      <><ArrowDownRight className="w-3 h-3 mr-1" />{t('common.offline')}</>
                    )}
                  </Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </motion.div>

        {/* Recent Activity */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}>
          <Card className="ll-card border-white/5" data-testid="recent-activity-card">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-white" style={{ fontFamily: 'Outfit' }}>
                {t('dashboard.recentActivity')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-1">
              {data.recent_activity.length === 0 ? (
                <p className="text-sm text-gray-500">{t('common.noData')}</p>
              ) : data.recent_activity.map((log) => (
                <div key={log.id} className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-white/[0.02] transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="w-1.5 h-1.5 rounded-full bg-cyan-500/50" />
                    <div>
                      <span className="text-sm text-gray-300">{log.action.replace(/_/g, ' ')}</span>
                      {log.details && <p className="text-xs text-gray-600 mt-0.5">{log.details}</p>}
                    </div>
                  </div>
                  <span className="text-[10px] text-gray-600 font-mono whitespace-nowrap">
                    {new Date(log.created_at).toLocaleDateString()}
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
