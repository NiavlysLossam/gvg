import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { AlertCircle, AlertTriangle, ArrowLeft, Map as MapIcon, X } from 'lucide-react';
import { PublicEventResponse, PublicSpotFeature, CartResponse } from '../types/public';
import { fetchPublicEvent, fetchPublicSpots, fetchCart, lockSpot, unlockSpot } from '../lib/api';
import { getSessionToken } from '../lib/session';
import { PublicHeader } from '../components/public/PublicHeader';
import { PublicMap } from '../components/public/PublicMap';
import { CartDrawer } from '../components/public/CartDrawer';
import { SpotDetailDrawer } from '../components/public/SpotDetailDrawer';

interface PublicEventPageProps {
  slug: string;
  onNavigateHome?: () => void;
  onNavigateToShowcase?: () => void;
  onNavigateToReservation?: () => void;
}

interface ToastState {
  id: number;
  message: string;
  type: 'error' | 'warning' | 'info' | 'success';
}

function extractErrorDetail(err: any, defaultMsg: string): string {
  if (!err) return defaultMsg;
  const detail = err.detail || err.message;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail[0]?.msg || JSON.stringify(detail[0]) || defaultMsg;
  }
  if (typeof detail === 'object') {
    return JSON.stringify(detail);
  }
  return defaultMsg;
}

export const PublicEventPage: React.FC<PublicEventPageProps> = ({
  slug,
  onNavigateHome,
  onNavigateToShowcase,
  onNavigateToReservation,
}) => {
  const [event, setEvent] = useState<PublicEventResponse | null>(null);
  const [spots, setSpots] = useState<PublicSpotFeature[]>([]);
  const [cart, setCart] = useState<CartResponse | null>(null);
  const [selectedSpot, setSelectedSpot] = useState<PublicSpotFeature | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [notFound, setNotFound] = useState<boolean>(false);
  const [initialError, setInitialError] = useState<string | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [removingSpotId, setRemovingSpotId] = useState<string | null>(null);
  const [pendingSpotIds, setPendingSpotIds] = useState<Set<string>>(new Set());
  const [toasts, setToasts] = useState<ToastState[]>([]);

  // Persistent anonymous session token
  const [sessionToken] = useState<string>(() => getSessionToken());

  // Set of spot IDs currently in cart
  const cartSpotIds = useMemo(() => {
    return new Set(cart?.spots?.map((s) => s.id) || []);
  }, [cart]);

  // Toast notifications helper
  const showToast = useCallback(
    (message: string, type: 'error' | 'warning' | 'info' | 'success' = 'info') => {
      const id = Date.now() + Math.random();
      setToasts((prev) => [...prev, { id, message, type }]);
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 5000);
    },
    []
  );

  // Initial event + spots + cart load
  const loadInitialData = useCallback(async () => {
    setLoading(true);
    setNotFound(false);
    setInitialError(null);
    setErrorBanner(null);

    try {
      const [eventData, spotsData, cartData] = await Promise.all([
        fetchPublicEvent(slug),
        fetchPublicSpots(slug),
        fetchCart(slug, sessionToken).catch(() => null),
      ]);
      setEvent(eventData);
      setSpots(spotsData.features);
      if (cartData && cartData.total_count > 0) {
        setCart(cartData);
      }
    } catch (err: any) {
      if (err?.status === 404 || err?.message?.includes('introuvable')) {
        setNotFound(true);
      } else {
        setInitialError(extractErrorDetail(err, 'Impossible de charger le vide-grenier'));
      }
    } finally {
      setLoading(false);
    }
  }, [slug, sessionToken]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Isolated spots polling (only re-fetches dynamic spots, only when tab is visible)
  const pollSpots = useCallback(async () => {
    if (typeof document !== 'undefined' && document.visibilityState !== 'visible') {
      return;
    }
    try {
      setIsRefreshing(true);
      const [spotsData, cartData] = await Promise.all([
        fetchPublicSpots(slug),
        fetchCart(slug, sessionToken).catch(() => null),
      ]);
      setSpots(spotsData.features);
      if (cartData) {
        setCart((prev) => {
          // If previous cart had items but server returned 0 items, timer expired on server
          if (prev && prev.total_count > 0 && cartData.total_count === 0) {
            showToast(
              'Votre réservation temporaire a expiré, les stands ont été libérés',
              'warning'
            );
          }
          return cartData.total_count > 0 ? cartData : null;
        });
      }
      setSelectedSpot((curr) => {
        if (!curr) return null;
        return spotsData.features.find((s) => s.id === curr.id) || curr;
      });
      setErrorBanner(null);
    } catch {
      setErrorBanner('Impossible de rafraîchir le plan');
      setTimeout(() => setErrorBanner(null), 4000);
    } finally {
      setIsRefreshing(false);
    }
  }, [slug, sessionToken, showToast]);

  // Stable 10-second polling interval for real-time spots updates
  useEffect(() => {
    if (!event) return;
    const interval = setInterval(() => {
      pollSpots();
    }, 10000);
    return () => clearInterval(interval);
  }, [event?.id, pollSpots]);

  // Handle spot selection/toggle on map
  const handleSpotSelect = async (spot: PublicSpotFeature) => {
    // Guard against rapid duplicate clicks
    if (pendingSpotIds.has(spot.id)) {
      return;
    }

    setPendingSpotIds((prev) => new Set(prev).add(spot.id));
    try {
      const isInCart = cartSpotIds.has(spot.id);

      // 1. If stall is already in Monique's cart: toggle unlock / deselect
      if (isInCart) {
        try {
          const updatedCart = await unlockSpot(slug, spot.id, sessionToken);
          setCart(updatedCart.total_count > 0 ? updatedCart : null);
          setSpots((prev) =>
            prev.map((s) =>
              s.id === spot.id
                ? { ...s, properties: { ...s.properties, status: 'available' } }
                : s
            )
          );
        } catch (err: any) {
          showToast(extractErrorDetail(err, 'Impossible de retirer cet emplacement'), 'error');
          pollSpots();
        }
        return;
      }

      // 2. If stall is sold or blocked
      if (spot.properties.status === 'reserved' || spot.properties.status === 'blocked') {
        showToast("Cet emplacement n'est plus disponible à la vente", 'warning');
        setSelectedSpot(spot);
        return;
      }

      // 3. If stall is available (or locked by someone else / expired)
      try {
        const updatedCart = await lockSpot(slug, spot.id, sessionToken);
        setCart(updatedCart);
        setSpots((prev) =>
          prev.map((s) =>
            s.id === spot.id
              ? { ...s, properties: { ...s.properties, status: 'locked' } }
              : s
          )
        );
        // Close inspection drawer if open
        setSelectedSpot(null);
      } catch (err: any) {
        const detailStr = extractErrorDetail(err, 'Impossible de réserver cet emplacement');
        if (err?.status === 409 || detailStr.includes('autre visiteur')) {
          showToast(
            detailStr || 'Ce stand est en cours de commande par un autre visiteur',
            'warning'
          );
        } else if (detailStr.includes('disponible')) {
          showToast(detailStr || "Cet emplacement n'est plus disponible à la vente", 'warning');
        } else {
          showToast(detailStr, 'error');
        }
        pollSpots();
      }
    } finally {
      setPendingSpotIds((prev) => {
        const next = new Set(prev);
        next.delete(spot.id);
        return next;
      });
    }
  };

  // Remove spot from Cart Drawer
  const handleRemoveSpot = async (spotId: string) => {
    if (pendingSpotIds.has(spotId)) {
      return;
    }
    setPendingSpotIds((prev) => new Set(prev).add(spotId));
    setRemovingSpotId(spotId);
    try {
      const updatedCart = await unlockSpot(slug, spotId, sessionToken);
      setCart(updatedCart.total_count > 0 ? updatedCart : null);
      setSpots((prev) =>
        prev.map((s) =>
          s.id === spotId
            ? { ...s, properties: { ...s.properties, status: 'available' } }
            : s
        )
      );
    } catch (err: any) {
      showToast(extractErrorDetail(err, 'Impossible de retirer ce stand'), 'error');
      pollSpots();
    } finally {
      setRemovingSpotId(null);
      setPendingSpotIds((prev) => {
        const next = new Set(prev);
        next.delete(spotId);
        return next;
      });
    }
  };

  // Hold Timer expiration (00:00) handler
  const handleTimerExpired = useCallback(() => {
    setCart(null);
    showToast(
      'Votre réservation temporaire a expiré, les stands ont été libérés',
      'warning'
    );
    pollSpots();
  }, [pollSpots, showToast]);

  // Proceed to checkout callback
  const handleProceedToCheckout = () => {
    if (onNavigateToReservation) {
      onNavigateToReservation();
    } else {
      const reservationUrl = `/e/${encodeURIComponent(slug)}/reservation`;
      window.history.pushState({}, '', reservationUrl);
      window.dispatchEvent(new PopStateEvent('popstate'));
    }
  };

  // Close inspection drawer
  const handleCloseDrawer = () => {
    setSelectedSpot(null);
  };

  // 1. Loading State (Skeleton Loader)
  if (loading && !event && !notFound && !initialError) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full text-center space-y-4 animate-pulse">
          <div className="w-16 h-16 bg-emerald-100 text-emerald-700 rounded-2xl flex items-center justify-center mx-auto shadow-xs">
            <MapIcon className="w-8 h-8 animate-bounce" />
          </div>
          <div className="h-6 bg-gray-200 rounded-lg w-3/4 mx-auto" />
          <div className="h-4 bg-gray-200 rounded-lg w-1/2 mx-auto" />
          <p className="text-sm font-medium text-gray-600 pt-2">
            Chargement du plan du vide-grenier...
          </p>
        </div>
      </div>
    );
  }

  // 2. Not Found State (404)
  if (notFound) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center">
          <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-extrabold text-gray-900">Événement introuvable</h2>
          <p className="text-sm text-gray-500 mt-2 leading-relaxed">
            Le vide-grenier demandé n'existe pas ou l'adresse URL est incorrecte.
          </p>
          {onNavigateHome && (
            <button
              onClick={onNavigateHome}
              className="mt-6 inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-semibold shadow-xs transition active:scale-95"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Retour à l'accueil</span>
            </button>
          )}
        </div>
      </div>
    );
  }

  // 3. Full-page Error State (Network or server error on initial load)
  if (initialError) {
    return (
      <div className="min-h-screen bg-[#FBFBFA] flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full bg-white rounded-2xl shadow-sm border border-gray-200 p-8 text-center">
          <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <AlertCircle className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-extrabold text-gray-900">Erreur de chargement</h2>
          <p className="text-sm text-gray-500 mt-2 leading-relaxed">{initialError}</p>
          <div className="mt-6 flex items-center justify-center gap-3">
            {onNavigateHome && (
              <button
                onClick={onNavigateHome}
                className="px-4 py-2.5 rounded-xl border border-gray-200 text-gray-700 hover:bg-gray-50 text-sm font-semibold transition"
              >
                Accueil
              </button>
            )}
            <button
              onClick={() => loadInitialData()}
              className="px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-sm font-semibold shadow-xs transition active:scale-95"
            >
              Réessayer
            </button>
          </div>
        </div>
      </div>
    );
  }

  // 4. Nominal Public Map Presentation
  return (
    <div className="h-screen w-full flex flex-col bg-[#FBFBFA] overflow-hidden">
      {/* Toast Notification Stack */}
      <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 flex flex-col items-center gap-2 max-w-md w-full px-4 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto w-full px-4 py-3 rounded-2xl shadow-xl border text-sm font-semibold flex items-center gap-2.5 transition-all duration-200 ${
              t.type === 'warning'
                ? 'bg-amber-600 text-white border-amber-700 shadow-amber-500/20'
                : t.type === 'error'
                ? 'bg-red-600 text-white border-red-700 shadow-red-500/20'
                : t.type === 'success'
                ? 'bg-emerald-700 text-white border-emerald-800 shadow-emerald-500/20'
                : 'bg-gray-900 text-white border-gray-800 shadow-gray-900/20'
            }`}
            role="alert"
          >
            <AlertCircle className="w-5 h-5 flex-shrink-0" />
            <span className="flex-1 leading-snug">{t.message}</span>
            <button
              onClick={() => setToasts((prev) => prev.filter((item) => item.id !== t.id))}
              className="p-1 hover:bg-white/20 rounded-lg transition"
              aria-label="Fermer l'alerte"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      {/* Discreet refresh error banner */}
      {errorBanner && (
        <div className="fixed top-2 left-1/2 transform -translate-x-1/2 z-40 bg-amber-50 border border-amber-300 text-amber-900 px-4 py-2 rounded-full shadow-lg text-xs font-semibold flex items-center gap-2 animate-fade-in">
          <AlertTriangle className="w-4 h-4 text-amber-600" />
          <span>{errorBanner}</span>
        </div>
      )}

      {/* Public Header */}
      {event && (
        <PublicHeader
          event={event}
          onRefresh={pollSpots}
          isRefreshing={isRefreshing}
          onNavigateToShowcase={onNavigateToShowcase}
        />
      )}

      {/* Main Map Area */}
      <main className="flex-1 min-h-0 w-full relative">
        {event && (
          <PublicMap
            event={event}
            spots={spots}
            selectedSpot={selectedSpot}
            cartSpotIds={cartSpotIds}
            onSpotSelect={handleSpotSelect}
          />
        )}
      </main>

      {/* Collapsible Floating Cart Drawer */}
      <CartDrawer
        cart={cart}
        onRemoveSpot={handleRemoveSpot}
        onTimerExpired={handleTimerExpired}
        onProceedToCheckout={handleProceedToCheckout}
        removingSpotId={removingSpotId}
      />

      {/* Stall Detail Inspection Drawer (for reserved/blocked stalls) */}
      <SpotDetailDrawer
        spot={selectedSpot}
        onClose={handleCloseDrawer}
      />
    </div>
  );
};


