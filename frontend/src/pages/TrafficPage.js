import { useState, useEffect } from 'react';
import { useI18n } from '@/contexts/I18nContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';
import { Loader2 } from 'lucide-react';
import api from '@/lib/api';
import { motion } from 'framer-motion';

const formatBytes = (b) => {
  if (!b) return '0 B';
  const k = 1024, s = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(b) / Math.log(k));
  return parseFloat((b / Math.pow(k, i)).toFixed(1)) + ' ' + s[i];
};

const formatGb = (b) => (b / 1_000_000_000).toFixed(2);

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-zinc-950 border border-white/10 rounded-lg p-3 shadow-xl">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className="text-sm text-cyan-400 font-mono">{formatBytes(payload[0].value)}</p>
    </div>
  );
};

export default function TrafficPage() {
  const [daily, setDaily] = useState([]);
  const [traffic, setTraffic] = useState({ by_user: [], by_node: [] });
  const [loading, setLoading] = useState(true);
  const { t } = useI18n();

  useEffect(() => {
    Promise.all([api.get('/traffic/daily'), api.get('/traffic')]).then(([d, tr]) => {
      setDaily(d.data); setTraffic(tr.data); setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center py-20"><Loader2 className="w-6 h-6 animate-spin text-cyan-400" /></div>
  );

  return (
    <div className="space-y-6" data-testid="traffic-page">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>{t('traffic.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">{t('traffic.last30Days')}</p>
      </div>

      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <Card className="ll-card border-white/5" data-testid="traffic-chart">
          <CardHeader><CardTitle className="text-base text-white" style={{ fontFamily: 'Outfit' }}>{t('traffic.daily')}</CardTitle></CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={daily}>
                  <defs>
                    <linearGradient id="fillTraffic" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} tickLine={false} axisLine={false}
                    tickFormatter={(d) => new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })} />
                  <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} tickLine={false} axisLine={false}
                    tickFormatter={(v) => formatGb(v) + ' GB'} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="bytes" stroke="#06b6d4" strokeWidth={2} fill="url(#fillTraffic)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      <Tabs defaultValue="user" className="space-y-4">
        <TabsList className="bg-white/5 border border-white/10">
          <TabsTrigger value="user" className="data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400" data-testid="tab-by-user">
            {t('traffic.byUser')}
          </TabsTrigger>
          <TabsTrigger value="node" className="data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400" data-testid="tab-by-node">
            {t('traffic.byNode')}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="user">
          <Card className="ll-card border-white/5">
            <CardContent className="p-0 overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="border-white/5 hover:bg-transparent">
                    <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('users.username')}</TableHead>
                    <TableHead className="text-gray-500 text-xs uppercase tracking-wider text-right">{t('traffic.totalTraffic')}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {traffic.by_user.map((u) => (
                    <TableRow key={u.user_id} className="border-white/5 hover:bg-white/[0.02]">
                      <TableCell className="text-gray-300">{u.username}</TableCell>
                      <TableCell className="text-right font-mono text-sm text-gray-400">{formatBytes(u.bytes)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="node">
          <Card className="ll-card border-white/5">
            <CardContent className="pt-6">
              <div className="h-[250px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={traffic.by_node}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 11 }} tickLine={false} axisLine={false} />
                    <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} tickLine={false} axisLine={false}
                      tickFormatter={(v) => formatGb(v) + ' GB'} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="bytes" fill="#06b6d4" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
