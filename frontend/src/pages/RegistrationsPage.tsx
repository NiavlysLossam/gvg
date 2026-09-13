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
  Clock,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';
import { EventModel } from '../types/event';
import { AdminOrder, DashboardStats } from '../types/order';
import { fetchEventOrders, fetchEventDashboardStats } from '../lib/api';
import { ManualBookingModal } from '../components/ManualBookingModal';

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

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [debouncedSearch, setDebouncedSearch] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'confirmed' | 'offline' | 'pending'>('all');

  // Sorting
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  // Manual booking modal
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

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
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-gray-200 shadow-xs">
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
          {onOpenEditor && (
            <button
              onClick={onOpenEditor}
              className="px-3.5 py-2 text-xs sm:text-sm font-semibold text-gray-700 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-xl transition flex items-center gap-1.5"
            >
              <Layers className="w-4 h-4 text-gray-500" />
              <span>Voir le plan</span>
            </button>
          )}

          <button
            onClick={() => setIsModalOpen(true)}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-xs sm:text-sm font-bold rounded-xl shadow-xs transition flex items-center gap-2"
          >
            <PlusCircle className="w-4 h-4" />
            <span>Saisie Hors-Ligne</span>
          </button>
        </div>
      </div>

      {/* Toast notification */}
      {toastMessage && (
        <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 p-4 rounded-xl flex items-center justify-between shadow-xs animate-fade-in">
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
        <div className="bg-red-50 border border-red-200 text-red-800 p-4 rounded-xl flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            <span className="text-sm font-medium">{error}</span>
          </div>
          <button onClick={loadData} className="text-xs font-bold text-red-700 hover:underline">
            Réessayer
          </button>
        </div>
      )}

      {/* Jauge de remplissage épurée */}
      <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-xs space-y-3">
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
        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs flex flex-col justify-between">
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
        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs flex flex-col justify-between">
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
        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs flex flex-col justify-between">
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
        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs flex flex-col justify-between">
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
      <div className="bg-white p-4 rounded-2xl border border-gray-200 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Status Tabs */}
        <div className="flex items-center gap-1.5 p-1 bg-gray-100 rounded-xl w-full sm:w-auto overflow-x-auto">
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap ${
              statusFilter === 'all'
                ? 'bg-white text-gray-900 shadow-xs'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            Tous ({stats?.total_orders_count ?? 0})
          </button>
          <button
            onClick={() => setStatusFilter('confirmed')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap ${
              statusFilter === 'confirmed'
                ? 'bg-white text-gray-900 shadow-xs'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            Confirmés ({stats?.confirmed_orders_count ?? 0})
          </button>
          <button
            onClick={() => setStatusFilter('offline')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap flex items-center gap-1 ${
              statusFilter === 'offline'
                ? 'bg-white text-indigo-900 shadow-xs'
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
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap ${
              statusFilter === 'pending'
                ? 'bg-white text-gray-900 shadow-xs'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            En attente ({stats?.pending_orders_count ?? 0})
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
            className="w-full pl-9 pr-8 py-2 text-xs rounded-xl border border-gray-200 focus:outline-hidden focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500"
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
      <div className="bg-white rounded-2xl border border-gray-200 shadow-xs overflow-hidden">
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
                      ) : ord.status === 'pending' ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold text-amber-700">
                          <Clock className="w-3.5 h-3.5" />
                          <span>En attente</span>
                        </span>
                      ) : (
                        <span className="text-[11px] font-bold text-gray-500 capitalize">
                          {ord.status}
                        </span>
                      )}
                    </td>

                    {/* Notes & Ref */}
                    <td className="py-3.5 px-4 text-[11px] text-gray-500 max-w-[200px]">
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
                      {!ord.offline_payment_reference && !ord.admin_notes && (
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
