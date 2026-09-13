import React, { useState, useEffect, useMemo } from 'react';
import {
  ArrowLeft,
  PlusCircle,
  Search,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Receipt,
  Banknote,
  Gift,
  CreditCard,
  Users,
  Layers,
  FileText,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Clock,
  Check,
  X,
  XCircle,
  ShieldCheck,
  RotateCcw,
  AlertTriangle,
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
} from '../lib/api';
import { ManualBookingModal } from '../components/ManualBookingModal';
import { RemindersCard } from '../components/RemindersCard';

interface RegistrationsPageProps {
  event: EventModel;
  onBack: () => void;
  onOpenEditor?: () => void;
}

type SortField = 'date' | 'name' | 'stand' | 'amount' | 'status';
type SortOrder = 'asc' | 'desc';

export const RegistrationsPage: React.FC<RegistrationsPageProps> = ({
  event,
  onBack,
  onOpenEditor,
}) => {
  const [orders, setOrders] = useState<AdminOrder[]>([]);
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

  // Actions & Modals
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
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
      const [orderRes, statsRes] = await Promise.all([
        fetchEventOrders(event.id, statusFilter, debouncedSearch),
        fetchEventDashboardStats(event.id),
      ]);
      setOrders(orderRes.items);
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

  const handleManualBookingSuccess = (orderNumber: string) => {
    setIsModalOpen(false);
    setToastMessage(`Réservation manuelle n° ${orderNumber} enregistrée avec succès !`);
    setTimeout(() => setToastMessage(null), 6000);
    loadData();
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

  // Occupancy bar calculation
  const totalSpots = stats?.total_spots || 0;
  const reservedSpots = stats?.reserved_spots || 0;
  const lockedSpots = stats?.locked_spots || 0;
  const reservedPct = totalSpots > 0 ? (reservedSpots / totalSpots) * 100 : 0;
  const lockedPct = totalSpots > 0 ? (lockedSpots / totalSpots) * 100 : 0;

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
              Suivi en temps réel du remplissage et enregistrement des règlements manuels au guichet.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          {/* Moderation switch toggle */}
          <div className="flex items-center gap-2.5 bg-gray-50 border border-gray-200 px-3 py-1.5 rounded-xl">
            <ShieldCheck className={`w-4 h-4 ${isModerated ? 'text-emerald-600' : 'text-gray-400'}`} />
            <div className="flex flex-col text-left">
              <span className="text-[11px] font-bold text-gray-800 leading-tight">Modération</span>
              <span className={`text-[10px] leading-tight font-medium ${isModerated ? 'text-emerald-600' : 'text-gray-400'}`}>
                {isModerated ? 'Active' : 'Désactivée'}
              </span>
            </div>
            <button
              type="button"
              onClick={handleToggleModeration}
              disabled={updatingModeration}
              className={`relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                isModerated ? 'bg-emerald-600' : 'bg-gray-300'
              } ${updatingModeration ? 'opacity-50 cursor-not-allowed' : ''}`}
              title={
                isModerated
                  ? 'Désactiver la modération (les paiements CB seront encaissés automatiquement)'
                  : 'Activer la modération (les paiements CB feront l’objet d’une pré-autorisation avant validation)'
              }
            >
              <span
                aria-hidden="true"
                className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                  isModerated ? 'translate-x-4' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {onOpenEditor && (
            <button
              onClick={onOpenEditor}
              className="px-3.5 py-2 text-xs sm:text-sm font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-xl transition flex items-center gap-1.5"
            >
              <Layers className="w-4 h-4 text-gray-500" />
              <span>Voir le plan</span>
            </button>
          )}

          {currentEventStatus !== 'cancelled' ? (
            <button
              onClick={() => {
                setIsBulkCancelModalOpen(true);
                setBulkConfirmationText('');
                setBulkCancelReason('');
                setModalError(null);
                setBulkCancelReport(null);
              }}
              className="px-3.5 py-2 text-xs sm:text-sm font-semibold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 rounded-xl transition flex items-center gap-1.5"
              title="Annuler l'événement d'urgence et rembourser tous les inscrits (force majeure / météo)"
            >
              <AlertTriangle className="w-4 h-4 text-red-600" />
              <span>Annuler l'événement</span>
            </button>
          ) : (
            <span className="px-3 py-1.5 text-xs font-bold text-red-800 bg-red-100 border border-red-300 rounded-xl flex items-center gap-1.5">
              <XCircle className="w-4 h-4 text-red-600" />
              <span>Événement Annulé</span>
            </span>
          )}

          <button
            onClick={() => setIsModalOpen(true)}
            disabled={currentEventStatus === 'cancelled'}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs sm:text-sm font-bold rounded-xl shadow-sm transition flex items-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
            title={currentEventStatus === 'cancelled' ? "Impossible d'ajouter des inscriptions sur un événement annulé" : undefined}
          >
            <PlusCircle className="w-4 h-4" />
            <span>Saisie Hors-Ligne</span>
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
          <button onClick={loadData} className="text-xs font-bold text-red-700 hover:underline">
            Réessayer
          </button>
        </div>
      )}

      {/* Reminders Status & Triggers */}
      <RemindersCard eventIdOrSlug={event.id} />

      {/* Jauge de remplissage épurée */}
      <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
              Jauge de remplissage
            </span>
            <div className="text-xl font-black text-gray-900 flex items-center gap-2 mt-0.5">
              <span>
                {reservedSpots} / {totalSpots} stands réservés
              </span>
              <span className="text-sm font-bold px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200">
                {stats?.occupancy_rate ?? 0}%
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs font-medium text-gray-500">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-xs bg-emerald-500" />
              <span>Réservés ({reservedSpots})</span>
            </div>
            {lockedSpots > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-xs bg-amber-400" />
                <span>En cours ({lockedSpots})</span>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-xs bg-gray-200" />
              <span>Disponibles ({stats?.available_spots ?? 0})</span>
            </div>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-4 bg-gray-100 rounded-full overflow-hidden flex shadow-inner">
          <div
            style={{ width: `${reservedPct}%` }}
            className="bg-emerald-500 transition-all duration-500"
            title={`Réservés : ${reservedSpots} stands (${reservedPct.toFixed(1)}%)`}
          />
          <div
            style={{ width: `${lockedPct}%` }}
            className="bg-amber-400 transition-all duration-500"
            title={`En cours de réservation : ${lockedSpots} stands (${lockedPct.toFixed(1)}%)`}
          />
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Revenue */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
              Chiffre d'affaires total
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
              €
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-black text-gray-900">
              {(stats?.total_revenue ?? 0).toFixed(2)} €
            </div>
            <div className="text-xs text-gray-500 mt-1">
              Cumul des ventes en ligne et hors-ligne
            </div>
          </div>
        </div>

        {/* Stripe Revenue */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-emerald-700">
              En ligne (Stripe)
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <CreditCard className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-black text-emerald-800">
              {(stats?.stripe_revenue ?? 0).toFixed(2)} €
            </div>
            <div className="text-xs text-emerald-600 mt-1">Paiements par carte bancaire</div>
          </div>
        </div>

        {/* Offline Revenue */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-700">
              Hors-ligne (Guichet)
            </span>
            <div className="w-8 h-8 rounded-lg bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Banknote className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-black text-indigo-900">
              {(stats?.offline_revenue ?? 0).toFixed(2)} €
            </div>
            <div className="text-xs text-gray-500 mt-1 flex items-center gap-2">
              <span>Chèques: {(stats?.offline_check_revenue ?? 0).toFixed(0)}€</span>
              <span>&bull;</span>
              <span>Espèces: {(stats?.offline_cash_revenue ?? 0).toFixed(0)}€</span>
            </div>
          </div>
        </div>

        {/* Total Registrations */}
        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">
              Exposants inscrits
            </span>
            <div className="w-8 h-8 rounded-lg bg-gray-50 text-gray-600 flex items-center justify-center">
              <Users className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-black text-gray-900">
              {stats?.confirmed_orders_count ?? 0}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              dont {stats?.offline_orders_count ?? 0} inscription(s) hors-ligne
            </div>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-2xl border border-gray-200 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Status Tabs */}
        <div className="flex items-center gap-1.5 p-1 bg-gray-100 rounded-xl w-full sm:w-auto overflow-x-auto">
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap ${
              statusFilter === 'all'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            Tous ({stats?.total_orders_count ?? 0})
          </button>
          <button
            onClick={() => setStatusFilter('pending_approval')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap flex items-center gap-1.5 ${
              statusFilter === 'pending_approval'
                ? 'bg-white text-amber-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <Clock className="w-3.5 h-3.5 text-amber-600" />
            <span>À valider</span>
            {(stats?.pending_approval_orders_count ?? 0) > 0 ? (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] font-black bg-amber-500 text-white animate-pulse">
                {stats?.pending_approval_orders_count}
              </span>
            ) : (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-gray-200 text-gray-700">
                0
              </span>
            )}
          </button>
          <button
            onClick={() => setStatusFilter('confirmed')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap ${
              statusFilter === 'confirmed'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            Confirmés ({stats?.confirmed_orders_count ?? 0})
          </button>
          <button
            onClick={() => setStatusFilter('cancellation_requested')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap flex items-center gap-1.5 ${
              statusFilter === 'cancellation_requested'
                ? 'bg-white text-amber-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <Clock className="w-3.5 h-3.5 text-amber-600" />
            <span>Annulations demandées</span>
            {(stats?.cancellation_requested_orders_count ?? 0) > 0 ? (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] font-black bg-amber-500 text-white animate-pulse">
                {stats?.cancellation_requested_orders_count}
              </span>
            ) : (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-gray-200 text-gray-700">
                0
              </span>
            )}
          </button>
          <button
            onClick={() => setStatusFilter('refunded')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap flex items-center gap-1.5 ${
              statusFilter === 'refunded'
                ? 'bg-white text-purple-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <RotateCcw className="w-3.5 h-3.5 text-purple-600" />
            <span>Remboursés</span>
            {(stats?.refunded_orders_count ?? 0) > 0 && (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-purple-100 text-purple-800">
                {stats?.refunded_orders_count}
              </span>
            )}
          </button>
          <button
            onClick={() => setStatusFilter('cancelled')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap flex items-center gap-1.5 ${
              statusFilter === 'cancelled'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <XCircle className="w-3.5 h-3.5 text-gray-500" />
            <span>Annulés</span>
            {(stats?.cancelled_orders_count ?? 0) > 0 && (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-gray-100 text-gray-700">
                {stats?.cancelled_orders_count}
              </span>
            )}
          </button>
          <button
            onClick={() => setStatusFilter('offline')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap flex items-center gap-1 ${
              statusFilter === 'offline'
                ? 'bg-white text-indigo-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <span>Hors-ligne</span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-indigo-100 text-indigo-800">
              {stats?.offline_orders_count ?? 0}
            </span>
          </button>
          <button
            onClick={() => setStatusFilter('pending')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap flex items-center gap-1.5 ${
              statusFilter === 'pending'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <span>Transactions non abouties</span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-amber-100 text-amber-800">
              {stats?.pending_orders_count ?? 0}
            </span>
          </button>
          <button
            onClick={() => setStatusFilter('rejected')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap flex items-center gap-1.5 ${
              statusFilter === 'rejected'
                ? 'bg-white text-red-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <XCircle className="w-3.5 h-3.5 text-red-500" />
            <span>Refusés</span>
          </button>
        </div>

        {/* Search Input */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Rechercher nom, stand, email..."
            className="w-full pl-9 pr-8 py-2 text-xs rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-xs font-bold"
            >
              &times;
            </button>
          )}
        </div>
      </div>

      {/* Orders Table */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        {loading && orders.length === 0 ? (
          <div className="py-20 text-center text-gray-500">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-emerald-600" />
            <p className="text-sm">Chargement des inscriptions...</p>
          </div>
        ) : orders.length === 0 ? (
          <div className="py-16 text-center text-gray-500 space-y-3">
            <FileText className="w-10 h-10 text-gray-300 mx-auto" />
            <div className="text-base font-bold text-gray-700">Aucune inscription trouvée</div>
            <p className="text-xs text-gray-400 max-w-sm mx-auto">
              {searchQuery
                ? `Aucun résultat ne correspond à la recherche « ${searchQuery} ».`
                : 'Aucune commande enregistrée pour le moment dans cet événement.'}
            </p>
            <button
              onClick={() => setIsModalOpen(true)}
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-bold rounded-lg transition mt-2"
            >
              <PlusCircle className="w-4 h-4" />
              <span>Ajouter une réservation manuelle</span>
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-gray-50/80 border-b border-gray-200 text-gray-500 font-bold uppercase tracking-wider text-[11px]">
                  <th
                    onClick={() => handleSort('date')}
                    className="py-3.5 px-4 cursor-pointer select-none hover:text-gray-900 transition"
                  >
                    <div className="inline-flex items-center gap-1">
                      <span>Commande / Date</span>
                      {renderSortIcon('date')}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('name')}
                    className="py-3.5 px-4 cursor-pointer select-none hover:text-gray-900 transition"
                  >
                    <div className="inline-flex items-center gap-1">
                      <span>Exposant</span>
                      {renderSortIcon('name')}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('stand')}
                    className="py-3.5 px-4 cursor-pointer select-none hover:text-gray-900 transition"
                  >
                    <div className="inline-flex items-center gap-1">
                      <span>Stands</span>
                      {renderSortIcon('stand')}
                    </div>
                  </th>
                  <th className="py-3.5 px-4">Règlement</th>
                  <th
                    onClick={() => handleSort('amount')}
                    className="py-3.5 px-4 cursor-pointer select-none hover:text-gray-900 transition"
                  >
                    <div className="inline-flex items-center gap-1">
                      <span>Montant</span>
                      {renderSortIcon('amount')}
                    </div>
                  </th>
                  <th
                    onClick={() => handleSort('status')}
                    className="py-3.5 px-4 cursor-pointer select-none hover:text-gray-900 transition"
                  >
                    <div className="inline-flex items-center gap-1">
                      <span>Statut</span>
                      {renderSortIcon('status')}
                    </div>
                  </th>
                  <th className="py-3.5 px-4">Notes / Réf</th>
                  <th className="py-3.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-gray-700">
                {sortedOrders.map((ord) => (
                  <tr key={ord.id} className="hover:bg-gray-50/60 transition">
                    {/* Order & Date */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <div className="font-bold text-gray-900">{ord.order_number}</div>
                      <div className="text-[11px] text-gray-400 mt-0.5">
                        {formatDate(ord.created_at)}
                      </div>
                    </td>

                    {/* Exhibitor */}
                    <td className="py-3.5 px-4">
                      <div className="font-bold text-gray-900">{ord.full_name}</div>
                      <div className="text-[11px] text-gray-500">{ord.phone}</div>
                      {ord.email && (
                        <div className="text-[11px] text-gray-400 truncate max-w-[160px]">
                          {ord.email}
                        </div>
                      )}
                    </td>

                    {/* Spots */}
                    <td className="py-3.5 px-4">
                      <div className="flex flex-wrap gap-1">
                        {ord.spot_labels && ord.spot_labels.length > 0 ? (
                          ord.spot_labels.map((lbl) => (
                            <span
                              key={lbl}
                              className="px-2 py-0.5 rounded-md font-bold text-[11px] bg-gray-100 text-gray-800 border border-gray-200"
                            >
                              {lbl}
                            </span>
                          ))
                        ) : (
                          <span className="text-gray-400 italic text-[11px]">Non spécifié</span>
                        )}
                      </div>
                    </td>

                    {/* Payment Badge */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {renderPaymentBadge(ord.payment_method, ord.is_offline, ord.offline_payment_reference)}
                    </td>

                    {/* Amount */}
                    <td className="py-3.5 px-4 whitespace-nowrap font-black text-gray-900">
                      {ord.total_price.toFixed(2)} €
                    </td>

                    {/* Status */}
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {ord.status === 'confirmed' ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Confirmé</span>
                        </span>
                      ) : ord.status === 'cancellation_requested' ? (
                        <span
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-900 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-300"
                          title={`Annulation demandée par l'exposant${ord.cancellation_reason ? ` (Motif: ${ord.cancellation_reason})` : ''}`}
                        >
                          <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                          <span>Annulation demandée</span>
                        </span>
                      ) : ord.status === 'pending_approval' ? (
                        <span
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-300"
                          title="En attente de validation par l'organisateur (pré-autorisation enregistrée)"
                        >
                          <Clock className="w-3.5 h-3.5 text-amber-600" />
                          <span>À valider</span>
                        </span>
                      ) : ord.status === 'rejected' ? (
                        <span
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded-full border border-red-200"
                          title="Réservation refusée et pré-autorisation annulée"
                        >
                          <XCircle className="w-3.5 h-3.5 text-red-500" />
                          <span>Refusé</span>
                        </span>
                      ) : ord.status === 'refunded' ? (
                        <span
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-purple-700 bg-purple-50 px-2 py-0.5 rounded-full border border-purple-200"
                          title="Commande entièrement remboursée, stand(s) libéré(s)"
                        >
                          <RotateCcw className="w-3.5 h-3.5 text-purple-600" />
                          <span>Remboursé</span>
                        </span>
                      ) : ord.status === 'cancelled' ? (
                        <span
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-gray-500 bg-gray-100 px-2 py-0.5 rounded-full border border-gray-200 line-through"
                          title="Commande annulée sans débit ou lors d'une annulation d'événement"
                        >
                          <XCircle className="w-3.5 h-3.5 text-gray-400" />
                          <span>Annulé</span>
                        </span>
                      ) : ord.status === 'pending' ? (
                        <span
                          className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-800 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200"
                          title={ord.is_offline ? "Règlement en attente d'encaissement" : "L'exposant n'a pas finalisé son paiement en ligne"}
                        >
                          <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                          <span>{ord.is_offline ? "Règlement en attente" : "Transaction non aboutie"}</span>
                        </span>
                      ) : (
                        <span className="text-[11px] font-bold text-gray-500 capitalize">
                          {ord.status}
                        </span>
                      )}
                    </td>

                    {/* Notes & Ref */}
                    <td className="py-3.5 px-4 text-[11px] text-gray-500 max-w-[200px]">
                      {ord.cancellation_reason && (
                        <div
                          className="font-semibold text-amber-800 truncate"
                          title={`Motif: ${ord.cancellation_reason}${ord.cancellation_comment ? ` — « ${ord.cancellation_comment} »` : ''}`}
                        >
                          Annulation : {getCancellationReasonLabel(ord.cancellation_reason)}
                          {ord.cancellation_comment && ` (${ord.cancellation_comment})`}
                        </div>
                      )}
                      {ord.offline_payment_reference && (
                        <div className="font-semibold text-gray-800">
                          Réf: {ord.offline_payment_reference}
                        </div>
                      )}
                      {ord.admin_notes && (
                        <div className="italic text-gray-600 truncate" title={ord.admin_notes}>
                          « {ord.admin_notes} »
                        </div>
                      )}
                      {!ord.cancellation_reason && !ord.offline_payment_reference && !ord.admin_notes && (
                        <span className="text-gray-300">&mdash;</span>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="py-3.5 px-4 whitespace-nowrap text-right">
                      {ord.status === 'pending_approval' ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => {
                              setApproveModalOrder(ord);
                              setModalError(null);
                            }}
                            disabled={actionLoadingId === ord.id}
                            className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold flex items-center gap-1 shadow-sm transition disabled:opacity-50"
                            title="Valider l'inscription et capturer la pré-autorisation CB"
                          >
                            {actionLoadingId === ord.id ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Check className="w-3.5 h-3.5" />
                            )}
                            <span>Accepter</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setRejectModalOrder(ord);
                              setRejectReason('');
                              setModalError(null);
                            }}
                            disabled={actionLoadingId === ord.id}
                            className="px-2.5 py-1 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 rounded-lg text-xs font-bold flex items-center gap-1 transition disabled:opacity-50"
                            title="Refuser l'inscription, annuler l'autorisation et libérer les stands"
                          >
                            <X className="w-3.5 h-3.5" />
                            <span>Refuser</span>
                          </button>
                        </div>
                      ) : ord.status === 'cancellation_requested' ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            type="button"
                            onClick={() => {
                              setRefundModalOrder(ord);
                              setRefundReason('');
                              setModalError(null);
                            }}
                            disabled={actionLoadingId === ord.id}
                            className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold flex items-center gap-1 shadow-sm transition disabled:opacity-50"
                            title="Valider le remboursement et libérer les stands"
                          >
                            {actionLoadingId === ord.id ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Check className="w-3.5 h-3.5" />
                            )}
                            <span>Valider remboursement</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setRejectCancellationModalOrder(ord);
                              setRejectCancellationReason('');
                              setModalError(null);
                            }}
                            disabled={actionLoadingId === ord.id}
                            className="px-2.5 py-1 bg-red-50 hover:bg-red-100 text-red-700 border border-red-200 rounded-lg text-xs font-bold flex items-center gap-1 transition disabled:opacity-50"
                            title="Refuser la demande d'annulation et maintenir la réservation"
                          >
                            <X className="w-3.5 h-3.5" />
                            <span>Refuser</span>
                          </button>
                        </div>
                      ) : ord.status === 'confirmed' ? (
                        <div className="flex items-center justify-end">
                          <button
                            type="button"
                            onClick={() => {
                              setRefundModalOrder(ord);
                              setRefundReason('');
                              setModalError(null);
                            }}
                            disabled={actionLoadingId === ord.id}
                            className="px-2 py-1 text-gray-600 hover:text-red-700 hover:bg-red-50 border border-transparent hover:border-red-200 rounded-lg text-xs font-semibold flex items-center gap-1 transition disabled:opacity-50"
                            title="Rembourser cette réservation et libérer les stands"
                          >
                            <RotateCcw className="w-3.5 h-3.5 text-gray-400" />
                            <span>Rembourser</span>
                          </button>
                        </div>
                      ) : (
                        <span className="text-gray-300">&mdash;</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Approve Confirmation Modal */}
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
                <span className="text-gray-500">Montant :</span>
                <span className="font-black text-gray-900">
                  {approveModalOrder.total_price.toFixed(2)} €
                </span>
              </div>
            </div>

            <p className="text-xs text-gray-600">
              En confirmant, vous déclenchez la <strong>capture immédiate</strong> de la pré-autorisation bancaire Stripe. L'inscription sera définitivement confirmée et les fonds transférés.
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
                <span>Confirmer et capturer</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reject Confirmation Modal */}
      {rejectModalOrder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-2xl shadow-xl border border-gray-100 max-w-md w-full p-6 space-y-4">
            <div className="flex items-center gap-3 text-red-600">
              <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center">
                <XCircle className="w-5 h-5" />
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
                <span className="text-gray-500">Montant à annuler :</span>
                <span className="font-black text-gray-900">
                  {rejectModalOrder.total_price.toFixed(2)} €
                </span>
              </div>
            </div>

            <p className="text-xs text-gray-600">
              L'autorisation bancaire sera <strong>annulée sans aucun débit</strong> sur le compte de l'exposant. Les stands réservés redeviendront <strong>immédiatement disponibles</strong> sur le plan.
            </p>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-gray-700">
                Motif du refus (optionnel, consigné en note interne)
              </label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Ex. Dossier non conforme, pièce justificative manquante..."
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

      {/* Manual Booking Modal */}
      <ManualBookingModal
        isOpen={isModalOpen}
        event={event}
        onClose={() => setIsModalOpen(false)}
        onSuccess={handleManualBookingSuccess}
      />
    </div>
  );
};
