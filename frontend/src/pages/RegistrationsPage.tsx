import React, { useState, useEffect, useMemo } from 'react';
import {
  ArrowLeft,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Receipt,
  Banknote,
  Gift,
  CreditCard,
  Layers,
  FileText,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Check,
  X,
  XCircle,
  ShieldCheck,
  RotateCcw,
  AlertTriangle,
  Mail,
  ChevronDown,
  FileSpreadsheet,
  Printer,
  PlusCircle,
} from 'lucide-react';
import { EventModel } from '../types/event';
import {
  AdminOrder,
  DashboardStats,
  getCancellationReasonLabel,
  BulkEventCancelResponse,
} from '../types/order';
import {
  fetchEventOrders,
  fetchEventDashboardStats,
  updateEvent,
  approveOrder,
  rejectOrder,
  refundOrder,
  rejectCancellationRequest,
  cancelAndRefundAllEventOrders,
  getAdminCheckinPdfUrl,
  getAdminCheckinXlsxUrl,
} from '../lib/api';
import { BroadcastModal } from '../components/BroadcastModal';
import { RegistrationsTabId } from './registrations/types';
import { RegistrationsTab, SortField, SortOrder } from './registrations/RegistrationsTab';
import { GuichetTab } from './registrations/GuichetTab';
import { ModerationTab } from './registrations/ModerationTab';
import { CommunicationsTab } from './registrations/CommunicationsTab';

interface RegistrationsPageProps {
  event: EventModel;
  onBack: () => void;
  onOpenEditor?: () => void;
}

function getInitialTab(): RegistrationsTabId {
  if (typeof window === 'undefined') return 'inscriptions';
  try {
    const params = new URLSearchParams(window.location.search);
    const tab = params.get('tab');
    if (
      tab === 'guichet' ||
      tab === 'moderation' ||
      tab === 'communications' ||
      tab === 'inscriptions'
    ) {
      return tab;
    }
  } catch {
    // fallback
  }
  return 'inscriptions';
}

export const RegistrationsPage: React.FC<RegistrationsPageProps> = ({
  event,
  onBack,
  onOpenEditor,
}) => {
  const [activeTab, setActiveTab] = useState<RegistrationsTabId>(getInitialTab());
  const [orders, setOrders] = useState<AdminOrder[]>([]);
  const [allOrders, setAllOrders] = useState<AdminOrder[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Moderation state
  const [isModerated, setIsModerated] = useState<boolean>(event.manual_approval_required ?? false);
  const [updatingModeration, setUpdatingModeration] = useState<boolean>(false);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'pending_approval' | 'confirmed' | 'offline' | 'cancellation_requested' | 'refunded' | 'cancelled' | 'pending' | 'rejected'
  >('all');

  // Sorting
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  // Modals & Action loading state
  const [approveModalOrder, setApproveModalOrder] = useState<AdminOrder | null>(null);
  const [rejectModalOrder, setRejectModalOrder] = useState<AdminOrder | null>(null);
  const [rejectReason, setRejectReason] = useState<string>('');
  const [modalError, setModalError] = useState<string | null>(null);
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Arbitration & Bulk Cancel Modals
  const [refundModalOrder, setRefundModalOrder] = useState<AdminOrder | null>(null);
  const [refundReason, setRefundReason] = useState<string>('');
  const [rejectCancellationModalOrder, setRejectCancellationModalOrder] = useState<AdminOrder | null>(null);
  const [rejectCancellationReason, setRejectCancellationReason] = useState<string>('');
  const [isBulkCancelModalOpen, setIsBulkCancelModalOpen] = useState<boolean>(false);
  const [bulkConfirmationText, setBulkConfirmationText] = useState<string>('');
  const [bulkCancelReason, setBulkCancelReason] = useState<string>('');
  const [bulkCancelLoading, setBulkCancelLoading] = useState<boolean>(false);
  const [bulkCancelReport, setBulkCancelReport] = useState<BulkEventCancelResponse | null>(null);
  const [currentEventStatus, setCurrentEventStatus] = useState<string>(event.status || 'published');

  // Broadcast Modal & Row Selection
  const [isBroadcastModalOpen, setIsBroadcastModalOpen] = useState<boolean>(false);
  const [selectedOrderIds, setSelectedOrderIds] = useState<Set<string>>(new Set());

  // Check-in Export Dropdown
  const [isExportMenuOpen, setIsExportMenuOpen] = useState<boolean>(false);
  const exportMenuRef = React.useRef<HTMLDivElement>(null);

  // Listen to popstate to sync back/forward navigation
  useEffect(() => {
    const handlePopState = () => {
      setActiveTab(getInitialTab());
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleTabChange = (tab: RegistrationsTabId) => {
    setActiveTab(tab);
    try {
      const url = new URL(window.location.href);
      if (tab === 'inscriptions') {
        url.searchParams.delete('tab');
      } else {
        url.searchParams.set('tab', tab);
      }
      window.history.pushState({}, '', url.toString());
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setIsExportMenuOpen(false);
      }
    };
    if (isExportMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isExportMenuOpen]);

  useEffect(() => {
    setIsModerated(event.manual_approval_required ?? false);
  }, [event.manual_approval_required]);

  useEffect(() => {
    setCurrentEventStatus(event.status || 'published');
  }, [event.status]);

  // Debounce search input by 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [orderRes, allOrdersRes, statsRes] = await Promise.all([
        fetchEventOrders(event.id, statusFilter, debouncedSearch),
        fetchEventOrders(event.id),
        fetchEventDashboardStats(event.id),
      ]);
      setOrders(orderRes.items);
      setAllOrders(allOrdersRes.items);
      setStats(orderRes.stats || statsRes);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors du chargement des inscriptions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [event.id, statusFilter, debouncedSearch]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('asc');
    }
  };

  const sortedOrders = useMemo(() => {
    const list = [...orders];
    list.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case 'date': {
          const tA = a.created_at ? new Date(a.created_at).getTime() : 0;
          const tB = b.created_at ? new Date(b.created_at).getTime() : 0;
          cmp = tA - tB;
          break;
        }
        case 'name':
          cmp = (a.full_name || '').localeCompare(b.full_name || '', 'fr', { sensitivity: 'base' });
          break;
        case 'stand': {
          const sA = (a.spot_labels || []).join(', ');
          const sB = (b.spot_labels || []).join(', ');
          cmp = sA.localeCompare(sB, 'fr', { numeric: true, sensitivity: 'base' });
          break;
        }
        case 'amount':
          cmp = a.total_price_cents - b.total_price_cents;
          break;
        case 'status':
          cmp = (a.status || '').localeCompare(b.status || '');
          break;
      }
      return sortOrder === 'asc' ? cmp : -cmp;
    });
    return list;
  }, [orders, sortField, sortOrder]);

  // Selection helpers for broadcast
  const visibleConfirmedOrders = useMemo(() => {
    return sortedOrders.filter((o) => o.status === 'confirmed');
  }, [sortedOrders]);

  const isAllConfirmedSelected = useMemo(() => {
    if (visibleConfirmedOrders.length === 0) return false;
    return visibleConfirmedOrders.every((o) => selectedOrderIds.has(o.id));
  }, [visibleConfirmedOrders, selectedOrderIds]);

  const handleToggleSelectAll = () => {
    if (isAllConfirmedSelected) {
      setSelectedOrderIds((prev) => {
        const next = new Set(prev);
        visibleConfirmedOrders.forEach((o) => next.delete(o.id));
        return next;
      });
    } else {
      setSelectedOrderIds((prev) => {
        const next = new Set(prev);
        visibleConfirmedOrders.forEach((o) => next.add(o.id));
        return next;
      });
    }
  };

  const handleToggleSelectOrder = (orderId: string) => {
    setSelectedOrderIds((prev) => {
      const next = new Set(prev);
      if (next.has(orderId)) {
        next.delete(orderId);
      } else {
        next.add(orderId);
      }
      return next;
    });
  };

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="w-3 h-3 text-gray-400 opacity-60 inline ml-1" />;
    }
    return sortOrder === 'asc' ? (
      <ArrowUp className="w-3 h-3 text-emerald-600 inline ml-1" />
    ) : (
      <ArrowDown className="w-3 h-3 text-emerald-600 inline ml-1" />
    );
  };

  const handleToggleModeration = async () => {
    const nextValue = !isModerated;
    setUpdatingModeration(true);
    try {
      await updateEvent(event.id, { manual_approval_required: nextValue });
      event.manual_approval_required = nextValue;
      setIsModerated(nextValue);
      setToastMessage(
        nextValue
          ? 'Modération manuelle activée : les futures réservations par carte feront l’objet d’une pré-autorisation.'
          : 'Modération manuelle désactivée : les futures réservations par carte seront immédiatement encaissées.'
      );
      setTimeout(() => setToastMessage(null), 6000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la mise à jour de la modération');
    } finally {
      setUpdatingModeration(false);
    }
  };

  const handleApprove = async () => {
    if (!approveModalOrder) return;
    const order = approveModalOrder;
    setActionLoadingId(order.id);
    setModalError(null);
    try {
      await approveOrder(event.id, order.id);
      setToastMessage(`Inscription n° ${order.order_number} validée avec succès ! Fonds capturés.`);
      setTimeout(() => setToastMessage(null), 6000);
      setApproveModalOrder(null);
      await loadData();
    } catch (err: unknown) {
      setModalError(err instanceof Error ? err.message : 'Erreur lors de la validation de la commande');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleReject = async () => {
    if (!rejectModalOrder) return;
    const order = rejectModalOrder;
    setActionLoadingId(order.id);
    setModalError(null);
    try {
      await rejectOrder(event.id, order.id, { reason: rejectReason.trim() || undefined });
      setToastMessage(`Inscription n° ${order.order_number} refusée. Pré-autorisation annulée et stands libérés.`);
      setTimeout(() => setToastMessage(null), 6000);
      setRejectModalOrder(null);
      setRejectReason('');
      await loadData();
    } catch (err: unknown) {
      setModalError(err instanceof Error ? err.message : 'Erreur lors du refus de la commande');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleRefund = async () => {
    if (!refundModalOrder) return;
    const order = refundModalOrder;
    setActionLoadingId(order.id);
    setModalError(null);
    try {
      await refundOrder(event.id, order.id, {
        reason: refundReason.trim() || undefined,
      });
      setToastMessage(
        order.payment_method === 'stripe'
          ? `Remboursement de ${order.total_price.toFixed(2)} € émis via Stripe pour la commande n° ${order.order_number}. Stand(s) libéré(s).`
          : `Commande hors-ligne n° ${order.order_number} marquée comme remboursée. Stand(s) libéré(s).`
      );
      setTimeout(() => setToastMessage(null), 6000);
      setRefundModalOrder(null);
      setRefundReason('');
      await loadData();
    } catch (err: unknown) {
      setModalError(err instanceof Error ? err.message : 'Erreur lors du remboursement de la commande');
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleRejectCancellation = async () => {
    if (!rejectCancellationModalOrder) return;
    const order = rejectCancellationModalOrder;
    if (!rejectCancellationReason.trim()) {
      setModalError("Le motif du refus de l'annulation est obligatoire.");
      return;
    }
    setActionLoadingId(order.id);
    setModalError(null);
    try {
      await rejectCancellationRequest(event.id, order.id, {
        reason: rejectCancellationReason.trim(),
      });
      setToastMessage(`Demande d'annulation pour la commande n° ${order.order_number} refusée. L'inscription reste confirmée.`);
      setTimeout(() => setToastMessage(null), 6000);
      setRejectCancellationModalOrder(null);
      setRejectCancellationReason('');
      await loadData();
    } catch (err: unknown) {
      setModalError(err instanceof Error ? err.message : "Erreur lors du refus de la demande d'annulation");
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleBulkCancel = async () => {
    const trimmedConfirm = bulkConfirmationText.trim();
    const isExactMatch =
      trimmedConfirm.toUpperCase() === 'CONFIRMER' ||
      trimmedConfirm.toUpperCase() === 'ANNULER' ||
      trimmedConfirm.toLowerCase() === event.title.trim().toLowerCase();

    if (!isExactMatch) {
      setModalError("Confirmation invalide. Veuillez saisir 'CONFIRMER' ou le titre exact de l'événement.");
      return;
    }

    setBulkCancelLoading(true);
    setModalError(null);
    try {
      const report = await cancelAndRefundAllEventOrders(event.id, {
        confirmation: trimmedConfirm,
        reason: bulkCancelReason.trim() || undefined,
      });
      setBulkCancelReport(report);
      setCurrentEventStatus(report.event_status || 'cancelled');
      setToastMessage(
        `Événement annulé : ${report.refunded_count} commande(s) remboursée(s), ${report.cancelled_count} annulée(s). Tous les stands sont libérés.`
      );
      setTimeout(() => setToastMessage(null), 8000);
      await loadData();
    } catch (err: unknown) {
      setModalError(err instanceof Error ? err.message : "Erreur lors de l'annulation générale");
    } finally {
      setBulkCancelLoading(false);
    }
  };

  // Payment badge renderer
  const renderPaymentBadge = (method: string, _isOffline: boolean, ref?: string | null) => {
    switch (method) {
      case 'check':
        return (
          <span
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-800 border border-slate-300"
            title={ref ? `Réf: ${ref}` : 'Paiement par chèque'}
          >
            <Receipt className="w-3.5 h-3.5 text-slate-600" />
            <span>Hors-ligne (Chèque)</span>
          </span>
        );
      case 'cash':
        return (
          <span
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-900 border border-amber-300"
            title={ref ? `Réf: ${ref}` : 'Paiement en espèces'}
          >
            <Banknote className="w-3.5 h-3.5 text-amber-600" />
            <span>Hors-ligne (Espèces)</span>
          </span>
        );
      case 'other':
        return (
          <span
            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-50 text-purple-900 border border-purple-300"
            title={ref ? `Réf: ${ref}` : 'Autre / Gratuité'}
          >
            <Gift className="w-3.5 h-3.5 text-purple-600" />
            <span>Hors-ligne (Autre)</span>
          </span>
        );
      case 'stripe':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-300">
            <CreditCard className="w-3.5 h-3.5 text-emerald-600" />
            <span>En ligne (Stripe)</span>
          </span>
        );
    }
  };

  const formatDate = (dateStr?: string | null) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  // Badges counters
  const pendingActionCount =
    (stats?.pending_approval_orders_count ?? 0) +
    (stats?.cancellation_requested_orders_count ?? 0);
  const offlineCount = stats?.offline_orders_count ?? 0;
  const totalCount = stats?.total_orders_count ?? orders.length;

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-xl transition"
            title="Retour à la liste des événements"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-2xl font-black text-gray-900 tracking-tight">
                Inscriptions &mdash; {event.title}
              </h2>
              <span className="text-xs px-2.5 py-0.5 rounded-full font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                Administration
              </span>
            </div>
            <p className="text-xs sm:text-sm text-gray-500 mt-0.5">
              Pilotage des réservations, saisie au guichet, arbitrage et communications.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          {onOpenEditor && (
            <button
              onClick={onOpenEditor}
              className="px-3.5 py-2 text-xs sm:text-sm font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-xl transition flex items-center gap-1.5 shadow-xs"
            >
              <Layers className="w-4 h-4 text-gray-500" />
              <span className="hidden sm:inline">Voir le plan</span>
            </button>
          )}

          {/* Check-in Export Dropdown */}
          <div className="relative" ref={exportMenuRef}>
            <button
              type="button"
              onClick={() => setIsExportMenuOpen((prev) => !prev)}
              className="px-3.5 py-2 text-xs sm:text-sm font-semibold text-gray-700 bg-white hover:bg-gray-50 border border-gray-300 rounded-xl transition flex items-center gap-1.5 shadow-xs"
              title="Télécharger la feuille d'émargement officielle pour le jour J"
              aria-expanded={isExportMenuOpen}
              aria-haspopup="true"
            >
              <Printer className="w-4 h-4 text-emerald-600" />
              <span>Émargement</span>
              <ChevronDown
                className={`w-3.5 h-3.5 text-gray-500 transition-transform ${
                  isExportMenuOpen ? 'rotate-180' : ''
                }`}
              />
            </button>

            {isExportMenuOpen && (
              <div className="absolute right-0 mt-2 w-72 bg-white rounded-2xl shadow-xl border border-gray-200 py-2 z-50">
                <div className="px-3.5 py-2 border-b border-gray-100">
                  <p className="text-xs font-bold text-gray-900">Feuille d'émargement officielle</p>
                  <p className="text-[11px] text-gray-500">Prête à imprimer ou ouvrir sur tableur</p>
                </div>

                <div className="p-1 space-y-0.5">
                  <a
                    href={getAdminCheckinPdfUrl(event.slug || event.id, 'spot')}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() => setIsExportMenuOpen(false)}
                    className="flex items-start gap-2.5 p-2 rounded-xl hover:bg-emerald-50 text-gray-800 transition group"
                  >
                    <div className="p-1.5 rounded-lg bg-emerald-100 text-emerald-700 group-hover:bg-emerald-200 mt-0.5">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-gray-900 group-hover:text-emerald-800">
                        PDF par emplacement (N° Stand)
                      </div>
                      <div className="text-[11px] text-gray-500">
                        Ordre naturel des allées (A-1, A-2, A-10)
                      </div>
                    </div>
                  </a>

                  <a
                    href={getAdminCheckinPdfUrl(event.slug || event.id, 'alpha')}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() => setIsExportMenuOpen(false)}
                    className="flex items-start gap-2.5 p-2 rounded-xl hover:bg-emerald-50 text-gray-800 transition group"
                  >
                    <div className="p-1.5 rounded-lg bg-blue-100 text-blue-700 group-hover:bg-blue-200 mt-0.5">
                      <FileText className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-gray-900 group-hover:text-emerald-800">
                        PDF alphabétique (Nom exposant)
                      </div>
                      <div className="text-[11px] text-gray-500">
                        Tri A → Z par nom et prénom d'exposant
                      </div>
                    </div>
                  </a>

                  <a
                    href={getAdminCheckinXlsxUrl(event.slug || event.id)}
                    download={`emargement_${event.slug || event.id}.xlsx`}
                    onClick={() => setIsExportMenuOpen(false)}
                    className="flex items-start gap-2.5 p-2 rounded-xl hover:bg-emerald-50 text-gray-800 transition group"
                  >
                    <div className="p-1.5 rounded-lg bg-green-100 text-green-700 group-hover:bg-green-200 mt-0.5">
                      <FileSpreadsheet className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-gray-900 group-hover:text-emerald-800">
                        Tableur Excel (.xlsx)
                      </div>
                      <div className="text-[11px] text-gray-500">
                        Classeur 2 onglets avec colonnes de pointage
                      </div>
                    </div>
                  </a>
                </div>
              </div>
            )}
          </div>

          <button
            onClick={() => handleTabChange('guichet')}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs sm:text-sm font-bold rounded-xl shadow-sm transition flex items-center gap-2"
            title="Ouvrir le formulaire de saisie rapide sur place"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Guichet</span>
          </button>
        </div>
      </div>

      {/* Toast notification */}
      {toastMessage && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl flex items-center justify-between shadow-sm animate-fade-in">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-5 h-5 text-emerald-600" />
            <span className="text-sm font-medium">{toastMessage}</span>
          </div>
          <button
            onClick={() => setToastMessage(null)}
            className="text-xs font-bold text-emerald-700 hover:underline"
          >
            Fermer
          </button>
        </div>
      )}

      {/* Error alert */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-xl flex items-center justify-between shadow-sm">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <span className="text-sm font-medium">{error}</span>
          </div>
          <button
            onClick={loadData}
            className="text-xs font-bold text-red-700 hover:underline"
          >
            Réessayer
          </button>
        </div>
      )}

      {/* Horizontal Tabs Navigation Bar */}
      <div className="border-b border-gray-200 bg-white px-4 rounded-2xl shadow-xs">
        <nav role="tablist" className="flex space-x-2 sm:space-x-4 overflow-x-auto" aria-label="Onglets de gestion des inscriptions">
          <button
            type="button"
            role="tab"
            id="tab-inscriptions"
            aria-selected={activeTab === 'inscriptions'}
            aria-controls="panel-inscriptions"
            onClick={() => handleTabChange('inscriptions')}
            className={`py-3.5 px-3 sm:px-4 border-b-2 font-bold text-xs sm:text-sm transition flex items-center gap-2 whitespace-nowrap ${
              activeTab === 'inscriptions'
                ? 'border-emerald-600 text-emerald-800'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <FileText className="w-4 h-4" />
            <span>1. Inscriptions</span>
            <span
              className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                activeTab === 'inscriptions'
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-gray-100 text-gray-600'
              }`}
            >
              {totalCount}
            </span>
          </button>

          <button
            type="button"
            role="tab"
            id="tab-guichet"
            aria-selected={activeTab === 'guichet'}
            aria-controls="panel-guichet"
            onClick={() => handleTabChange('guichet')}
            className={`py-3.5 px-3 sm:px-4 border-b-2 font-bold text-xs sm:text-sm transition flex items-center gap-2 whitespace-nowrap ${
              activeTab === 'guichet'
                ? 'border-emerald-600 text-emerald-800'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Banknote className="w-4 h-4" />
            <span>2. Guichet sur place</span>
            <span
              className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                activeTab === 'guichet'
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-gray-100 text-gray-600'
              }`}
            >
              {offlineCount}
            </span>
          </button>

          <button
            type="button"
            role="tab"
            id="tab-moderation"
            aria-selected={activeTab === 'moderation'}
            aria-controls="panel-moderation"
            onClick={() => handleTabChange('moderation')}
            className={`py-3.5 px-3 sm:px-4 border-b-2 font-bold text-xs sm:text-sm transition flex items-center gap-2 whitespace-nowrap ${
              activeTab === 'moderation'
                ? 'border-emerald-600 text-emerald-800'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>3. Modération & Litiges</span>
            {pendingActionCount > 0 ? (
              <span className="px-2 py-0.5 rounded-full text-xs font-black bg-amber-500 text-white animate-pulse">
                {pendingActionCount}
              </span>
            ) : (
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                  activeTab === 'moderation'
                    ? 'bg-emerald-100 text-emerald-800'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                0
              </span>
            )}
          </button>

          <button
            type="button"
            role="tab"
            id="tab-communications"
            aria-selected={activeTab === 'communications'}
            aria-controls="panel-communications"
            onClick={() => handleTabChange('communications')}
            className={`py-3.5 px-3 sm:px-4 border-b-2 font-bold text-xs sm:text-sm transition flex items-center gap-2 whitespace-nowrap ${
              activeTab === 'communications'
                ? 'border-emerald-600 text-emerald-800'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Mail className="w-4 h-4" />
            <span>4. Communications</span>
          </button>
        </nav>
      </div>

      {/* Tab 1: Inscriptions */}
      <div
        role="tabpanel"
        id="panel-inscriptions"
        aria-labelledby="tab-inscriptions"
        hidden={activeTab !== 'inscriptions'}
      >
        {activeTab === 'inscriptions' && (
          <RegistrationsTab
            event={event}
            orders={orders}
            sortedOrders={sortedOrders}
            stats={stats}
            loading={loading}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            statusFilter={statusFilter}
            setStatusFilter={setStatusFilter}
            onSort={handleSort}
            renderSortIcon={renderSortIcon}
            selectedOrderIds={selectedOrderIds}
            onToggleSelectAll={handleToggleSelectAll}
            onToggleSelectOrder={handleToggleSelectOrder}
            isAllConfirmedSelected={isAllConfirmedSelected}
            renderPaymentBadge={renderPaymentBadge}
            formatDate={formatDate}
            onOpenBroadcast={() => setIsBroadcastModalOpen(true)}
            onRefresh={loadData}
            onOpenRefundModal={(order) => {
              setRefundModalOrder(order);
              setRefundReason('');
              setModalError(null);
            }}
            onOpenApproveModal={(order) => {
              setApproveModalOrder(order);
              setModalError(null);
            }}
            onOpenRejectModal={(order) => {
              setRejectModalOrder(order);
              setRejectReason('');
              setModalError(null);
            }}
            onOpenRejectCancellationModal={(order) => {
              setRejectCancellationModalOrder(order);
              setRejectCancellationReason('');
              setModalError(null);
            }}
          />
        )}
      </div>

      {/* Tab 2: Guichet sur place */}
      <div
        role="tabpanel"
        id="panel-guichet"
        aria-labelledby="tab-guichet"
        hidden={activeTab !== 'guichet'}
      >
        {activeTab === 'guichet' && (
          <GuichetTab
            event={event}
            orders={allOrders}
            stats={stats}
            onBookingCreated={(orderNumber) => {
              setToastMessage(`Inscription guichet n° ${orderNumber} enregistrée avec succès !`);
              setTimeout(() => setToastMessage(null), 6000);
              loadData();
            }}
            renderPaymentBadge={renderPaymentBadge}
            formatDate={formatDate}
          />
        )}
      </div>

      {/* Tab 3: Modération & Litiges */}
      <div
        role="tabpanel"
        id="panel-moderation"
        aria-labelledby="tab-moderation"
        hidden={activeTab !== 'moderation'}
      >
        {activeTab === 'moderation' && (
          <ModerationTab
            event={event}
            orders={allOrders}
            isModerated={isModerated}
            updatingModeration={updatingModeration}
            onToggleModeration={handleToggleModeration}
            onOpenApproveModal={(order) => {
              setApproveModalOrder(order);
              setModalError(null);
            }}
            onOpenRejectModal={(order) => {
              setRejectModalOrder(order);
              setRejectReason('');
              setModalError(null);
            }}
            onOpenRefundModal={(order) => {
              setRefundModalOrder(order);
              setRefundReason('');
              setModalError(null);
            }}
            onOpenRejectCancellationModal={(order) => {
              setRejectCancellationModalOrder(order);
              setRejectCancellationReason('');
              setModalError(null);
            }}
            onOpenBulkCancelModal={() => {
              setIsBulkCancelModalOpen(true);
              setBulkConfirmationText('');
              setBulkCancelReason('');
              setModalError(null);
              setBulkCancelReport(null);
            }}
            currentEventStatus={currentEventStatus}
            formatDate={formatDate}
          />
        )}
      </div>

      {/* Tab 4: Communications */}
      <div
        role="tabpanel"
        id="panel-communications"
        aria-labelledby="tab-communications"
        hidden={activeTab !== 'communications'}
      >
        {activeTab === 'communications' && (
          <CommunicationsTab
            event={event}
            onOpenBroadcast={() => {
              setSelectedOrderIds(new Set());
              setIsBroadcastModalOpen(true);
            }}
            confirmedCount={stats?.confirmed_orders_count ?? 0}
          />
        )}
      </div>

      {/* --- Page-level Action Modals --- */}

      {/* Approve Modal */}
      {approveModalOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl shadow-xl border border-gray-100 max-w-md w-full p-6 space-y-4">
            <div className="flex items-center gap-3 text-emerald-600">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center">
                <Check className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900">Valider l'inscription</h3>
                <p className="text-xs text-gray-500">Commande {approveModalOrder.order_number}</p>
              </div>
            </div>

            <div className="bg-gray-50 p-3.5 rounded-xl text-xs space-y-1.5 border border-gray-100">
              <div className="flex justify-between">
                <span className="text-gray-500">Exposant :</span>
                <span className="font-bold text-gray-900">{approveModalOrder.full_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Stand(s) :</span>
                <span className="font-bold text-gray-900">
                  {(approveModalOrder.spot_labels || []).join(', ') || '—'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Montant à capturer :</span>
                <span className="font-black text-emerald-700">
                  {approveModalOrder.total_price.toFixed(2)} €
                </span>
              </div>
            </div>

            <p className="text-xs text-gray-600">
              En validant, l'autorisation bancaire Stripe sera <strong>capturée définitivement</strong>. L'exposant recevra son e-mail de confirmation avec l'attestation officielle et les stands lui seront définitivement attribués.
            </p>

            {modalError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-800 text-xs rounded-xl flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                <span>{modalError}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setApproveModalOrder(null);
                  setModalError(null);
                }}
                disabled={actionLoadingId === approveModalOrder.id}
                className="px-4 py-2 text-xs font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl transition disabled:opacity-50"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleApprove}
                disabled={actionLoadingId === approveModalOrder.id}
                className="px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl transition flex items-center gap-1.5 shadow-sm disabled:opacity-50"
              >
                {actionLoadingId === approveModalOrder.id && (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                )}
                <span>Confirmer et encaisser</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Modal */}
      {rejectModalOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl shadow-xl border border-gray-100 max-w-md w-full p-6 space-y-4">
            <div className="flex items-center gap-3 text-red-600">
              <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center">
                <X className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900">Refuser l'inscription</h3>
                <p className="text-xs text-gray-500">Commande {rejectModalOrder.order_number}</p>
              </div>
            </div>

            <div className="bg-gray-50 p-3.5 rounded-xl text-xs space-y-1.5 border border-gray-100">
              <div className="flex justify-between">
                <span className="text-gray-500">Exposant :</span>
                <span className="font-bold text-gray-900">{rejectModalOrder.full_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Stand(s) :</span>
                <span className="font-bold text-gray-900">
                  {(rejectModalOrder.spot_labels || []).join(', ') || '—'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Montant :</span>
                <span className="font-black text-gray-900">
                  {rejectModalOrder.total_price.toFixed(2)} €
                </span>
              </div>
            </div>

            <p className="text-xs text-gray-600">
              En refusant cette inscription, la pré-autorisation bancaire Stripe sera <strong>annulée sans aucun débit</strong> pour l'exposant. Les stands réservés redeviendront <strong>immédiatement disponibles</strong> pour d'autres participants.
            </p>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-gray-700">
                Motif du refus (optionnel, transmis à l'exposant)
              </label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Ex. Stand inadapté, justificatifs non conformes..."
                rows={2}
                className="w-full p-2.5 text-xs rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
              />
            </div>

            {modalError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-800 text-xs rounded-xl flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                <span>{modalError}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setRejectModalOrder(null);
                  setRejectReason('');
                  setModalError(null);
                }}
                disabled={actionLoadingId === rejectModalOrder.id}
                className="px-4 py-2 text-xs font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl transition disabled:opacity-50"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleReject}
                disabled={actionLoadingId === rejectModalOrder.id}
                className="px-4 py-2 text-xs font-bold text-white bg-red-600 hover:bg-red-700 rounded-xl transition flex items-center gap-1.5 shadow-sm disabled:opacity-50"
              >
                {actionLoadingId === rejectModalOrder.id && (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                )}
                <span>Confirmer le refus</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Refund Confirmation Modal */}
      {refundModalOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl shadow-xl border border-gray-100 max-w-md w-full p-6 space-y-4">
            <div className="flex items-center gap-3 text-emerald-600">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center">
                <RotateCcw className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900">
                  {refundModalOrder.status === 'cancellation_requested'
                    ? "Valider le remboursement"
                    : "Rembourser la commande"}
                </h3>
                <p className="text-xs text-gray-500">Commande {refundModalOrder.order_number}</p>
              </div>
            </div>

            <div className="bg-gray-50 p-3.5 rounded-xl text-xs space-y-1.5 border border-gray-100">
              <div className="flex justify-between">
                <span className="text-gray-500">Exposant :</span>
                <span className="font-bold text-gray-900">{refundModalOrder.full_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Stand(s) :</span>
                <span className="font-bold text-gray-900">
                  {(refundModalOrder.spot_labels || []).join(', ') || '—'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Mode de règlement :</span>
                <span className="font-bold text-gray-900">
                  {refundModalOrder.payment_method === 'stripe'
                    ? 'Carte bancaire (Stripe)'
                    : `Hors-ligne (${refundModalOrder.payment_method})`}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Montant à rembourser :</span>
                <span className="font-black text-gray-900">
                  {refundModalOrder.total_price.toFixed(2)} €
                </span>
              </div>
              {refundModalOrder.cancellation_reason && (
                <div className="pt-1.5 border-t border-gray-200 mt-1.5">
                  <span className="text-amber-800 font-semibold block">
                    Motif de l'exposant : {getCancellationReasonLabel(refundModalOrder.cancellation_reason)}
                  </span>
                  {refundModalOrder.cancellation_comment && (
                    <span className="text-gray-600 italic block mt-0.5">
                      « {refundModalOrder.cancellation_comment} »
                    </span>
                  )}
                </div>
              )}
            </div>

            <p className="text-xs text-gray-600">
              {refundModalOrder.payment_method === 'stripe' ? (
                <>
                  Le remboursement de <strong>{refundModalOrder.total_price.toFixed(2)} €</strong> sera émis via l'API Stripe sur la carte bancaire de l'exposant. Les stands réservés redeviendront <strong>immédiatement disponibles</strong> sur le plan public.
                </>
              ) : (
                <>
                  Règlement enregistré hors-ligne : la commande sera passée au statut <strong>Remboursée</strong> et les stands redeviendront <strong>immédiatement disponibles</strong>. Pensez à restituer le règlement (chèque ou espèces) manuellement à l'exposant.
                </>
              )}
            </p>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-gray-700">
                Note interne / Motif du remboursement (optionnel)
              </label>
              <textarea
                value={refundReason}
                onChange={(e) => setRefundReason(e.target.value)}
                placeholder="Ex. Remboursement validé suite à demande d'annulation..."
                rows={2}
                className="w-full p-2.5 text-xs rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
              />
            </div>

            {modalError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-800 text-xs rounded-xl flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                <span>{modalError}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setRefundModalOrder(null);
                  setRefundReason('');
                  setModalError(null);
                }}
                disabled={actionLoadingId === refundModalOrder.id}
                className="px-4 py-2 text-xs font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl transition disabled:opacity-50"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleRefund}
                disabled={actionLoadingId === refundModalOrder.id}
                className="px-4 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 rounded-xl transition flex items-center gap-1.5 shadow-sm disabled:opacity-50"
              >
                {actionLoadingId === refundModalOrder.id && (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                )}
                <span>Confirmer le remboursement</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Cancellation Modal */}
      {rejectCancellationModalOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl shadow-xl border border-gray-100 max-w-md w-full p-6 space-y-4">
            <div className="flex items-center gap-3 text-red-600">
              <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center">
                <XCircle className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900">Refuser la demande d'annulation</h3>
                <p className="text-xs text-gray-500">Commande {rejectCancellationModalOrder.order_number}</p>
              </div>
            </div>

            <div className="bg-gray-50 p-3.5 rounded-xl text-xs space-y-1.5 border border-gray-100">
              <div className="flex justify-between">
                <span className="text-gray-500">Exposant :</span>
                <span className="font-bold text-gray-900">{rejectCancellationModalOrder.full_name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Stand(s) :</span>
                <span className="font-bold text-gray-900">
                  {(rejectCancellationModalOrder.spot_labels || []).join(', ') || '—'}
                </span>
              </div>
              {rejectCancellationModalOrder.cancellation_reason && (
                <div className="pt-1.5 border-t border-gray-200 mt-1.5">
                  <span className="text-amber-800 font-semibold block">
                    Motif invoqué : {getCancellationReasonLabel(rejectCancellationModalOrder.cancellation_reason)}
                  </span>
                  {rejectCancellationModalOrder.cancellation_comment && (
                    <span className="text-gray-600 italic block mt-0.5">
                      « {rejectCancellationModalOrder.cancellation_comment} »
                    </span>
                  )}
                </div>
              )}
            </div>

            <p className="text-xs text-gray-600">
              En refusant, la commande repasse en statut <strong>Confirmée</strong>. Aucun remboursement ne sera effectué et les stands resteront <strong>réservés</strong> au nom de l'exposant.
            </p>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-gray-700">
                Motif du refus (obligatoire) <span className="text-red-500">*</span>
              </label>
              <textarea
                value={rejectCancellationReason}
                onChange={(e) => setRejectCancellationReason(e.target.value)}
                placeholder="Ex. Demande hors délai selon le règlement de l'événement..."
                rows={3}
                className="w-full p-2.5 text-xs rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
              />
            </div>

            {modalError && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-800 text-xs rounded-xl flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                <span>{modalError}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => {
                  setRejectCancellationModalOrder(null);
                  setRejectCancellationReason('');
                  setModalError(null);
                }}
                disabled={actionLoadingId === rejectCancellationModalOrder.id}
                className="px-4 py-2 text-xs font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl transition disabled:opacity-50"
              >
                Annuler
              </button>
              <button
                type="button"
                onClick={handleRejectCancellation}
                disabled={actionLoadingId === rejectCancellationModalOrder.id || !rejectCancellationReason.trim()}
                className="px-4 py-2 text-xs font-bold text-white bg-red-600 hover:bg-red-700 rounded-xl transition flex items-center gap-1.5 shadow-sm disabled:opacity-50"
              >
                {actionLoadingId === rejectCancellationModalOrder.id && (
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                )}
                <span>Confirmer le refus</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Emergency Bulk Cancellation Modal */}
      {isBulkCancelModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl shadow-2xl border border-red-200 max-w-lg w-full p-6 space-y-4">
            <div className="flex items-center gap-3 text-red-600">
              <div className="w-12 h-12 rounded-xl bg-red-100 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-6 h-6 text-red-600" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-gray-900">
                  Annulation d'urgence & Remboursement groupé
                </h3>
                <p className="text-xs text-red-600 font-medium">Action irréversible (Force majeure / Météo)</p>
              </div>
            </div>

            {bulkCancelReport ? (
              <div className="space-y-4">
                <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-xl text-xs space-y-2">
                  <div className="font-bold text-sm flex items-center gap-1.5 text-emerald-800">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Traitement groupé terminé</span>
                  </div>
                  <p>
                    L'événement est désormais <strong>annulé</strong> et tous les stands ont été libérés.
                  </p>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-center">
                    <div className="bg-white p-2 rounded-lg border border-emerald-100">
                      <div className="text-lg font-black text-gray-900">{bulkCancelReport.total_processed}</div>
                      <div className="text-[10px] text-gray-500 uppercase">Traitées</div>
                    </div>
                    <div className="bg-white p-2 rounded-lg border border-emerald-100">
                      <div className="text-lg font-black text-emerald-700">{bulkCancelReport.refunded_count}</div>
                      <div className="text-[10px] text-gray-500 uppercase">Remboursées</div>
                    </div>
                    <div className="bg-white p-2 rounded-lg border border-emerald-100">
                      <div className="text-lg font-black text-indigo-700">{bulkCancelReport.cancelled_count}</div>
                      <div className="text-[10px] text-gray-500 uppercase">Annulées</div>
                    </div>
                    <div className="bg-white p-2 rounded-lg border border-emerald-100">
                      <div className="text-lg font-black text-red-700">{bulkCancelReport.failed_count}</div>
                      <div className="text-[10px] text-gray-500 uppercase">Échecs</div>
                    </div>
                  </div>
                </div>

                {bulkCancelReport.errors && bulkCancelReport.errors.length > 0 && (
                  <div className="p-3 bg-red-50 border border-red-200 text-red-800 text-xs rounded-xl space-y-1">
                    <div className="font-bold">Avertissements / Erreurs ({bulkCancelReport.errors.length}) :</div>
                    <ul className="list-disc list-inside space-y-0.5 max-h-28 overflow-y-auto">
                      {bulkCancelReport.errors.map((err, i) => (
                        <li key={i}>{err}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="flex justify-end pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setIsBulkCancelModalOpen(false);
                      setBulkCancelReport(null);
                    }}
                    className="px-4 py-2 text-xs font-bold text-white bg-gray-800 hover:bg-gray-900 rounded-xl transition"
                  >
                    Fermer
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="p-3.5 bg-red-50/70 rounded-xl border border-red-100 text-xs text-red-950 space-y-2">
                  <div className="font-bold text-red-900">En confirmant cette action d'urgence :</div>
                  <ul className="list-disc list-inside space-y-1 text-red-800">
                    <li>Toutes les commandes par <strong>carte bancaire</strong> seront remboursées via Stripe.</li>
                    <li>Toutes les inscriptions <strong>hors-ligne</strong> seront marquées comme remboursées.</li>
                    <li>Toutes les pré-autorisations en cours seront <strong>annulées sans débit</strong>.</li>
                    <li>L'événement passera définitivement en statut <strong>Annulé</strong>.</li>
                    <li>L'intégralité des stands sera <strong>libérée</strong> sur le plan.</li>
                  </ul>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-xs font-semibold text-gray-700">
                    Motif de l'annulation générale (ex: vigilance météo, arrêté préfectoral)
                  </label>
                  <input
                    type="text"
                    value={bulkCancelReason}
                    onChange={(e) => setBulkCancelReason(e.target.value)}
                    placeholder="Ex. Vigilance météo rouge vent violent"
                    className="w-full p-2.5 text-xs rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
                  />
                </div>

                <div className="space-y-1.5 bg-amber-50 p-3 rounded-xl border border-amber-200">
                  <label className="block text-xs font-bold text-amber-900">
                    Double confirmation obligatoire :
                  </label>
                  <p className="text-[11px] text-amber-800">
                    Tapez <strong>CONFIRMER</strong> ou le titre exact de l'événement « <strong>{event.title}</strong> » pour déverrouiller l'action.
                  </p>
                  <input
                    type="text"
                    value={bulkConfirmationText}
                    onChange={(e) => setBulkConfirmationText(e.target.value)}
                    placeholder="Tapez CONFIRMER ou le titre..."
                    className="w-full p-2.5 text-xs font-mono bg-white rounded-lg border border-amber-300 focus:outline-none focus:ring-2 focus:ring-red-500/20 focus:border-red-500"
                  />
                </div>

                {modalError && (
                  <div className="p-3 bg-red-50 border border-red-200 text-red-800 text-xs rounded-xl flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                    <span>{modalError}</span>
                  </div>
                )}

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => {
                      setIsBulkCancelModalOpen(false);
                      setBulkConfirmationText('');
                      setBulkCancelReason('');
                      setModalError(null);
                    }}
                    disabled={bulkCancelLoading}
                    className="px-4 py-2 text-xs font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-xl transition disabled:opacity-50"
                  >
                    Abandonner
                  </button>
                  <button
                    type="button"
                    onClick={handleBulkCancel}
                    disabled={
                      bulkCancelLoading ||
                      !(
                        bulkConfirmationText.trim().toUpperCase() === 'CONFIRMER' ||
                        bulkConfirmationText.trim().toUpperCase() === 'ANNULER' ||
                        bulkConfirmationText.trim().toLowerCase() === event.title.trim().toLowerCase()
                      )
                    }
                    className="px-4 py-2 text-xs font-bold text-white bg-red-600 hover:bg-red-700 rounded-xl transition flex items-center gap-1.5 shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
                  >
                    {bulkCancelLoading && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                    <span>Annuler l'événement & Rembourser tous les inscrits</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Broadcast Modal */}
      <BroadcastModal
        isOpen={isBroadcastModalOpen}
        event={event}
        totalConfirmedCount={stats?.confirmed_orders_count ?? 0}
        selectedOrders={orders.filter((o) => selectedOrderIds.has(o.id))}
        onClose={() => setIsBroadcastModalOpen(false)}
        onSuccess={(report) => {
          setToastMessage(report.message || "Diffusion d'e-mails initiée avec succès !");
          setSelectedOrderIds(new Set());
        }}
      />
    </div>
  );
};
