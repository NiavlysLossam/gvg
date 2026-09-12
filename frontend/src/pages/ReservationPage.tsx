import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ArrowLeft,
  Clock,
  MapPin,
  Calendar,
  ShoppingBag,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  RotateCcw,
  Sparkles,
} from 'lucide-react';

import { PublicEventResponse, CartResponse } from '../types/public';
import { OrderOut } from '../types/order';
import { fetchPublicEvent, fetchCart } from '../lib/api';
import { getSessionToken } from '../lib/session';
import { GuestCheckoutForm } from '../components/checkout/GuestCheckoutForm';
import { StripePaymentForm } from '../components/checkout/StripePaymentForm';

interface ReservationPageProps {
  slug: string;
  onNavigateToMap: () => void;
  onNavigateHome?: () => void;
  onNavigateToConfirmation: (slug: string, orderId: string, accessToken: string) => void;
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

export const ReservationPage: React.FC<ReservationPageProps> = ({
  slug,
  onNavigateToMap,
  onNavigateHome,
  onNavigateToConfirmation,
}) => {

  const [event, setEvent] = useState<PublicEventResponse | null>(null);
  const [cart, setCart] = useState<CartResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [notFound, setNotFound] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isExpired, setIsExpired] = useState<boolean>(false);
  const [remainingSeconds, setRemainingSeconds] = useState<number>(0);
  const [completedOrder, setCompletedOrder] = useState<OrderOut | null>(null);

  const [sessionToken] = useState<string>(() => getSessionToken());

  // Load initial event and cart data
  const loadData = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    setNotFound(false);
    setIsExpired(false);

    try {
      const [eventData, cartData] = await Promise.all([
        fetchPublicEvent(slug),
        fetchCart(slug, sessionToken).catch(() => null),
      ]);
      setEvent(eventData);
      if (cartData && cartData.total_count > 0) {
        setCart(cartData);
      } else {
        setCart(null);
      }
    } catch (err: any) {
      if (err?.status === 404 || err?.message?.includes('introuvable')) {
        setNotFound(true);
      } else {
        setFetchError(err?.detail || err?.message || 'Erreur lors du chargement de la réservation');
      }
    } finally {
      setLoading(false);
    }
  }, [slug, sessionToken]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Hold Timer synchronization
  const expiresAt = cart?.expires_at;
  const totalCount = cart?.total_count || 0;

  useEffect(() => {
    if (!expiresAt || totalCount === 0 || completedOrder) {
      setRemainingSeconds(0);
      return;
    }

    const calculateRemaining = () => {
      if (!expiresAt) return 0;
      const hasTimezone = /[Zz]$|[+-]\d{2}:\d{2}$/.test(expiresAt);
      const normalizedIso = hasTimezone ? expiresAt : `${expiresAt}Z`;
      const expiryTime = new Date(normalizedIso).getTime();
      if (isNaN(expiryTime)) return 0;
      const now = Date.now();
      return Math.max(0, Math.floor((expiryTime - now) / 1000));
    };

    const initial = calculateRemaining();
    setRemainingSeconds(initial);

    if (initial <= 0) {
      setIsExpired(true);
      return;
    }

    const interval = setInterval(() => {
      const remaining = calculateRemaining();
      setRemainingSeconds(remaining);
      if (remaining <= 0) {
        clearInterval(interval);
        setIsExpired(true);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [expiresAt, totalCount, completedOrder]);

  const timerDisplay = useMemo(() => {
    if (isNaN(remainingSeconds) || remainingSeconds < 0) return '00:00';
    const mins = Math.floor(remainingSeconds / 60);
    const secs = remainingSeconds % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }, [remainingSeconds]);

  const isUrgent = remainingSeconds > 0 && remainingSeconds <= 120;

  // Handle successful order creation
  const handleOrderCreated = (order: OrderOut) => {
    setCompletedOrder(order);
  };

  const handleExpired = () => {
    setIsExpired(true);
  };

  // 1. Loading Skeleton
  if (loading && !event && !notFound) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full space-y-4 animate-pulse text-center">
          <div className="w-16 h-16 bg-emerald-100 text-emerald-700 rounded-2xl flex items-center justify-center mx-auto">
            <ShoppingBag className="w-8 h-8 animate-bounce" />
          </div>
          <div className="h-6 bg-gray-200 rounded-lg w-3/4 mx-auto" />
          <div className="h-4 bg-gray-200 rounded-lg w-1/2 mx-auto" />
          <p className="text-sm font-medium text-gray-500 pt-2">
            Préparation de votre réservation...
          </p>
        </div>
      </div>
    );
  }

  // 2. Not Found
  if (notFound) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center">
          <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-extrabold text-gray-900">Événement introuvable</h2>
          <p className="text-sm text-gray-500 mt-2">
            Le vide-grenier demandé n'existe pas ou l'adresse URL est incorrecte.
          </p>
          <button
            onClick={onNavigateHome || onNavigateToMap}
            className="mt-6 inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-semibold transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Retour à l'accueil</span>
          </button>
        </div>
      </div>
    );
  }

  // 2b. Fetch Error State
  if (fetchError && !event) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center">
          <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-extrabold text-gray-900">Erreur de chargement</h2>
          <p className="text-sm text-gray-500 mt-2 leading-relaxed">{fetchError}</p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <button
              onClick={onNavigateToMap}
              className="px-4 py-2.5 rounded-xl border border-gray-200 text-gray-700 hover:bg-gray-50 text-sm font-semibold transition"
            >
              Retour au plan
            </button>
            <button
              onClick={() => loadData()}
              className="px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-semibold shadow-sm transition active:scale-95"
            >
              Réessayer
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 3. Step 2: Stripe Elements Payment View
  if (completedOrder && event) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col">
        <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-xs">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
            <button
              onClick={onNavigateToMap}
              className="inline-flex items-center gap-2 text-sm font-semibold text-gray-600 hover:text-gray-900 transition active:scale-95"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">Retour au plan</span>
              <span className="sm:hidden">Plan</span>
            </button>
            <div className="text-right flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-800 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-full font-mono">
                Commande {completedOrder.order_number}
              </span>
            </div>
          </div>
        </header>

        <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-8">
          <div className="mb-6">
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-700 mb-1">
              <span>Étape 2 sur 2</span>
              <span>•</span>
              <span>Règlement par carte bancaire</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900">
              Paiement sécurisé de vos stands
            </h1>
            <p className="text-sm text-gray-500 mt-1">
              Vos coordonnées sont enregistrées. Veuillez saisir votre moyen de paiement pour confirmer définitivement votre réservation.
            </p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
            {/* Left Column: Order Recap */}
            <div className="lg:col-span-5 space-y-4">
              <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-gray-100">
                  <h2 className="text-sm font-bold uppercase tracking-wider text-gray-900 flex items-center gap-2">
                    <ShoppingBag className="w-4 h-4 text-emerald-700" />
                    <span>Récapitulatif ({completedOrder.items.length})</span>
                  </h2>
                  <span className="text-xs font-mono font-bold text-gray-500">
                    {completedOrder.order_number}
                  </span>
                </div>

                <div className="divide-y divide-gray-100 max-h-60 overflow-y-auto pr-1">
                  {completedOrder.items.map((it) => (
                    <div key={it.id} className="py-2.5 flex items-center justify-between text-sm">
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
                  <span className="text-sm font-bold text-gray-900">Total à payer</span>
                  <span className="text-xl font-extrabold text-emerald-800 font-mono">
                    {formatPrice(completedOrder.total_price)}
                  </span>
                </div>
              </div>

              {/* Exhibitor Info Card */}
              <div className="bg-gray-50 rounded-2xl p-5 border border-gray-200 text-xs text-gray-600 space-y-2">
                <p className="font-bold text-gray-800 text-sm">Informations exposant</p>
                <p>
                  <strong>Nom :</strong> {completedOrder.first_name} {completedOrder.last_name}
                </p>
                <p>
                  <strong>Email :</strong> {completedOrder.email}
                </p>
                <p>
                  <strong>Téléphone :</strong> {completedOrder.phone}
                </p>
                <p>
                  <strong>Adresse :</strong> {completedOrder.street_address}, {completedOrder.postal_code} {completedOrder.city}
                </p>
              </div>
            </div>

            {/* Right Column: Stripe Elements Payment Form */}
            <div className="lg:col-span-7">
              <StripePaymentForm
                slug={slug}
                order={completedOrder}
                onSuccess={(orderId) => {
                  try {
                    window.sessionStorage.setItem(`gvg_order_token_${orderId}`, completedOrder.access_token);
                  } catch {
                    // ignore
                  }
                  onNavigateToConfirmation(slug, orderId, completedOrder.access_token);
                }}
                onExpired={handleExpired}
              />
            </div>
          </div>
        </main>
      </div>
    );
  }


  // 4. Expired State (Locks released)
  if (isExpired) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-3xl shadow-sm border border-gray-200 p-8 text-center space-y-4 animate-fade-in">
          <div className="w-16 h-16 bg-amber-100 text-amber-700 rounded-2xl flex items-center justify-center mx-auto">
            <AlertTriangle className="w-8 h-8" />
          </div>

          <h2 className="text-2xl font-extrabold text-gray-900">
            Votre réservation temporaire a expiré
          </h2>

          <p className="text-sm text-gray-600 leading-relaxed">
            Votre délai de 15 minutes est écoulé. Les emplacements ont été automatiquement libérés
            pour les autres exposants.
          </p>

          <div className="pt-4">
            <button
              onClick={onNavigateToMap}
              className="w-full inline-flex items-center justify-center gap-2 py-3.5 px-6 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-sm shadow-sm transition"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Choisir à nouveau mes stands</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 5. Empty Cart State
  if (!cart || cart.total_count === 0) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col">
        {/* Simple Header */}
        <header className="bg-white border-b border-gray-200 h-16 flex items-center px-4 sm:px-6">
          <button
            onClick={onNavigateToMap}
            className="inline-flex items-center gap-2 text-sm font-semibold text-gray-600 hover:text-gray-900 transition"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Retour au plan</span>
          </button>
        </header>

        <main className="flex-1 flex items-center justify-center p-4">
          <div className="max-w-md w-full bg-white rounded-3xl shadow-sm border border-gray-200 p-8 text-center space-y-4">
            <div className="w-16 h-16 bg-gray-100 text-gray-500 rounded-2xl flex items-center justify-center mx-auto">
              <ShoppingBag className="w-8 h-8" />
            </div>

            <h2 className="text-2xl font-extrabold text-gray-900">Votre panier est vide</h2>

            <p className="text-sm text-gray-500 leading-relaxed">
              Vous n'avez aucun emplacement sélectionné pour le moment. Consultez le plan interactif
              pour choisir un ou plusieurs stands disponibles.
            </p>

            <div className="pt-4">
              <button
                onClick={onNavigateToMap}
                className="w-full inline-flex items-center justify-center gap-2 py-3.5 px-6 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white font-bold text-sm shadow-sm transition"
              >
                <span>Choisir des emplacements</span>
                <Sparkles className="w-4 h-4" />
              </button>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // 6. Nominal Checkout Flow
  return (
    <div className="min-h-screen bg-[#FBFBFA] flex flex-col">
      {/* Sticky Top Header with Navigation & Live Hold Timer */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <button
            onClick={onNavigateToMap}
            className="inline-flex items-center gap-2 text-sm font-semibold text-gray-600 hover:text-gray-900 transition active:scale-95"
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">Retour au plan</span>
            <span className="sm:hidden">Plan</span>
          </button>

          {/* Live Hold Timer Pill */}
          <div
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs sm:text-sm font-bold border transition-colors ${
              isUrgent
                ? 'bg-red-50 text-red-700 border-red-300 animate-pulse'
                : 'bg-amber-50 text-amber-800 border-amber-300'
            }`}
            title="Temps restant pour finaliser votre réservation"
          >
            <Clock className={`w-4 h-4 ${isUrgent ? 'text-red-600' : 'text-amber-600'}`} />
            <span>Places réservées :</span>
            <span className="font-mono tracking-wider">{timerDisplay}</span>
          </div>
        </div>
      </header>

      {/* Main Content: Left Column (Cart Summary) + Right Column (Guest Form) */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-8">
        <div className="mb-6">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900">
            Finaliser ma réservation
          </h1>
          {event && (
            <p className="text-sm text-gray-500 mt-1 flex flex-wrap items-center gap-3">
              <span className="font-semibold text-gray-700">{event.title}</span>
              {event.location_address && (
                <span className="flex items-center gap-1">
                  <MapPin className="w-3.5 h-3.5 text-gray-400" />
                  <span>{event.location_address}</span>
                </span>
              )}
              {event.start_date && (
                <span className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-gray-400" />
                  <span>{formatDate(event.start_date)}</span>
                </span>
              )}
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* Left Column: Cart Summary (5 cols on lg) */}
          <div className="lg:col-span-5 space-y-4">
            <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-sm space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-gray-100">
                <h2 className="text-sm font-bold uppercase tracking-wider text-gray-900 flex items-center gap-2">
                  <ShoppingBag className="w-4 h-4 text-emerald-700" />
                  <span>Mes stands sélectionnés ({cart.total_count})</span>
                </h2>
                <button
                  onClick={onNavigateToMap}
                  className="text-xs text-emerald-700 hover:text-emerald-800 font-semibold"
                >
                  Modifier
                </button>
              </div>

              {/* Spots List */}
              <div className="divide-y divide-gray-100 max-h-60 overflow-y-auto pr-1">
                {cart.spots.map((spot) => (
                  <div key={spot.id} className="py-2.5 flex items-center justify-between text-sm">
                    <div>
                      <span className="font-bold text-gray-900">Stand {spot.label}</span>
                      <span className="text-gray-500 text-xs ml-2">
                        ({formatMeters(spot.linear_meters)} m)
                      </span>
                    </div>
                    <span className="font-mono font-semibold text-gray-800">
                      {formatPrice(spot.price)}
                    </span>
                  </div>
                ))}
              </div>

              {/* Total Row */}
              <div className="pt-3 border-t border-gray-200 flex items-center justify-between">
                <div>
                  <p className="text-xs text-gray-500 font-medium">
                    Total métrage : {formatMeters(cart.total_linear_meters)} m
                  </p>
                  <p className="text-sm font-bold text-gray-900">Montant total</p>
                </div>
                <div className="text-right">
                  <span className="text-xl font-extrabold text-emerald-800 font-mono">
                    {formatPrice(cart.total_price)}
                  </span>
                </div>
              </div>
            </div>

            {/* Legal / Reassurance Card */}
            <div className="bg-emerald-50/50 rounded-2xl p-5 border border-emerald-200 text-xs text-emerald-950 space-y-2">
              <p className="font-bold flex items-center gap-1.5 text-emerald-900">
                <CheckCircle2 className="w-4 h-4 text-emerald-700 flex-shrink-0" />
                <span>Simplicité et respect de votre vie privée</span>
              </p>
              <p className="text-emerald-800 leading-relaxed">
                Aucun compte ni mot de passe n'est requis. Nous ne demandons aucune copie de pièce
                d'identité en ligne. Vous recevrez directement un lien sécurisé par email pour
                accéder à votre stand.
              </p>
            </div>
          </div>

          {/* Right Column: Guest Checkout Form (7 cols on lg) */}
          <div className="lg:col-span-7">
            <GuestCheckoutForm
              slug={slug}
              sessionToken={sessionToken}
              totalPriceCents={cart.total_price_cents}
              totalLinearMeters={cart.total_linear_meters}
              totalCount={cart.total_count}
              disabled={isExpired}
              onSubmitOrder={handleOrderCreated}
              onExpired={handleExpired}
            />
          </div>
        </div>
      </main>
    </div>
  );
};
