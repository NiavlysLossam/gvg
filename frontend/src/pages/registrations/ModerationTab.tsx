import React from 'react';
import {
  ShieldCheck,
  Clock,
  Check,
  RotateCcw,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Phone,
  Mail,
} from 'lucide-react';
import { EventModel } from '../../types/event';
import { AdminOrder, getCancellationReasonLabel } from '../../types/order';

interface ModerationTabProps {
  event: EventModel;
  orders: AdminOrder[];
  isModerated: boolean;
  updatingModeration: boolean;
  onToggleModeration: () => void;
  onOpenApproveModal: (order: AdminOrder) => void;
  onOpenRejectModal: (order: AdminOrder) => void;
  onOpenRefundModal: (order: AdminOrder) => void;
  onOpenRejectCancellationModal: (order: AdminOrder) => void;
  onOpenBulkCancelModal: () => void;
  currentEventStatus: string;
  formatDate: (dateStr?: string | null) => string;
}

export const ModerationTab: React.FC<ModerationTabProps> = ({
  event,
  orders,
  isModerated,
  updatingModeration,
  onToggleModeration,
  onOpenApproveModal,
  onOpenRejectModal,
  onOpenRefundModal,
  onOpenRejectCancellationModal,
  onOpenBulkCancelModal,
  currentEventStatus,
  formatDate,
}) => {
  const pendingApprovals = orders.filter((o) => o.status === 'pending_approval');
  const pendingCancellations = orders.filter((o) => o.status === 'cancellation_requested');

  return (
    <div className="space-y-6">
      {/* Moderation Mode Setting Card */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div
              className={`p-3 rounded-xl shrink-0 ${
                isModerated
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-gray-100 text-gray-500'
              }`}
            >
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-gray-900">
                  Modération Manuelle des Inscriptions
                </h3>
                <span
                  className={`text-xs px-2.5 py-0.5 rounded-full font-bold ${
                    isModerated
                      ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                      : 'bg-gray-100 text-gray-600 border border-gray-200'
                  }`}
                >
                  {isModerated ? 'Active' : 'Désactivée'}
                </span>
              </div>
              <p className="text-xs sm:text-sm text-gray-500 mt-1 max-w-2xl">
                {isModerated
                  ? 'Les paiements par carte font l’objet d’une pré-autorisation bancaire de 7 jours. Vous validez manuellement chaque inscription avant l’encaissement définitif des fonds.'
                  : 'Les paiements par carte bancaire sont encaissés immédiatement et les inscriptions sont confirmées de manière autonome dès le règlement.'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3 self-end sm:self-center">
            <button
              type="button"
              onClick={onToggleModeration}
              disabled={updatingModeration}
              className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                isModerated ? 'bg-emerald-600' : 'bg-gray-300'
              } ${updatingModeration ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <span
                aria-hidden="true"
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
                  isModerated ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>
        </div>
      </div>

      {/* Pending Approvals Queue */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-gray-100 pb-3">
          <div className="flex items-center gap-2">
            <Clock className="w-5 h-5 text-amber-600" />
            <h3 className="font-bold text-gray-900 text-base">
              File d'Attente de Validation ({pendingApprovals.length})
            </h3>
          </div>
          {pendingApprovals.length > 0 && (
            <span className="text-xs px-2.5 py-1 rounded-full font-black bg-amber-100 text-amber-900 border border-amber-300 animate-pulse">
              Action requise
            </span>
          )}
        </div>

        {pendingApprovals.length === 0 ? (
          <div className="py-8 text-center text-gray-400 text-xs">
            <ShieldCheck className="w-8 h-8 mx-auto mb-2 text-emerald-500 opacity-60" />
            <p className="font-semibold text-gray-700">Aucune inscription en attente de modération</p>
            <p className="text-gray-400 mt-0.5">Toutes les réservations sont à jour.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {pendingApprovals.map((order) => (
              <div
                key={order.id}
                className="py-4 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-gray-900 text-sm">{order.full_name}</span>
                    <span className="font-mono text-xs px-2 py-0.5 bg-gray-100 rounded-md text-gray-700">
                      {order.order_number}
                    </span>
                    <span className="text-xs text-gray-400">
                      Demande du {formatDate(order.created_at)}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
                    {order.phone && (
                      <span className="flex items-center gap-1">
                        <Phone className="w-3.5 h-3.5 text-gray-400" />
                        <span>{order.phone}</span>
                      </span>
                    )}
                    {order.email && (
                      <span className="flex items-center gap-1">
                        <Mail className="w-3.5 h-3.5 text-gray-400" />
                        <span>{order.email}</span>
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 text-xs text-emerald-800">
                    <span className="font-semibold">Stands demandés :</span>
                    {(order.spot_labels || []).map((lbl) => (
                      <span
                        key={lbl}
                        className="px-2 py-0.5 bg-emerald-50 border border-emerald-200 font-extrabold rounded-md"
                      >
                        {lbl}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end md:self-center">
                  <div className="text-right mr-2">
                    <div className="text-base font-black text-gray-900">
                      {order.total_price.toFixed(2)} €
                    </div>
                    <div className="text-[11px] text-gray-400">Pré-autorisation Stripe</div>
                  </div>

                  <button
                    type="button"
                    onClick={() => onOpenRejectModal(order)}
                    className="px-3.5 py-1.5 bg-white hover:bg-red-50 text-red-600 border border-red-200 rounded-xl text-xs font-bold transition"
                  >
                    Refuser
                  </button>
                  <button
                    type="button"
                    onClick={() => onOpenApproveModal(order)}
                    className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold shadow-sm transition flex items-center gap-1"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>Valider (Encaisser)</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pending Cancellations & Disputes Queue */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-gray-100 pb-3">
          <div className="flex items-center gap-2">
            <RotateCcw className="w-5 h-5 text-purple-600" />
            <h3 className="font-bold text-gray-900 text-base">
              Demandes d'Annulation & Arbitrage de Remboursements ({pendingCancellations.length})
            </h3>
          </div>
          {pendingCancellations.length > 0 && (
            <span className="text-xs px-2.5 py-1 rounded-full font-black bg-purple-100 text-purple-900 border border-purple-300 animate-pulse">
              Arbitrage requis
            </span>
          )}
        </div>

        {pendingCancellations.length === 0 ? (
          <div className="py-8 text-center text-gray-400 text-xs">
            <Check className="w-8 h-8 mx-auto mb-2 text-purple-500 opacity-60" />
            <p className="font-semibold text-gray-700">Aucune demande d'annulation en cours</p>
            <p className="text-gray-400 mt-0.5">Aucun litige ou demande de remboursement à traiter.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {pendingCancellations.map((order) => (
              <div
                key={order.id}
                className="py-4 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-gray-900 text-sm">{order.full_name}</span>
                    <span className="font-mono text-xs px-2 py-0.5 bg-gray-100 rounded-md text-gray-700">
                      {order.order_number}
                    </span>
                    <span className="text-xs text-gray-400">
                      Inscrit le {formatDate(order.created_at)}
                    </span>
                  </div>

                  <div className="p-3 bg-purple-50/60 border border-purple-100 rounded-xl text-xs text-purple-900 space-y-1">
                    <div className="font-semibold text-purple-950 flex items-center gap-1.5">
                      <HelpCircle className="w-3.5 h-3.5 text-purple-600" />
                      <span>
                        Motif : {getCancellationReasonLabel(order.cancellation_reason)}
                      </span>
                    </div>
                    {order.cancellation_comment && (
                      <p className="italic pl-5 text-purple-800">
                        « {order.cancellation_comment} »
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 text-xs text-gray-600">
                    <span>Stands réservés :</span>
                    {(order.spot_labels || []).map((lbl) => (
                      <span
                        key={lbl}
                        className="px-2 py-0.5 bg-gray-100 font-extrabold rounded-md text-gray-800"
                      >
                        {lbl}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0 self-end md:self-center">
                  <div className="text-right mr-2">
                    <div className="text-base font-black text-gray-900">
                      {order.total_price.toFixed(2)} €
                    </div>
                    <div className="text-[11px] text-gray-400">
                      {order.payment_method === 'stripe' ? 'Via Stripe' : 'Règlement guichet'}
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => onOpenRejectCancellationModal(order)}
                    className="px-3.5 py-1.5 bg-white hover:bg-gray-100 text-gray-700 border border-gray-300 rounded-xl text-xs font-bold transition"
                  >
                    Refuser l'annulation
                  </button>
                  <button
                    type="button"
                    onClick={() => onOpenRefundModal(order)}
                    className="px-4 py-1.5 bg-purple-600 hover:bg-purple-700 text-white rounded-xl text-xs font-bold shadow-sm transition flex items-center gap-1"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                    <span>Valider le Remboursement</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Emergency Event Cancellation & Bulk Refund Zone */}
      <div className="bg-red-50 border border-red-200 rounded-2xl p-6 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="p-2.5 rounded-xl bg-red-100 text-red-600 shrink-0">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <h4 className="font-bold text-red-900 text-base">
                Annulation Générale de l'Événement (Force Majeure / Météo)
              </h4>
              <p className="text-xs text-red-700 mt-1 max-w-2xl">
                En cas d'intempéries majeures ou d'arrêté préfectoral, cette action annule
                définitivement l'événement « <strong>{event.title}</strong> », rembourse intégralement tous les exposants confirmés via
                Stripe, libère tous les stands et expédie une notification e-mail d'annulation
                générale.
              </p>
            </div>
          </div>

          {currentEventStatus !== 'cancelled' ? (
            <button
              type="button"
              onClick={onOpenBulkCancelModal}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-bold text-xs sm:text-sm rounded-xl shadow-sm transition shrink-0"
            >
              Annuler et Rembourser Tout
            </button>
          ) : (
            <span className="px-3 py-1.5 text-xs font-bold text-red-800 bg-red-200 border border-red-300 rounded-xl flex items-center gap-1.5 shrink-0">
              <XCircle className="w-4 h-4 text-red-600" />
              <span>Événement Déjà Annulé</span>
            </span>
          )}
        </div>
      </div>
    </div>
  );
};
