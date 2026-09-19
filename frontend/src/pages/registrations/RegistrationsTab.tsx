import React, { useState, useMemo } from 'react';
import {
  Search,
  RefreshCw,
  Users,
  CreditCard,
  Banknote,
  Clock,
  RotateCcw,
  XCircle,
  FileText,
  Mail,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react';
import { EventModel } from '../../types/event';
import { AdminOrder, DashboardStats, getCancellationReasonLabel } from '../../types/order';
import { getAdminAttestationPdfUrl } from '../../lib/api';

export type SortField = 'date' | 'name' | 'stand' | 'amount' | 'status';
export type SortOrder = 'asc' | 'desc';

interface RegistrationsTabProps {
  event: EventModel;
  orders: AdminOrder[];
  sortedOrders: AdminOrder[];
  stats: DashboardStats | null;
  loading: boolean;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  statusFilter: 'all' | 'pending_approval' | 'confirmed' | 'offline' | 'cancellation_requested' | 'refunded' | 'cancelled' | 'pending' | 'rejected';
  setStatusFilter: (filter: 'all' | 'pending_approval' | 'confirmed' | 'offline' | 'cancellation_requested' | 'refunded' | 'cancelled' | 'pending' | 'rejected') => void;
  onSort: (field: SortField) => void;
  renderSortIcon: (field: SortField) => React.ReactNode;
  selectedOrderIds: Set<string>;
  onToggleSelectAll: () => void;
  onToggleSelectOrder: (orderId: string) => void;
  isAllConfirmedSelected: boolean;
  renderPaymentBadge: (method: string, isOffline: boolean, ref?: string | null) => React.ReactNode;
  formatDate: (dateStr?: string | null) => string;
  onOpenBroadcast: () => void;
  onRefresh: () => void;
  onOpenRefundModal: (order: AdminOrder) => void;
  onOpenApproveModal: (order: AdminOrder) => void;
  onOpenRejectModal: (order: AdminOrder) => void;
  onOpenRejectCancellationModal: (order: AdminOrder) => void;
}

const ITEMS_PER_PAGE = 25;

export const RegistrationsTab: React.FC<RegistrationsTabProps> = ({
  event,
  orders,
  sortedOrders,
  stats,
  loading,
  searchQuery,
  setSearchQuery,
  statusFilter,
  setStatusFilter,
  onSort,
  renderSortIcon,
  selectedOrderIds,
  onToggleSelectAll,
  onToggleSelectOrder,
  isAllConfirmedSelected,
  renderPaymentBadge,
  formatDate,
  onOpenBroadcast,
  onRefresh,
  onOpenRefundModal,
  onOpenApproveModal,
  onOpenRejectModal,
  onOpenRejectCancellationModal,
}) => {
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Reset page on search or filter change
  React.useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, statusFilter]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(sortedOrders.length / ITEMS_PER_PAGE));

  // Safeguard pagination bounds if orders are removed / refunded
  React.useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(1);
    }
  }, [currentPage, totalPages]);

  const paginatedOrders = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    return sortedOrders.slice(start, start + ITEMS_PER_PAGE);
  }, [sortedOrders, currentPage]);

  // Occupancy calculations
  const totalSpots = stats?.total_spots || 0;
  const reservedSpots = stats?.reserved_spots || 0;
  const lockedSpots = stats?.locked_spots || 0;
  const reservedPct = totalSpots > 0 ? (reservedSpots / totalSpots) * 100 : 0;
  const lockedPct = totalSpots > 0 ? (lockedSpots / totalSpots) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Occupancy Progress Bar */}
      <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-sm">
          <div className="flex items-center gap-2">
            <span className="font-bold text-gray-900">Remplissage du plan :</span>
            <span className="text-emerald-700 font-extrabold text-base">
              {reservedSpots} / {totalSpots} stands réservés
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full font-bold bg-emerald-100 text-emerald-800">
              {reservedPct.toFixed(1)}%
            </span>
          </div>
          <div className="text-xs text-gray-500 flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-emerald-500 inline-block" />
              <span>Confirmés ({reservedSpots})</span>
            </div>
            {lockedSpots > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-amber-400 inline-block" />
                <span>Paniers en cours ({lockedSpots})</span>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-gray-200 inline-block" />
              <span>Libres ({stats?.available_spots || 0})</span>
            </div>
          </div>
        </div>

        <div className="w-full bg-gray-100 h-3 rounded-full overflow-hidden flex shadow-inner">
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
            onClick={() => setStatusFilter('pending')}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap flex items-center gap-1.5 ${
              statusFilter === 'pending'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <Clock className="w-3.5 h-3.5 text-gray-400" />
            <span>Paniers en cours</span>
            {(stats?.pending_orders_count ?? 0) > 0 && (
              <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-gray-100 text-gray-700">
                {stats?.pending_orders_count}
              </span>
            )}
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

        {/* Search and refresh */}
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-64">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Rechercher nom, stand, n°..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-8 py-2 bg-gray-50 border border-gray-200 rounded-xl text-xs sm:text-sm focus:bg-white focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-0.5 rounded-full"
                title="Effacer la recherche"
              >
                <XCircle className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
          <button
            onClick={onRefresh}
            className="p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-xl transition border border-gray-200 shadow-sm"
            title="Rafraîchir les données"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-emerald-600' : ''}`} />
          </button>
        </div>
      </div>

      {/* Bulk Selection Bar */}
      {selectedOrderIds.size > 0 && (
        <div className="bg-emerald-50 border border-emerald-200 p-3 rounded-xl flex items-center justify-between shadow-xs animate-fade-in">
          <div className="flex items-center gap-2 text-emerald-900 text-xs sm:text-sm font-semibold">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <span>
              {selectedOrderIds.size} exposant(s) sélectionné(s) sur ce tableau
            </span>
            <button
              type="button"
              onClick={onToggleSelectAll}
              className="ml-2 text-xs text-emerald-700 underline font-normal hover:text-emerald-900"
            >
              Désélectionner tout
            </button>
          </div>
          <button
            type="button"
            onClick={onOpenBroadcast}
            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold transition flex items-center gap-1.5 shadow-sm"
          >
            <Mail className="w-3.5 h-3.5" />
            <span>Envoyer un e-mail au groupe ({selectedOrderIds.size})</span>
          </button>
        </div>
      )}

      {/* Orders Table */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-left text-xs sm:text-sm">
            <thead className="bg-gray-50/75 text-gray-500 font-semibold uppercase tracking-wider text-[11px]">
              <tr>
                <th scope="col" className="px-4 py-3 w-10">
                  <input
                    type="checkbox"
                    checked={isAllConfirmedSelected}
                    onChange={onToggleSelectAll}
                    aria-label="Sélectionner tous les exposants confirmés"
                    className="w-4 h-4 rounded-sm border-gray-300 text-emerald-600 focus:ring-emerald-500"
                  />
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 cursor-pointer hover:bg-gray-100 transition"
                  onClick={() => onSort('date')}
                >
                  <span>Date</span>
                  {renderSortIcon('date')}
                </th>
                <th scope="col" className="px-4 py-3">
                  <span>N° Commande</span>
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 cursor-pointer hover:bg-gray-100 transition"
                  onClick={() => onSort('name')}
                >
                  <span>Exposant</span>
                  {renderSortIcon('name')}
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 cursor-pointer hover:bg-gray-100 transition"
                  onClick={() => onSort('stand')}
                >
                  <span>Stand(s)</span>
                  {renderSortIcon('stand')}
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 cursor-pointer hover:bg-gray-100 transition"
                  onClick={() => onSort('amount')}
                >
                  <span>Montant</span>
                  {renderSortIcon('amount')}
                </th>
                <th scope="col" className="px-4 py-3">
                  <span>Paiement</span>
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 cursor-pointer hover:bg-gray-100 transition"
                  onClick={() => onSort('status')}
                >
                  <span>Statut</span>
                  {renderSortIcon('status')}
                </th>
                <th scope="col" className="px-4 py-3">
                  <span>Notes / Réf</span>
                </th>
                <th scope="col" className="px-4 py-3 text-right">
                  <span>Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {loading && orders.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-gray-500">
                    <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-emerald-600" />
                    <span>Chargement des réservations...</span>
                  </td>
                </tr>
              ) : paginatedOrders.length === 0 ? (
                <tr>
                  <td colSpan={10} className="py-12 text-center text-gray-400">
                    <Users className="w-8 h-8 mx-auto mb-2 opacity-40" />
                    <p className="font-semibold text-gray-600">Aucune inscription trouvée</p>
                    <p className="text-xs text-gray-400 mt-1">
                      {searchQuery
                        ? 'Modifiez votre recherche ou effacez les filtres.'
                        : 'Les réservations apparaîtront ici dès leur enregistrement.'}
                    </p>
                  </td>
                </tr>
              ) : (
                paginatedOrders.map((order) => {
                  const isConfirmed = order.status === 'confirmed';
                  const isSelected = selectedOrderIds.has(order.id);

                  return (
                    <tr
                      key={order.id}
                      className={`hover:bg-gray-50/80 transition ${
                        isSelected ? 'bg-emerald-50/40' : ''
                      }`}
                    >
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          disabled={!isConfirmed}
                          onChange={() => onToggleSelectOrder(order.id)}
                          aria-label={`Sélectionner l'exposant ${order.full_name}`}
                          className="w-4 h-4 rounded-sm border-gray-300 text-emerald-600 focus:ring-emerald-500 disabled:opacity-30"
                        />
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-xs text-gray-500 font-mono">
                        {formatDate(order.created_at)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap font-mono text-xs font-bold text-gray-800">
                        {order.order_number}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-bold text-gray-900 leading-tight">
                          {order.full_name}
                        </div>
                        <div className="text-xs text-gray-500 flex flex-col gap-0.5 mt-0.5">
                          {order.phone && <span>{order.phone}</span>}
                          {order.email && <span className="inline-block truncate max-w-[180px]">{order.email}</span>}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-1">
                          {order.spot_labels && order.spot_labels.length > 0 ? (
                            order.spot_labels.map((lbl) => (
                              <span
                                key={lbl}
                                className="px-2 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-800 font-extrabold text-xs rounded-md shadow-sm"
                              >
                                {lbl}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-gray-400 italic">Aucun</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap font-extrabold text-gray-900">
                        {order.total_price.toFixed(2)} €
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {renderPaymentBadge(order.payment_method, order.is_offline, order.offline_payment_reference)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {order.status === 'confirmed' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                            <span>Confirmé</span>
                          </span>
                        ) : order.status === 'pending_approval' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200 animate-pulse">
                            <Clock className="w-3.5 h-3.5 text-amber-600" />
                            <span>À valider</span>
                          </span>
                        ) : order.status === 'cancellation_requested' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300">
                            <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                            <span>Annulation demandée</span>
                          </span>
                        ) : order.status === 'refunded' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-100 text-purple-800 border border-purple-200">
                            <RotateCcw className="w-3.5 h-3.5 text-purple-600" />
                            <span>Remboursé</span>
                          </span>
                        ) : order.status === 'cancelled' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-800 border border-red-200">
                            <XCircle className="w-3.5 h-3.5 text-red-600" />
                            <span>Annulé</span>
                          </span>
                        ) : order.status === 'pending' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-gray-100 text-gray-700 border border-gray-200">
                            <Clock className="w-3.5 h-3.5 text-gray-500" />
                            <span>Panier en cours</span>
                          </span>
                        ) : order.status === 'rejected' ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-red-100 text-red-800 border border-red-200">
                            <XCircle className="w-3.5 h-3.5 text-red-600" />
                            <span>Refusé</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold bg-gray-100 text-gray-800">
                            {order.status}
                          </span>
                        )}
                      </td>
                      {/* Notes & Ref */}
                      <td className="px-4 py-3 text-[11px] text-gray-500 max-w-[200px]">
                        {order.cancellation_reason && (
                          <div
                            className="font-semibold text-amber-800 truncate"
                            title={`Motif: ${order.cancellation_reason}${order.cancellation_comment ? ` — « ${order.cancellation_comment} »` : ''}`}
                          >
                            Annulation : {getCancellationReasonLabel(order.cancellation_reason)}
                            {order.cancellation_comment && ` (${order.cancellation_comment})`}
                          </div>
                        )}
                        {order.offline_payment_reference && (
                          <div className="font-semibold text-gray-800 truncate" title={order.offline_payment_reference}>
                            Réf: {order.offline_payment_reference}
                          </div>
                        )}
                        {order.admin_notes && (
                          <div className="italic text-gray-600 truncate" title={order.admin_notes}>
                            « {order.admin_notes} »
                          </div>
                        )}
                        {!order.cancellation_reason && !order.offline_payment_reference && !order.admin_notes && (
                          <span className="text-gray-300">&mdash;</span>
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-right text-xs">
                        <div className="flex items-center justify-end gap-1.5">
                          {isConfirmed && (
                            <a
                              href={getAdminAttestationPdfUrl(event.slug || event.id, order.id)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="p-1.5 text-emerald-700 hover:bg-emerald-50 rounded-lg border border-emerald-200 transition"
                              title="Télécharger l'attestation PDF réglementaire de l'exposant"
                            >
                              <FileText className="w-4 h-4" />
                            </a>
                          )}
                          {order.status === 'pending_approval' && (
                            <>
                              <button
                                type="button"
                                onClick={() => onOpenApproveModal(order)}
                                className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold text-xs shadow-sm transition"
                              >
                                Valider
                              </button>
                              <button
                                type="button"
                                onClick={() => onOpenRejectModal(order)}
                                className="px-2.5 py-1 bg-red-600 hover:bg-red-700 text-white rounded-lg font-bold text-xs shadow-sm transition"
                              >
                                Refuser
                              </button>
                            </>
                          )}
                          {order.status === 'cancellation_requested' && (
                            <>
                              <button
                                type="button"
                                onClick={() => onOpenRefundModal(order)}
                                className="px-2.5 py-1 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-bold text-xs shadow-sm transition"
                                title="Valider le remboursement et libérer les stands"
                              >
                                Rembourser
                              </button>
                              <button
                                type="button"
                                onClick={() => onOpenRejectCancellationModal(order)}
                                className="px-2.5 py-1 bg-white hover:bg-gray-100 text-gray-700 rounded-lg border border-gray-300 font-bold text-xs transition"
                                title="Refuser la demande d'annulation"
                              >
                                Refuser
                              </button>
                            </>
                          )}
                          {isConfirmed && (
                            <button
                              type="button"
                              onClick={() => onOpenRefundModal(order)}
                              className="px-2 py-1 text-red-600 hover:bg-red-50 rounded-lg border border-red-200 font-semibold text-xs transition"
                              title="Rembourser et annuler cette commande"
                            >
                              Rembourser
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="p-4 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
            <div>
              Affichage de {Math.min(sortedOrders.length, (currentPage - 1) * ITEMS_PER_PAGE + 1)} à{' '}
              {Math.min(sortedOrders.length, currentPage * ITEMS_PER_PAGE)} sur {sortedOrders.length} inscriptions
            </div>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed font-semibold"
              >
                Précédent
              </button>
              <span className="px-2 font-bold text-gray-700">
                {currentPage} / {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed font-semibold"
              >
                Suivant
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
