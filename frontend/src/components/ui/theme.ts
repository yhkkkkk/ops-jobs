import type { GlobalThemeOverrides } from 'naive-ui'
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  FileUp,
  GitBranch,
  GitFork,
  GitMerge,
  Info,
  KeyRound,
  MoreHorizontal,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Search,
  Server,
  Settings2,
  ShieldCheck,
  Trash2,
  Users,
  Workflow,
} from 'lucide-vue-next'

/**
 * Shared tokens for new Naive UI surfaces.
 *
 * These values intentionally mirror the existing app.css tokens. Keeping the
 * mapping here gives the migration a single place to tune without changing
 * the legacy Arco pages that still rely on their own theme variables.
 */
export const platformThemeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#2f6feb',
    primaryColorHover: '#235fd1',
    primaryColorPressed: '#1e4fae',
    primaryColorSuppl: '#eaf2ff',
    successColor: '#16a34a',
    warningColor: '#d97706',
    errorColor: '#dc2626',
    infoColor: '#2f6feb',
    borderRadius: '8px',
    fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", "Microsoft YaHei", sans-serif',
    fontFamilyMono: 'ui-monospace, "JetBrains Mono", "SFMono-Regular", Menlo, Consolas, monospace',
  },
}

/** Stable icon vocabulary for migrated platform surfaces. */
export const platformIcons = {
  activity: Activity,
  alert: AlertTriangle,
  check: CheckCircle2,
  clock: Clock3,
  fileTransfer: FileUp,
  branch: GitBranch,
  fork: GitFork,
  merge: GitMerge,
  info: Info,
  key: KeyRound,
  more: MoreHorizontal,
  edit: Pencil,
  play: Play,
  add: Plus,
  refresh: RefreshCw,
  search: Search,
  server: Server,
  settings: Settings2,
  security: ShieldCheck,
  delete: Trash2,
  users: Users,
  workflow: Workflow,
} as const

export type PlatformIconName = keyof typeof platformIcons

export const platformIconSize = 16
