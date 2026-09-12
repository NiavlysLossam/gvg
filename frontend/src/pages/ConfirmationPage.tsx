import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  CheckCircle2,
  Calendar,
  MapPin,
  Clock,
  ArrowLeft,
  Download,
  AlertCircle,
  Loader2,
  Share2,
  HelpCircle,
  ShoppingBag,
} from 'lucide-react';
import { OrderOut } from '../types/order';
import { PublicEventResponse } from '../types/public';
import { fetchPublicOrder, fetchPublicEvent } from '../lib/api';

interface ConfirmationPageProps {
  slug: string;
  orderId: string;
  onNavigateToMap: () => void;
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

function formatDate(isoDate: string): string {
  try {
    const d = new Date(isoDate);
    return new Intl.DateTimeFormat('fr-FR', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    }).format(d);
  } catch {
    return isoDate;
  }
}

export const ConfirmationPage: React.FC<ConfirmationPageProps> = ({
  slug,
  orderId,
  onNavigateToMap,
  onNavigateHome,
}) => {
  const [event, setEvent] = useState<PublicEventResponse | null>(null);
  const [order, setOrder] = useState<OrderOut | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [polling, setPolling] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState<boolean>(false);

  const isFailedRedirect = useMemo(() => {
    if (typeof window === 'undefined') return false;
    const params = new URLSearchParams(window.location.search);
    return params.get('redirect_status') === 'failed';
  }, []);

  // Retrieve token from URL query params or sessionStorage

  const accessToken = useMemo(() => {
    if (typeof window === 'undefined') return '';
    const params = new URLSearchParams(window.location.search);
    const queryToken = params.get('token') || params.get('access_token');
    if (queryToken) return queryToken;

    // Fallback to sessionStorage
    try {
      const stored = window.sessionStorage.getItem(`gvg_order_token_${orderId}`);
      if (stored) return stored;
    } catch {
      // ignore
    }
    return '';
  }, [orderId]);

  // Initial load
  const loadInitialData = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);

    if (!accessToken) {
      setErrorMessage(
        'Jeton d’accès manquant. Veuillez utiliser le lien reçu par email ou présent dans votre confirmation.'
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
      setErrorMessage(err?.detail || err?.message || 'Impossible de charger les détails de la confirmation.');
    } finally {
      setLoading(false);
    }
  }, [slug, orderId, accessToken]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Soft Polling fallback if webhook is slightly delayed during 3DS redirection
  useEffect(() => {
    if (!order || order.status === 'confirmed' || !accessToken) {
      setPolling(false);
      return;
    }

    setPolling(true);
    let attempts = 0;
    const maxAttempts = 15; // Poll up to 30 seconds

    const pollInterval = setInterval(async () => {
      attempts += 1;
      try {
        const refreshed = await fetchPublicOrder(slug, orderId, accessToken);
        if (refreshed.status === 'confirmed') {
          setOrder(refreshed);
          setPolling(false);
          clearInterval(pollInterval);
        }
      } catch {
        // Polling failure: ignore and retry
      }

      if (attempts >= maxAttempts) {
        clearInterval(pollInterval);
        setPolling(false);
      }
    }, 2000);

    return () => clearInterval(pollInterval);
  }, [order?.status, slug, orderId, accessToken]);

  // Add to Calendar (.ics download) helper
  const handleDownloadCalendar = () => {
    if (!event) return;
    const title = event.title || 'Vide-Grenier';
    const address = event.location_address || '';
    const description = `Réservation pour le vide-grenier ${title}. Commande n° ${order?.order_number || ''}`;

    const startDate = event.start_date ? new Date(event.start_date) : new Date();
    const endDate = event.end_date ? new Date(event.end_date) : new Date(startDate.getTime() + 8 * 3600 * 1000);

    const formatIcsDate = (d: Date) => d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');

    const icsContent = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//GVG//Gestion Vide Greniers//FR',
      'BEGIN:VEVENT',
      `SUMMARY:${title}`,
      `DESCRIPTION:${description}`,
      `LOCATION:${address}`,
      `DTSTART:${formatIcsDate(startDate)}`,
      `DTEND:${formatIcsDate(endDate)}`,
      'STATUS:CONFIRMED',
      'END:VEVENT',
      'END:VCALENDAR',
    ].join('\r\n');

    const blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `vide-grenier-${slug}.ics`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Copy link helper
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


  // 1. Loading Skeleton
  if (loading) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full space-y-4 animate-pulse text-center">
          <div className="w-16 h-16 bg-emerald-100 text-emerald-700 rounded-2xl flex items-center justify-center mx-auto">
            <Loader2 className="w-8 h-8 animate-spin" />
          </div>
          <div className="h-6 bg-gray-200 rounded-lg w-3/4 mx-auto" />
          <div className="h-4 bg-gray-200 rounded-lg w-1/2 mx-auto" />
          <p className="text-sm font-medium text-gray-500 pt-2">
            Chargement de votre confirmation...
          </p>
        </div>
      </div>
    );
  }

  // 2. Error State
  if (errorMessage || !order) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-3xl shadow-sm border border-gray-200 p-8 text-center space-y-4">
          <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto">
            <AlertCircle className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-extrabold text-gray-900">Impossible d'afficher la confirmation</h2>
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

  const isConfirmed = order.status === 'confirmed';

  return (
    <div className="min-h-screen bg-[#FBFBFA] flex flex-col">
      {/* Top Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-xs">
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
            <button
              onClick={onNavigateToMap}
              className="inline-flex items-center gap-2 text-sm font-semibold text-gray-600 hover:text-gray-900 transition active:scale-95"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Retour au plan</span>
            </button>
          </div>
          <div className="text-right">

            <span className="font-mono text-xs font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-full">
              {order.order_number}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-3xl w-full mx-auto px-4 sm:px-6 py-8 space-y-6">
        {/* Failed Redirect Alert */}
        {isFailedRedirect && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-2xl text-red-800 text-sm flex items-start gap-3 animate-fade-in">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-bold">Le paiement par redirection bancaire a échoué</p>
              <p className="text-xs text-red-700 leading-relaxed">
                L'authentification auprès de votre établissement bancaire n'a pas abouti ou a été annulée. Veuillez retourner au plan pour renouveler votre commande.
              </p>
            </div>
          </div>
        )}

        {/* Webhook in-flight Soft Polling Banner */}
        {polling && !isConfirmed && (
          <div className="p-4 bg-amber-50 border border-amber-200 rounded-2xl text-amber-900 text-sm flex items-center gap-3 animate-pulse">
            <Loader2 className="w-5 h-5 text-amber-700 animate-spin flex-shrink-0" />
            <div>
              <p className="font-bold">Confirmation de votre règlement en cours...</p>
              <p className="text-xs text-amber-800 mt-0.5">
                Nous synchronisons votre transaction avec la banque. Votre écran se mettra à jour automatiquement.
              </p>
            </div>
          </div>
        )}

        {/* Celebration / Success Hero Banner (strictly gated on isConfirmed) */}
        {isConfirmed ? (
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-gray-200 shadow-sm text-center space-y-4 animate-fade-in">
            <div className="w-20 h-20 bg-emerald-100 text-emerald-700 rounded-full flex items-center justify-center mx-auto shadow-sm">
              <CheckCircle2 className="w-12 h-12 text-emerald-700" />
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 leading-tight">
              Bravo {order.first_name}, votre stand est réservé !
            </h1>

            <p className="text-sm sm:text-base text-gray-600 max-w-lg mx-auto leading-relaxed">
              Votre commande <strong className="text-gray-900 font-mono">{order.order_number}</strong> a bien
              été enregistrée. Pensez à imprimer votre attestation sur l'honneur pour le jour du vide-grenier.
            </p>

            <div className="pt-2 flex flex-wrap justify-center gap-3">
              <button
                onClick={handleCopyLink}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-gray-200 bg-white hover:bg-gray-50 text-gray-700 text-xs font-semibold shadow-xs transition"
              >
                <Share2 className="w-3.5 h-3.5 text-gray-500" />
                <span>{copiedLink ? 'Lien copié !' : 'Partager ou conserver mon lien'}</span>
              </button>
              <button
                onClick={handleDownloadCalendar}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-emerald-200 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-semibold shadow-xs transition"
              >
                <Calendar className="w-3.5 h-3.5 text-emerald-700" />
                <span>Ajouter à mon agenda</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-amber-200 shadow-sm text-center space-y-4 animate-fade-in">
            <div className="w-16 h-16 bg-amber-100 text-amber-700 rounded-full flex items-center justify-center mx-auto shadow-sm">
              <Loader2 className="w-10 h-10 text-amber-700 animate-spin" />
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-gray-900 leading-tight">
              Validation de votre commande en cours...
            </h1>
            <p className="text-sm text-gray-600 max-w-md mx-auto leading-relaxed">
              Votre règlement pour la commande <strong className="text-gray-900 font-mono">{order.order_number}</strong> est en cours de vérification. Vos stands restent temporairement bloqués.
            </p>
          </div>
        )}

        {/* Reserved Stalls Card */}
        <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100">
            <h2 className="text-sm font-bold uppercase tracking-wider text-gray-900 flex items-center gap-2">
              <ShoppingBag className="w-4 h-4 text-emerald-700" />
              <span>Vos emplacements réservés ({order.items.length})</span>
            </h2>
            <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200">
              {isConfirmed ? 'Confirmé & Payé' : 'En attente de confirmation'}
            </span>
          </div>

          <div className="divide-y divide-gray-100">
            {order.items.map((it) => (
              <div key={it.id} className="py-3 flex items-center justify-between text-sm">
                <div>
                  <span className="font-bold text-gray-900">
                    Stand {it.spot_label || 'Emplacement'}
                  </span>
                  {it.spot_linear_meters && (
                    <span className="text-gray-500 text-xs ml-2">
                      ({formatMeters(it.spot_linear_meters)} m)
                    </span>
                  )}
                </div>
                <span className="font-mono font-semibold text-gray-800">
                  {formatPrice(it.price)}
                </span>
              </div>
            ))}
          </div>

          <div className="pt-3 border-t border-gray-200 flex items-center justify-between">
            <span className="text-sm font-bold text-gray-900">{isConfirmed ? 'Total réglé' : 'Total à régler'}</span>
            <span className="text-xl font-extrabold text-emerald-800 font-mono">
              {formatPrice(order.total_price)}
            </span>
          </div>
        </div>

        {/* Event Details Card */}
        {event && (
          <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm space-y-3">
            <h2 className="text-sm font-bold uppercase tracking-wider text-gray-900">
              Rappels pratiques pour le Jour J
            </h2>

            <div className="space-y-2 text-sm text-gray-600">
              <p className="font-bold text-gray-900">{event.title}</p>
              {event.location_address && (
                <div className="flex items-start gap-2">
                  <MapPin className="w-4 h-4 text-emerald-700 flex-shrink-0 mt-0.5" />
                  <span>{event.location_address}</span>
                </div>
              )}
              {event.start_date && (
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-emerald-700 flex-shrink-0" />
                  <span>{formatDate(event.start_date)}</span>
                </div>
              )}
              {event.setup_start_time && (
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-emerald-700 flex-shrink-0" />
                  <span>Accueil et installation des exposants dès {event.setup_start_time}</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Sworn Statement PDF Notice & Download Action (only when confirmed) */}
        {isConfirmed && (
          <div className="bg-emerald-50/70 border border-emerald-200 rounded-2xl p-5 text-emerald-950 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 animate-fade-in">
            <div className="space-y-1">
              <p className="font-bold text-sm text-emerald-900 flex items-center gap-2">
                <Download className="w-4 h-4 text-emerald-700" />
                <span>Attestation sur l'honneur à signer</span>
              </p>
              <p className="text-xs text-emerald-800 leading-relaxed max-w-md">
                Conformément à l'art. L310-2 du Code de commerce, présentez ce document signé aux organisateurs le dimanche matin.
              </p>
            </div>
            <button
              onClick={() => window.print()}
              className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold shadow-xs transition flex items-center justify-center gap-2 cursor-pointer"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Imprimer / Télécharger</span>
            </button>
          </div>
        )}


        {/* Cancellation Placeholder Card */}
        <div className="p-4 bg-gray-50 border border-gray-200 rounded-2xl text-xs text-gray-500 flex items-start gap-3">
          <HelpCircle className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-gray-700">Besoin d'annuler ou de modifier ?</p>
            <p className="leading-relaxed">
              En cas d'empêchement, vous pouvez solliciter une annulation auprès des organisateurs grâce à votre jeton d'accès sécurisé.
            </p>
          </div>
        </div>

        {/* Bottom Return CTA */}
        <div className="pt-4 flex justify-center">
          <button
            onClick={onNavigateToMap}
            className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-sm shadow-sm transition active:scale-95"
          >
            Retourner au plan du vide-grenier
          </button>
        </div>
      </main>
    </div>
  );
};
