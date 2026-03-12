import { useState } from 'react';
import { Sidebar } from './Sidebar';
import { useAuth } from '@/contexts/AuthContext';
import { useI18n } from '@/contexts/I18nContext';
import { Menu, Globe } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger
} from '@/components/ui/dropdown-menu';

const langLabels = { en: 'English', ru: 'Русский', tk: 'Türkmen' };

export default function Layout({ children }) {
  const { user } = useAuth();
  const { lang, setLang } = useI18n();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-[#050505] ll-grid-bg overflow-x-hidden">
      <Sidebar />

      <main className="flex-1 md:ml-64 min-h-screen relative w-0 min-w-0">
        {/* Top bar */}
        <header className="sticky top-0 z-40 flex items-center justify-between h-14 px-4 md:px-8 border-b border-white/5 bg-[#050505]/80 backdrop-blur-xl">
          <div className="flex items-center gap-3">
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden text-gray-400" data-testid="mobile-menu-toggle">
                  <Menu className="w-5 h-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="left" className="w-64 p-0 bg-[#050505] border-white/10">
                <Sidebar mobile onClose={() => setMobileOpen(false)} />
              </SheetContent>
            </Sheet>
          </div>

          <div className="flex items-center gap-2">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="gap-2 text-gray-400 hover:text-white" data-testid="language-selector">
                  <Globe className="w-4 h-4" />
                  <span className="text-xs uppercase">{lang}</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="bg-zinc-950 border-white/10">
                {Object.entries(langLabels).map(([code, label]) => (
                  <DropdownMenuItem
                    key={code}
                    onClick={() => setLang(code)}
                    className={`text-sm ${lang === code ? 'text-cyan-400' : 'text-gray-300'}`}
                    data-testid={`lang-${code}`}
                  >
                    {label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            {user && (
              <div className="hidden sm:flex items-center gap-2 pl-2 border-l border-white/10">
                <div className="w-7 h-7 rounded-full bg-cyan-500/20 flex items-center justify-center text-cyan-400 text-xs font-bold">
                  {user.username?.[0]?.toUpperCase()}
                </div>
                <span className="text-xs text-gray-400">{user.username}</span>
              </div>
            )}
          </div>
        </header>

        <div className="p-4 md:p-8 lg:p-10">
          {children}
        </div>
      </main>
    </div>
  );
}
