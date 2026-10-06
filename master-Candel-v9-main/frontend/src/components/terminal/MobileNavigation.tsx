import { Link } from 'react-router-dom';
import { Activity, BarChart3, GitBranch, Settings2, Terminal, X } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

export const MobileNavigation = ({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent data-testid="mobile-navigation-dialog" showCloseButton={false} className="mobile-navigation-dialog">
      <DialogHeader><DialogTitle data-testid="mobile-navigation-title">Master Candle</DialogTitle><DialogDescription data-testid="mobile-navigation-description">Workspace</DialogDescription></DialogHeader>
      <Button variant="ghost" size="icon-sm" data-testid="mobile-navigation-close" aria-label="Close navigation" className="pair-picker-close" onClick={() => onOpenChange(false)}><X size={17} /></Button>
      <nav data-testid="mobile-navigation-links">{[
        { route: 'signals', title: 'Signals', icon: Activity },
        { route: 'analytics', title: 'Analytics', icon: BarChart3 },
        { route: 'flow', title: 'Flow map', icon: GitBranch },
        { route: 'logs', title: 'Logs', icon: Terminal },
        { route: 'settings', title: 'Settings', icon: Settings2 },
      ].map(({ route, title, icon: Icon }) => <Link key={route} data-testid={`mobile-nav-${route}`} to={`/${route}`} onClick={() => onOpenChange(false)}><Icon size={19} /><span>{title}</span></Link>)}</nav>
    </DialogContent>
  </Dialog>
);