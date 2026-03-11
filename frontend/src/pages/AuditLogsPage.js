import { useState, useEffect } from 'react';
import { useI18n } from '@/contexts/I18nContext';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react';
import api from '@/lib/api';
import { motion } from 'framer-motion';

const actionColors = {
  login: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  node_created: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  node_deleted: 'bg-red-500/10 text-red-400 border-red-500/20',
  node_updated: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  user_created: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  user_deleted: 'bg-red-500/10 text-red-400 border-red-500/20',
  user_updated: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  user_node_switched: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  license_created: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  license_revoked: 'bg-red-500/10 text-red-400 border-red-500/20',
  settings_updated: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
  backup_created: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
  admin_setup: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
  totp_enabled: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  totp_disabled: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  bulk_node_switch: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
};

export default function AuditLogsPage() {
  const [data, setData] = useState({ logs: [], total: 0, page: 1 });
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const { t } = useI18n();
  const limit = 20;

  useEffect(() => {
    setLoading(true);
    api.get(`/audit-logs?page=${page}&limit=${limit}`).then(({ data }) => { setData(data); setLoading(false); }).catch(() => setLoading(false));
  }, [page]);

  const totalPages = Math.ceil(data.total / limit);

  return (
    <div className="space-y-6" data-testid="audit-page">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-white" style={{ fontFamily: 'Outfit' }}>{t('audit.title')}</h1>
        <p className="text-sm text-gray-500 mt-1">Track all administrative actions</p>
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
        <Card className="ll-card border-white/5">
          <CardContent className="p-0">
            <Table data-testid="audit-table">
              <TableHeader>
                <TableRow className="border-white/5 hover:bg-transparent">
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('audit.action')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('audit.details')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('audit.ipAddress')}</TableHead>
                  <TableHead className="text-gray-500 text-xs uppercase tracking-wider">{t('audit.timestamp')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow><TableCell colSpan={4} className="text-center py-12"><Loader2 className="w-5 h-5 animate-spin mx-auto text-gray-500" /></TableCell></TableRow>
                ) : data.logs.length === 0 ? (
                  <TableRow><TableCell colSpan={4} className="text-center py-12 text-gray-500">{t('common.noData')}</TableCell></TableRow>
                ) : data.logs.map((log) => (
                  <TableRow key={log.id} className="border-white/5 hover:bg-white/[0.02]">
                    <TableCell>
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-[11px] font-medium border ${actionColors[log.action] || 'bg-gray-500/10 text-gray-400 border-gray-500/20'}`}>
                        {log.action.replace(/_/g, ' ')}
                      </span>
                    </TableCell>
                    <TableCell className="text-gray-400 text-sm max-w-xs truncate">{log.details || '—'}</TableCell>
                    <TableCell className="font-mono text-xs text-gray-500">{log.ip_address || '—'}</TableCell>
                    <TableCell className="font-mono text-xs text-gray-500">{new Date(log.created_at).toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-4">
            <span className="text-xs text-gray-500">
              Page {page} of {totalPages} ({data.total} total)
            </span>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" disabled={page <= 1} onClick={() => setPage(p => p - 1)}
                className="text-gray-400 h-8" data-testid="audit-prev">
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <Button variant="ghost" size="sm" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}
                className="text-gray-400 h-8" data-testid="audit-next">
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
}
