export type RegistrationsTabId = 'inscriptions' | 'guichet' | 'moderation' | 'communications';

export interface RegistrationsNavigationProps {
  activeTab: RegistrationsTabId;
  onTabChange: (tab: RegistrationsTabId) => void;
  pendingCount: number;
  offlineCount: number;
  totalCount: number;
}

