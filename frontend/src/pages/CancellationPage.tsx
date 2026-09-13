import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ArrowLeft,
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  ShieldAlert,
  ShoppingBag,
  HelpCircle,
  AlertTriangle,
  Info,
  Share2,
} from 'lucide-react';
import {
  OrderOut,
  CANCELLATION_REASON_OPTIONS,
  getCancellationReasonLabel,
} from '../types/order';
import { PublicEventResponse } from '../types/public';
import { fetchPublicOrder, fetchPublicEvent, submitCancellationRequest } from '../lib/api';

interface CancellationPageProps {
  slug: string;
  orderId: string;
  onNavigateToMap: () => void;
  onNavigateToConfirmation?: (accessToken: string) => void;
  onNavigateHome?: () => void;
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
  }).format(price);
}

function formatMeters(meters: number): string {
  return new Intl.NumberFormat('fr-FR', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 2,
  }).format(meters);
}

function formatDate(isoDate?: string | null): string {
  if (!isoDate) return '—';
  try {
    const d = new Date(isoDate);
    return new Intl.DateTimeFormat('fr-FR', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(d);
  } catch {
    return isoDate;
  }
}

export const CancellationPage: React.FC<CancellationPageProps> = ({
  slug,
  orderId,
  onNavigateToMap,
  onNavigateToConfirmation,
  onNavigateHome,
}) => {
  const [event, setEvent] = useState<PublicEventResponse | null>(null);
  const [order, setOrder] = useState<OrderOut | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form State
  const [selectedReason, setSelectedReason] = useState<string>('medical');
  const [comment, setComment] = useState<string>('');
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [justSubmitted, setJustSubmitted] = useState<boolean>(false);
  const [copiedLink, setCopiedLink] = useState<boolean>(false);

  // Retrieve token from URL query params (search or hash) or sessionStorage
  const accessToken = useMemo(() => {
    if (typeof window === 'undefined') return '';
    const params = new URLSearchParams(window.location.search);
    let queryToken = params.get('token') || params.get('access_token');
    if (!queryToken && window.location.hash.includes('?')) {
      const hashQuery = window.location.hash.substring(window.location.hash.indexOf('?'));
      const hashParams = new URLSearchParams(hashQuery);
      queryToken = hashParams.get('token') || hashParams.get('access_token');
    }
    if (queryToken) return queryToken;

    try {
      const stored = window.sessionStorage.getItem(`gvg_order_token_${orderId}`);
      if (stored) return stored;
    } catch {
      // ignore
    }
    return '';
  }, [orderId]);

  const handleCopyLink = async () => {
    if (typeof window !== 'undefined' && navigator.clipboard) {
      try {
        await navigator.clipboard.writeText(window.location.href);
        setCopiedLink(true);
        setTimeout(() => setCopiedLink(false), 3000);
      } catch {
        // Clipboard write failed
      }
    }
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);

    if (!accessToken) {
      setErrorMessage(
        'Jeton d’accès manquant. Veuillez utiliser le lien sécurisé présent dans votre email ou page de confirmation.'
      );
      setLoading(false);
      return;
    }

    try {
      const [eventData, orderData] = await Promise.all([
        fetchPublicEvent(slug),
        fetchPublicOrder(slug, orderId, accessToken),
      ]);
      setEvent(eventData);
      setOrder(orderData);
    } catch (err: any) {
      let msg = 'Impossible de charger les informations de la commande.';
      if (err?.detail) {
        if (typeof err.detail === 'string') {
          msg = err.detail;
        } else if (Array.isArray(err.detail)) {
          msg = err.detail.map((d: any) => (typeof d === 'string' ? d : d.msg || JSON.stringify(d))).join(', ');
        } else if (typeof err.detail === 'object') {
          msg = JSON.stringify(err.detail);
        }
      } else if (err?.message) {
        msg = typeof err.message === 'string' ? err.message : JSON.stringify(err.message);
      }
      setErrorMessage(msg);
    } finally {
      setLoading(false);
    }
  }, [slug, orderId, accessToken]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!selectedReason) {
      setFormError('Veuillez sélectionner un motif d’annulation.');
      return;
    }

    if (selectedReason === 'other' && (!comment || !comment.trim())) {
      setFormError('Une précision dans le commentaire est obligatoire pour le motif « Autre ».');
      return;
    }

    setSubmitting(true);
    try {
      const updatedOrder = await submitCancellationRequest(slug, orderId, accessToken, {
        cancellation_reason: selectedReason,
        cancellation_comment: comment.trim() || undefined,
      });
      setOrder(updatedOrder);
      setJustSubmitted(true);
    } catch (err: any) {
      let msg = 'Une erreur est survenue lors de l’envoi de votre demande d’annulation.';
      if (err?.detail) {
        if (typeof err.detail === 'string') {
          msg = err.detail;
        } else if (Array.isArray(err.detail)) {
          msg = err.detail.map((d: any) => (typeof d === 'string' ? d : d.msg || JSON.stringify(d))).join(', ');
        } else if (typeof err.detail === 'object') {
          msg = JSON.stringify(err.detail);
        }
      } else if (err?.message) {
        msg = typeof err.message === 'string' ? err.message : JSON.stringify(err.message);
      }
      setFormError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // 1. Loading State
  if (loading) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full space-y-4 animate-pulse text-center">
          <div className="w-16 h-16 bg-amber-100 text-amber-700 rounded-2xl flex items-center justify-center mx-auto">
            <Loader2 className="w-8 h-8 animate-spin" />
          </div>
          <div className="h-6 bg-gray-200 rounded-lg w-3/4 mx-auto" />
          <div className="h-4 bg-gray-200 rounded-lg w-1/2 mx-auto" />
          <p className="text-sm font-medium text-gray-500 pt-2">
            Chargement du portail d’annulation...
          </p>
        </div>
      </div>
    );
  }

  // 2. Error / Missing Token State
  if (errorMessage || !order) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-3xl shadow-sm border border-gray-200 p-8 text-center space-y-4">
          <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto">
            <ShieldAlert className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-extrabold text-gray-900">Accès non autorisé ou lien invalide</h2>
          <p className="text-sm text-gray-600 leading-relaxed">{errorMessage}</p>
          <div className="pt-4 flex justify-center gap-3">
            <button
              onClick={onNavigateToMap}
              className="px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-bold shadow-sm transition"
            >
              Retourner au plan
            </button>
          </div>
        </div>
      </div>
    );
  }

  const isAlreadyRequested = order.status === 'cancellation_requested';
  const isTerminalIneligible = ['cancelled', 'rejected', 'refunded'].includes(order.status);
  const isPendingUnpaid = order.status === 'pending';

  return (
    <div className="min-h-screen bg-[#FBFBFA] flex flex-col">
      {/* Top Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            {onNavigateHome && (
              <button
                onClick={onNavigateHome}
                className="text-sm font-semibold text-gray-500 hover:text-gray-900 transition"
              >
                Accueil
              </button>
            )}
            {onNavigateToConfirmation ? (
              <button
                onClick={() => onNavigateToConfirmation(accessToken)}
                className="inline-flex items-center gap-2 text-sm font-semibold text-gray-600 hover:text-gray-900 transition active:scale-95"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Retour à la confirmation</span>
              </button>
            ) : (
              <button
                onClick={onNavigateToMap}
                className="inline-flex items-center gap-2 text-sm font-semibold text-gray-600 hover:text-gray-900 transition active:scale-95"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Retour au plan</span>
              </button>
            )}
          </div>
          <div className="text-right">
            <span className="font-mono text-xs font-bold px-3 py-1 rounded-full border text-gray-800 bg-gray-50 border-gray-200">
              {order.order_number}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-2xl w-full mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Order Summary Card */}
        <div className="bg-white rounded-2xl p-5 border border-gray-200 shadow-sm space-y-3">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <ShoppingBag className="w-4 h-4 text-emerald-700" />
              <span className="text-xs font-bold uppercase tracking-wider text-gray-700">
                {event?.title ? `Réservation — ${event.title}` : 'Récapitulatif de votre réservation'}
              </span>
            </div>
            <span className="text-xs font-bold text-gray-500">
              {order.first_name} {order.last_name}
            </span>
          </div>

          <div className="divide-y divide-gray-100">
            {order.items.map((it) => (
              <div key={it.id} className="py-2 flex items-center justify-between text-xs sm:text-sm">
                <span className="font-bold text-gray-900">
                  Stand {it.spot_label || 'Emplacement'}
                  {it.spot_linear_meters && (
                    <span className="text-gray-500 text-xs ml-1 font-normal">
                      ({formatMeters(it.spot_linear_meters)} m)
                    </span>
                  )}
                </span>
                <span className="font-mono font-semibold text-gray-800">
                  {formatPrice(it.price)}
                </span>
              </div>
            ))}
          </div>

          <div className="pt-2 border-t border-gray-100 flex items-center justify-between">
            <span className="text-xs font-semibold text-gray-600">Montant total</span>
            <span className="text-base font-extrabold font-mono text-gray-900">
              {formatPrice(order.total_price)}
            </span>
          </div>
        </div>

        {/* Case 1: Already Requested State */}
        {isAlreadyRequested ? (
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-amber-200 shadow-sm space-y-5 animate-fade-in">
            <div className="w-16 h-16 bg-amber-100 text-amber-800 rounded-full flex items-center justify-center mx-auto shadow-sm">
              <Clock className="w-8 h-8 text-amber-700" />
            </div>

            {justSubmitted && (
              <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-2xl text-emerald-800 text-xs sm:text-sm flex items-center gap-2.5 font-medium">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <span>Votre demande d’annulation a été soumise avec succès et est en attente d’arbitrage.</span>
              </div>
            )}

            <div className="text-center space-y-2">
              <h1 className="text-xl sm:text-2xl font-extrabold text-gray-900 leading-tight">
                {justSubmitted ? 'Demande d’annulation enregistrée' : 'Demande d’annulation en cours d’examen'}
              </h1>
              <p className="text-sm text-gray-600 max-w-lg mx-auto leading-relaxed">
                Votre demande d’annulation pour la commande{' '}
                <strong className="font-mono text-gray-900">{order.order_number}</strong> a bien
                été enregistrée et transmise à l’organisateur.
              </p>
            </div>

            {/* Status Information Box */}
            <div className="p-4 bg-amber-50/80 border border-amber-200 rounded-2xl text-amber-950 text-xs sm:text-sm space-y-3">
              <div className="flex items-center gap-2 font-bold text-amber-900">
                <Info className="w-4 h-4 text-amber-700 flex-shrink-0" />
                <span>Statut du dossier : Attente d’arbitrage par l’organisateur</span>
              </div>

              <div className="space-y-1.5 text-xs text-amber-800 border-t border-amber-200/60 pt-2">
                <p>
                  <strong>Motif renseigné :</strong> {getCancellationReasonLabel(order.cancellation_reason)}
                </p>
                {order.cancellation_comment && (
                  <p>
                    <strong>Commentaire :</strong> « {order.cancellation_comment} »
                  </p>
                )}
                {order.cancellation_requested_at && (
                  <p>
                    <strong>Date de soumission :</strong>{' '}
                    {formatDate(order.cancellation_requested_at)}
                  </p>
                )}
              </div>

              <p className="text-xs text-amber-900/90 leading-relaxed">
                Vos stands restent attribués jusqu’à la décision formelle de l’organisateur. Vous
                recevrez une notification dès que le dossier aura été traité.
              </p>
            </div>

            <div className="pt-3 flex flex-wrap justify-center gap-3">
              <button
                onClick={handleCopyLink}
                className="px-5 py-2.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-xs font-semibold shadow-sm transition inline-flex items-center gap-1.5"
              >
                <Share2 className="w-3.5 h-3.5 text-gray-500" />
                <span>{copiedLink ? 'Lien copié !' : 'Partager ou copier mon lien'}</span>
              </button>
              {onNavigateToConfirmation && (
                <button
                  onClick={() => onNavigateToConfirmation(accessToken)}
                  className="px-5 py-2.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-xs font-semibold shadow-sm transition"
                >
                  Voir ma confirmation de commande
                </button>
              )}
              <button
                onClick={onNavigateToMap}
                className="px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold shadow-sm transition"
              >
                Retourner au plan
              </button>
            </div>
          </div>
        ) : isTerminalIneligible ? (
          /* Case 2: Terminal Ineligible State (cancelled, rejected, refunded) */
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-gray-200 shadow-sm text-center space-y-4 animate-fade-in">
            <div className="w-16 h-16 bg-gray-100 text-gray-600 rounded-full flex items-center justify-center mx-auto">
              <AlertCircle className="w-8 h-8 text-gray-600" />
            </div>

            <h1 className="text-xl sm:text-2xl font-extrabold text-gray-900">
              Cette commande n’est plus modifiable
            </h1>

            <p className="text-sm text-gray-600 max-w-md mx-auto leading-relaxed">
              La commande <strong className="font-mono">{order.order_number}</strong> est
              actuellement au statut <strong>« {order.status} »</strong>. Il n’est plus possible de
              soumettre de demande d’annulation sur ce dossier.
            </p>

            <div className="pt-2 flex justify-center">
              <button
                onClick={onNavigateToMap}
                className="px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-bold shadow-sm transition"
              >
                Retourner au plan
              </button>
            </div>
          </div>
        ) : isPendingUnpaid ? (
          /* Case 3: Incomplete / Unpaid Order */
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-amber-200 shadow-sm text-center space-y-4 animate-fade-in">
            <div className="w-16 h-16 bg-amber-100 text-amber-700 rounded-full flex items-center justify-center mx-auto">
              <AlertTriangle className="w-8 h-8 text-amber-700" />
            </div>

            <h1 className="text-xl sm:text-2xl font-extrabold text-gray-900">
              Commande non finalisée
            </h1>

            <p className="text-sm text-gray-600 max-w-md mx-auto leading-relaxed">
              Cette commande n’est pas encore confirmée. Seules les réservations confirmées ou en
              cours de modération peuvent faire l’objet d’une demande d’annulation.
            </p>

            <div className="pt-2 flex justify-center">
              <button
                onClick={onNavigateToMap}
                className="px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-bold shadow-sm transition"
              >
                Retourner au plan
              </button>
            </div>
          </div>
        ) : (
          /* Case 4: Cancellation Form for Confirmed / Pending Approval Orders */
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-gray-200 shadow-sm space-y-6 animate-fade-in">
            <div className="space-y-2">
              <h1 className="text-xl sm:text-2xl font-extrabold text-gray-900 leading-tight">
                Demande d’annulation de votre réservation
              </h1>
              <p className="text-xs sm:text-sm text-gray-600 leading-relaxed">
                Un imprévu vous empêche de participer ? Renseignez votre motif d’annulation pour
                transmettre votre dossier à l’organisateur de l’événement.
              </p>
            </div>

            {/* Reassurance Callout */}
            <div className="p-4 bg-amber-50/70 border border-amber-200 rounded-2xl text-xs sm:text-sm text-amber-900 flex items-start gap-3">
              <HelpCircle className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-bold text-amber-950">Comment fonctionne l’annulation ?</p>
                <p className="text-xs text-amber-800 leading-relaxed">
                  Vos stands restent attribués jusqu’à l’arbitrage de l’organisateur. Si votre
                  demande est validée, le remboursement éventuel sera déclenché selon le règlement du
                  vide-grenier.
                </p>
              </div>
            </div>

            {/* Form Error Alert */}
            {formError && (
              <div className="p-3.5 bg-red-50 border border-red-200 text-red-800 rounded-xl text-xs flex items-start gap-2.5 animate-fade-in">
                <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              {/* Reason Selector */}
              <div className="space-y-2.5">
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-700">
                  Motif de l’annulation <span className="text-red-500">*</span>
                </label>
                <div className="grid grid-cols-1 gap-2.5">
                  {CANCELLATION_REASON_OPTIONS.map((r) => {
                    const isSelected = selectedReason === r.id;
                    return (
                      <label
                        key={r.id}
                        className={`p-3.5 rounded-xl border flex items-start gap-3 cursor-pointer transition ${
                          isSelected
                            ? 'bg-emerald-50/50 border-emerald-500 ring-2 ring-emerald-500/20 shadow-sm'
                            : 'bg-white border-gray-200 hover:bg-gray-50/80'
                        }`}
                      >
                        <input
                          type="radio"
                          name="cancellation_reason"
                          value={r.id}
                          checked={isSelected}
                          onChange={() => setSelectedReason(r.id)}
                          className="mt-0.5 text-emerald-600 focus:ring-emerald-500"
                        />
                        <div className="space-y-0.5">
                          <div className="text-xs sm:text-sm font-bold text-gray-900">
                            {r.label}
                          </div>
                          <div className="text-xs text-gray-500">{r.description}</div>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Comment Field */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="cancellation_comment"
                    className="block text-xs font-bold uppercase tracking-wider text-gray-700"
                  >
                    Commentaire explicatif{' '}
                    {selectedReason === 'other' ? (
                      <span className="text-red-500 font-bold">(obligatoire pour « Autre »)</span>
                    ) : (
                      <span className="text-gray-400 font-normal">(facultatif)</span>
                    )}
                  </label>
                  <span className="text-[11px] text-gray-400 font-mono">
                    {comment.length} / 1000
                  </span>
                </div>
                <textarea
                  id="cancellation_comment"
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  maxLength={1000}
                  rows={4}
                  placeholder={
                    selectedReason === 'other'
                      ? 'Précisez obligatoirement les motifs de votre demande...'
                      : 'Informations complémentaires utiles pour l’organisateur...'
                  }
                  className="w-full p-3 text-xs sm:text-sm rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition"
                />
              </div>

              {/* Submit Buttons */}
              <div className="pt-3 flex flex-col sm:flex-row items-center justify-end gap-3">
                {onNavigateToConfirmation && (
                  <button
                    type="button"
                    onClick={() => onNavigateToConfirmation(accessToken)}
                    disabled={submitting}
                    className="w-full sm:w-auto px-5 py-2.5 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-xs font-semibold shadow-sm transition disabled:opacity-50"
                  >
                    Annuler et retourner
                  </button>
                )}
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full sm:w-auto px-6 py-3 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs sm:text-sm shadow-sm transition flex items-center justify-center gap-2 active:scale-95 disabled:opacity-50 cursor-pointer"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Transmission en cours...</span>
                    </>
                  ) : (
                    <span>Confirmer ma demande d’annulation</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        )}
      </main>
    </div>
  );
};

export default CancellationPage;
