import React, { useState, useEffect } from 'react';
import {
  PlusCircle,
  ListFilter,
  Map,
  CheckCircle2,
  RefreshCw,
  AlertCircle,
  PenTool,
  Users,
  Loader2,
  ShieldCheck,
  Globe,
  Settings,
} from 'lucide-react';
import { EventModel } from './types/event';
import { fetchEvents, fetchEvent } from './lib/api';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { AdminHeader } from './components/AdminHeader';
import { LoginPage } from './pages/LoginPage';
import { HomePage } from './pages/HomePage';
import { EventForm } from './components/EventForm';
import { EventCard } from './components/EventCard';
import { MapCalibration } from './components/MapCalibration';
import { SpotEditor } from './components/SpotEditor';
import { RegistrationsPage } from './pages/RegistrationsPage';
import { PublicEventPage } from './pages/PublicEventPage';
import { EventShowcasePage } from './pages/EventShowcasePage';
import { ReservationPage } from './pages/ReservationPage';
import { ConfirmationPage } from './pages/ConfirmationPage';
import { CancellationPage } from './pages/CancellationPage';
import { AdminUsersPage } from './pages/AdminUsersPage';
import { EventSettingsPage } from './pages/EventSettingsPage';
import { DeleteEventModal } from './components/DeleteEventModal';

interface PublicRouteState {
  slug: string;
  view: 'showcase' | 'map' | 'reservation' | 'confirmation' | 'cancellation';
  orderId?: string;
}

function parseLoginRoute(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const pathname = window.location.pathname;
    if (pathname === '/login' || pathname.startsWith('/login/')) return true;
    const hash = window.location.hash;
    if (hash === '#/login' || hash.startsWith('#/login')) return true;
    const params = new URLSearchParams(window.location.search);
    if (params.has('login')) return true;
  } catch {
    return false;
  }
  return false;
}

function parseUsersRoute(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const pathname = window.location.pathname;
    if (pathname === '/admin/users' || pathname.startsWith('/admin/users/')) return true;
    const hash = window.location.hash;
    if (hash === '#/admin/users' || hash.startsWith('#/admin/users')) return true;
  } catch {
    return false;
  }
  return false;
}

function parseAdminRoute(): { eventId: string; view: 'inscriptions' } | null {
  if (typeof window === 'undefined') return null;
  try {
    const pathname = window.location.pathname;
    const match = pathname.match(/^\/admin\/(?:e|events)\/([^/?#]+)\/inscriptions\/?$/);
    if (match && match[1]) {
      return { eventId: decodeURIComponent(match[1]), view: 'inscriptions' };
    }
    const hash = window.location.hash;
    const hashMatch = hash.match(/^#\/admin\/(?:e|events)\/([^/?#]+)\/inscriptions\/?$/);
    if (hashMatch && hashMatch[1]) {
      return { eventId: decodeURIComponent(hashMatch[1]), view: 'inscriptions' };
    }
  } catch {
    return null;
  }
  return null;
}

function parseAdminDashboardRoute(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const pathname = window.location.pathname;
    if (pathname === '/admin' || pathname === '/admin/' || pathname.startsWith('/admin/')) return true;
    const hash = window.location.hash;
    if (hash === '#/admin' || hash === '#/admin/' || hash.startsWith('#/admin')) return true;
    const params = new URLSearchParams(window.location.search);
    if (params.has('admin')) return true;
  } catch {
    return false;
  }
  return false;
}

function parsePublicRoute(): PublicRouteState | null {
  if (typeof window === 'undefined') return null;
  try {
    const pathname = window.location.pathname;

    // 0. Pathname: /e/:slug/confirmation/:orderId or /events/:slug/confirmation/:orderId
    const confMatch = pathname.match(/^\/(?:e|events)\/([^/?#]+)\/confirmation\/([^/?#]+)\/?(?:\?.*)?$/);
    if (confMatch && confMatch[1] && confMatch[2]) {
      return {
        slug: decodeURIComponent(confMatch[1]),
        view: 'confirmation',
        orderId: decodeURIComponent(confMatch[2]),
      };
    }

    // 0b. Pathname: /e/:slug/annulation/:orderId or /events/:slug/annulation/:orderId
    const annMatch = pathname.match(/^\/(?:e|events)\/([^/?#]+)\/annulation\/([^/?#]+)\/?(?:\?.*)?$/);
    if (annMatch && annMatch[1] && annMatch[2]) {
      return {
        slug: decodeURIComponent(annMatch[1]),
        view: 'cancellation',
        orderId: decodeURIComponent(annMatch[2]),
      };
    }

    // 1. Pathname: /e/:slug/reservation or /events/:slug/reservation
    const resMatch = pathname.match(/^\/(?:e|events)\/([^/?#]+)\/reservation\/?$/);
    if (resMatch && resMatch[1]) {
      return {
        slug: decodeURIComponent(resMatch[1]),
        view: 'reservation',
      };
    }

    // 2. Pathname: /e/:slug/map or /events/:slug/map
    const mapMatch = pathname.match(/^\/(?:e|events)\/([^/?#]+)\/map\/?$/);
    if (mapMatch && mapMatch[1]) {
      return {
        slug: decodeURIComponent(mapMatch[1]),
        view: 'map',
      };
    }

    // 3. Pathname: /e/:slug or /events/:slug (Showcase)
    const showcaseMatch = pathname.match(/^\/(?:e|events)\/([^/?#]+)\/?$/);
    if (showcaseMatch && showcaseMatch[1]) {
      return {
        slug: decodeURIComponent(showcaseMatch[1]),
        view: 'showcase',
      };
    }

    // 4. Hash routing fallback
    const hash = window.location.hash;
    const hashConfMatch = hash.match(/^#\/(?:e|events)\/([^/?#]+)\/confirmation\/([^/?#]+)\/?(?:\?.*)?$/);
    if (hashConfMatch && hashConfMatch[1] && hashConfMatch[2]) {
      return {
        slug: decodeURIComponent(hashConfMatch[1]),
        view: 'confirmation',
        orderId: decodeURIComponent(hashConfMatch[2]),
      };
    }
    const hashAnnMatch = hash.match(/^#\/(?:e|events)\/([^/?#]+)\/annulation\/([^/?#]+)\/?(?:\?.*)?$/);
    if (hashAnnMatch && hashAnnMatch[1] && hashAnnMatch[2]) {
      return {
        slug: decodeURIComponent(hashAnnMatch[1]),
        view: 'cancellation',
        orderId: decodeURIComponent(hashAnnMatch[2]),
      };
    }
    const hashResMatch = hash.match(/^#\/(?:e|events)\/([^/?#]+)\/reservation\/?$/);
    if (hashResMatch && hashResMatch[1]) {
      return {
        slug: decodeURIComponent(hashResMatch[1]),
        view: 'reservation',
      };
    }
    const hashMapMatch = hash.match(/^#\/(?:e|events)\/([^/?#]+)\/map\/?$/);
    if (hashMapMatch && hashMapMatch[1]) {
      return {
        slug: decodeURIComponent(hashMapMatch[1]),
        view: 'map',
      };
    }
    const hashShowcaseMatch = hash.match(/^#\/(?:e|events)\/([^/?#]+)\/?$/);
    if (hashShowcaseMatch && hashShowcaseMatch[1]) {
      return {
        slug: decodeURIComponent(hashShowcaseMatch[1]),
        view: 'showcase',
      };
    }

    // 4. Query params fallback: ?slug=... &view=confirmation&orderId=...
    const params = new URLSearchParams(window.location.search);
    const slugParam = params.get('slug') || params.get('event');
    if (slugParam) {
      const viewParam = params.get('view');
      const orderIdParam = params.get('orderId') || params.get('order_id') || undefined;
      if (viewParam === 'annulation' || viewParam === 'cancellation' || (params.has('annulation') && orderIdParam)) {
        return {
          slug: slugParam,
          view: 'cancellation',
          orderId: orderIdParam,
        };
      }
      if (viewParam === 'confirmation' || orderIdParam) {
        return {
          slug: slugParam,
          view: 'confirmation',
          orderId: orderIdParam,
        };
      }
      if (viewParam === 'reservation' || params.has('reservation')) {
        return {
          slug: slugParam,
          view: 'reservation',
        };
      }
      if (viewParam === 'map' || params.has('map')) {
        return {
          slug: slugParam,
          view: 'map',
        };
      }
      return {
        slug: slugParam,
        view: 'showcase',
      };
    }
  } catch {
    return null;
  }
  return null;
}


const AppContent: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth();
  const [isLoginRoute, setIsLoginRoute] = useState<boolean>(parseLoginRoute());
  const [isUsersRoute, setIsUsersRoute] = useState<boolean>(parseUsersRoute());
  const [isAdminRoute, setIsAdminRoute] = useState<boolean>(
    parseAdminDashboardRoute() || parseUsersRoute() || Boolean(parseAdminRoute())
  );
  const [publicRoute, setPublicRoute] = useState<PublicRouteState | null>(parsePublicRoute());
  const [activeTab, setActiveTab] = useState<'list' | 'create' | 'calibrate' | 'editor' | 'inscriptions' | 'users' | 'settings'>(
    parseUsersRoute() ? 'users' : 'list'
  );
  const [selectedEvent, setSelectedEvent] = useState<EventModel | null>(null);
  const [eventToDelete, setEventToDelete] = useState<EventModel | null>(null);
  const [events, setEvents] = useState<EventModel[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [notification, setNotification] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    const handlePopState = () => {
      const isLog = parseLoginRoute();
      setIsLoginRoute(isLog);
      const pub = parsePublicRoute();
      setPublicRoute(pub);
      const isUsers = parseUsersRoute();
      setIsUsersRoute(isUsers);
      const isAdm = parseAdminDashboardRoute() || isUsers || Boolean(parseAdminRoute());
      setIsAdminRoute(isAdm);

      if (!pub && isAdm) {
        if (isUsers) {
          setActiveTab('users');
        } else {
          const adm = parseAdminRoute();
          if (adm) {
            setActiveTab('inscriptions');
          } else {
            setActiveTab('list');
          }
        }
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    if (isUsersRoute && isAuthenticated) {
      setActiveTab('users');
    }
  }, [isUsersRoute, isAuthenticated]);

  const navigateToPublic = (slug: string) => {
    window.history.pushState({}, '', `/e/${encodeURIComponent(slug)}`);
    setPublicRoute({ slug, view: 'showcase' });
    setIsAdminRoute(false);
    setIsLoginRoute(false);
  };

  const navigateToMap = (slug: string) => {
    window.history.pushState({}, '', `/e/${encodeURIComponent(slug)}/map`);
    setPublicRoute({ slug, view: 'map' });
    setIsAdminRoute(false);
    setIsLoginRoute(false);
  };

  const navigateToReservation = (slug: string) => {
    window.history.pushState({}, '', `/e/${encodeURIComponent(slug)}/reservation`);
    setPublicRoute({ slug, view: 'reservation' });
    setIsAdminRoute(false);
    setIsLoginRoute(false);
  };

  const navigateToConfirmation = (slug: string, orderId: string, accessToken: string) => {
    window.history.pushState(
      {},
      '',
      `/e/${encodeURIComponent(slug)}/confirmation/${encodeURIComponent(orderId)}?token=${encodeURIComponent(accessToken)}`
    );
    setPublicRoute({ slug, view: 'confirmation', orderId });
    setIsAdminRoute(false);
    setIsLoginRoute(false);
  };

  const navigateToCancellation = (slug: string, orderId: string, accessToken?: string) => {
    const tokenQuery = accessToken ? `?token=${encodeURIComponent(accessToken)}` : '';
    window.history.pushState(
      {},
      '',
      `/e/${encodeURIComponent(slug)}/annulation/${encodeURIComponent(orderId)}${tokenQuery}`
    );
    setPublicRoute({ slug, view: 'cancellation', orderId });
    setIsAdminRoute(false);
    setIsLoginRoute(false);
  };

  const navigateHome = () => {
    window.history.pushState({}, '', '/');
    setPublicRoute(null);
    setIsLoginRoute(false);
    setIsAdminRoute(false);
    setIsUsersRoute(false);
    setActiveTab('list');
  };

  const navigateToAdmin = () => {
    window.history.pushState({}, '', '/admin');
    setPublicRoute(null);
    setIsLoginRoute(false);
    setIsAdminRoute(true);
    setIsUsersRoute(false);
    setActiveTab('list');
  };

  const navigateToLogin = () => {
    if (isAuthenticated) {
      navigateToAdmin();
    } else {
      window.history.pushState({}, '', '/login');
      setPublicRoute(null);
      setIsLoginRoute(true);
      setIsAdminRoute(false);
      setIsUsersRoute(false);
    }
  };

  const loadEvents = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const data = await fetchEvents();
      setEvents(data.items);

      const adm = parseAdminRoute();
      if (adm) {
        const matched = data.items.find((e) => e.id === adm.eventId || e.slug === adm.eventId);
        if (matched) {
          setSelectedEvent(matched);
          setActiveTab('inscriptions');
        } else {
          try {
            const fetched = await fetchEvent(adm.eventId);
            setSelectedEvent(fetched);
            setActiveTab('inscriptions');
          } catch {
            // ignore
          }
        }
      }
    } catch (err: unknown) {
      setFetchError(err instanceof Error ? err.message : 'Erreur lors du chargement des événements');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!publicRoute && isAdminRoute && isAuthenticated) {
      loadEvents();
    }
  }, [publicRoute, isAdminRoute, isAuthenticated]);

  const handleCreated = (newEvent: EventModel) => {
    setEvents([newEvent, ...events]);
    setSelectedEvent(newEvent);
    setActiveTab('calibrate');
    setNotification(
      `L'événement « ${newEvent.title} » a été créé avec succès ! Vous pouvez maintenant calibrer son plan.`
    );
    setTimeout(() => setNotification(null), 6000);
  };

  const handleConfigurePlan = (event: EventModel) => {
    setSelectedEvent(event);
    setActiveTab('calibrate');
  };

  const handleOpenEditor = (event: EventModel) => {
    setSelectedEvent(event);
    setActiveTab('editor');
  };

  const handleOpenInscriptions = (event: EventModel) => {
    setSelectedEvent(event);
    setActiveTab('inscriptions');
    window.history.pushState({}, '', `/admin/e/${encodeURIComponent(event.id)}/inscriptions`);
  };

  const handleSavedCalibration = (updatedEvent: EventModel) => {
    setEvents(events.map((e) => (e.id === updatedEvent.id ? updatedEvent : e)));
    setSelectedEvent(updatedEvent);
    setNotification(`Le plan de l'événement « ${updatedEvent.title} » a été calibré avec succès !`);
    setTimeout(() => setNotification(null), 6000);
  };

  const handleEditSettings = (event: EventModel) => {
    setSelectedEvent(event);
    setActiveTab('settings');
  };

  const handleSavedSettings = (updatedEvent: EventModel) => {
    setEvents(events.map((e) => (e.id === updatedEvent.id ? updatedEvent : e)));
    setSelectedEvent(updatedEvent);
    setNotification(`Les paramètres de « ${updatedEvent.title} » ont été mis à jour avec succès !`);
    setTimeout(() => setNotification(null), 6000);
  };

  if (publicRoute) {
    if (publicRoute.view === 'cancellation' && publicRoute.orderId) {
      return (
        <CancellationPage
          slug={publicRoute.slug}
          orderId={publicRoute.orderId}
          onNavigateToMap={() => navigateToMap(publicRoute.slug)}
          onNavigateToConfirmation={(token) =>
            navigateToConfirmation(publicRoute.slug, publicRoute.orderId!, token)
          }
          onNavigateHome={navigateHome}
        />
      );
    }
    if (publicRoute.view === 'confirmation' && publicRoute.orderId) {
      return (
        <ConfirmationPage
          slug={publicRoute.slug}
          orderId={publicRoute.orderId}
          onNavigateToMap={() => navigateToMap(publicRoute.slug)}
          onNavigateHome={navigateHome}
          onNavigateToCancellation={(orderId, token) =>
            navigateToCancellation(publicRoute.slug, orderId, token)
          }
        />
      );
    }
    if (publicRoute.view === 'reservation') {
      return (
        <ReservationPage
          slug={publicRoute.slug}
          onNavigateToMap={() => navigateToMap(publicRoute.slug)}
          onNavigateHome={navigateHome}
          onNavigateToConfirmation={navigateToConfirmation}
        />
      );
    }
    if (publicRoute.view === 'showcase') {
      return (
        <EventShowcasePage
          slug={publicRoute.slug}
          onNavigateToMap={() => navigateToMap(publicRoute.slug)}
          onNavigateToReservation={() => navigateToReservation(publicRoute.slug)}
          onNavigateHome={navigateHome}
        />
      );
    }
    return (
      <PublicEventPage
        slug={publicRoute.slug}
        onNavigateHome={navigateHome}
        onNavigateToShowcase={() => navigateToPublic(publicRoute.slug)}
        onNavigateToReservation={() => navigateToReservation(publicRoute.slug)}
      />
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center space-y-3">
          <Loader2 className="w-8 h-8 text-emerald-600 animate-spin" />
          <p className="text-sm font-medium text-gray-500">Chargement de votre session...</p>
        </div>
      </div>
    );
  }

  if (isLoginRoute) {
    if (isAuthenticated) {
      window.history.pushState({}, '', '/admin');
      setIsLoginRoute(false);
      setIsAdminRoute(true);
      setActiveTab('list');
    } else {
      return (
        <LoginPage
          onSuccess={(redirect) => {
            const dest = redirect || '/admin';
            window.history.pushState({}, '', dest);
            setIsLoginRoute(false);
            if (dest.startsWith('/admin/users')) {
              setIsUsersRoute(true);
              setIsAdminRoute(true);
              setActiveTab('users');
            } else {
              setIsAdminRoute(true);
              setActiveTab('list');
            }
          }}
          onNavigateHome={navigateHome}
        />
      );
    }
  }

  if (isAdminRoute) {
    if (!isAuthenticated) {
      return (
        <LoginPage
          onSuccess={(redirect) => {
            const dest = redirect || '/admin';
            window.history.pushState({}, '', dest);
            setIsLoginRoute(false);
            if (dest.startsWith('/admin/users')) {
              setIsUsersRoute(true);
              setIsAdminRoute(true);
              setActiveTab('users');
            } else {
              setIsAdminRoute(true);
              setActiveTab('list');
            }
          }}
          onNavigateHome={navigateHome}
        />
      );
    }

    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        {/* Top Navigation */}
        <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <button
              type="button"
              onClick={navigateHome}
              className="flex items-center space-x-3 cursor-pointer group text-left focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 rounded-xl"
              title="Retourner au portail public d'accueil"
              aria-label="Retourner au portail public d'accueil"
            >
              <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center font-bold text-lg shadow-sm group-hover:bg-emerald-700 transition">
                <Map className="w-5 h-5" />
              </div>
              <div>
                <span className="block font-extrabold text-gray-900 text-lg leading-tight group-hover:text-emerald-700 transition">
                  GVG
                </span>
                <p className="text-xs text-gray-500 font-medium">Gestion de Vide-Greniers</p>
              </div>
            </button>

            <div className="flex items-center space-x-3">
              <button
                type="button"
                onClick={navigateHome}
                className="px-3 py-2 rounded-lg text-sm font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 transition flex items-center gap-1.5 shadow-sm"
                title="Consulter le portail public d'accueil"
              >
                <Globe className="w-4 h-4 text-emerald-600" />
                <span className="hidden sm:inline">Portail Public</span>
              </button>

              <button
                onClick={() => {
                  setActiveTab('list');
                  window.history.pushState({}, '', '/admin');
                  setIsUsersRoute(false);
                }}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition flex items-center gap-2 ${
                  activeTab === 'list'
                    ? 'bg-gray-100 text-gray-900'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <ListFilter className="w-4 h-4" />
                <span>Événements ({events.length})</span>
              </button>

            {user?.role === 'super_admin' && (
              <button
                onClick={() => {
                  setActiveTab('users');
                  window.history.pushState({}, '', '/admin/users');
                  setIsUsersRoute(true);
                }}
                className={`px-4 py-2 rounded-lg text-sm font-semibold transition flex items-center gap-2 ${
                  activeTab === 'users'
                    ? 'bg-purple-100 text-purple-900'
                    : 'text-purple-700 hover:bg-purple-50'
                }`}
              >
                <ShieldCheck className="w-4 h-4 text-purple-600" />
                <span>Utilisateurs</span>
              </button>
            )}

            {activeTab === 'calibrate' && selectedEvent && (
              <div className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1.5">
                <Map className="w-3.5 h-3.5 text-emerald-600" />
                <span className="truncate max-w-[160px]">{selectedEvent.title} (Plan)</span>
              </div>
            )}

            {activeTab === 'editor' && selectedEvent && (
              <div className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1.5">
                <PenTool className="w-3.5 h-3.5 text-emerald-600" />
                <span className="truncate max-w-[160px]">{selectedEvent.title} (Stands)</span>
              </div>
            )}

            {activeTab === 'inscriptions' && selectedEvent && (
              <div className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-800 border border-indigo-200 flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-indigo-600" />
                <span className="truncate max-w-[160px]">{selectedEvent.title} (Inscriptions)</span>
              </div>
            )}

            {activeTab === 'settings' && selectedEvent && (
              <div className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1.5">
                <Settings className="w-3.5 h-3.5 text-emerald-600" />
                <span className="truncate max-w-[160px]">{selectedEvent.title} (Paramètres)</span>
              </div>
            )}

            <button
              onClick={() => {
                setActiveTab('create');
                setIsUsersRoute(false);
              }}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition flex items-center gap-2 shadow-sm ${
                activeTab === 'create'
                  ? 'bg-emerald-700 text-white'
                  : 'bg-emerald-600 hover:bg-emerald-700 text-white'
              }`}
            >
              <PlusCircle className="w-4 h-4" />
              <span>Nouvel Événement</span>
            </button>

            <AdminHeader
              onLogout={() => {
                window.history.pushState({}, '', '/login');
                setIsLoginRoute(true);
              }}
              onNavigateUsers={() => {
                setActiveTab('users');
                window.history.pushState({}, '', '/admin/users');
                setIsUsersRoute(true);
              }}
            />
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {fetchError && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-xl flex items-center justify-between shadow-sm">
            <div className="flex items-center space-x-3">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
              <p className="text-sm font-medium">{fetchError}</p>
            </div>
            <button
              onClick={loadEvents}
              className="text-xs text-red-700 hover:underline font-semibold"
            >
              Réessayer
            </button>
          </div>
        )}

        {notification && (
          <div className="mb-6 bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3 rounded-xl flex items-center justify-between shadow-sm animate-fade-in">
            <div className="flex items-center space-x-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
              <p className="text-sm font-medium">{notification}</p>
            </div>
            <button
              onClick={() => setNotification(null)}
              className="text-xs text-emerald-700 hover:underline font-semibold"
            >
              Fermer
            </button>
          </div>
        )}

        {activeTab === 'users' ? (
          user?.role === 'super_admin' ? (
            <div className="max-w-7xl mx-auto">
              <AdminUsersPage
                onBack={() => {
                  setActiveTab('list');
                  window.history.pushState({}, '', '/admin');
                  setIsUsersRoute(false);
                }}
              />
            </div>
          ) : (
            <div className="bg-red-50 border border-red-200 text-red-800 p-8 rounded-2xl text-center max-w-lg mx-auto my-12 shadow-sm">
              <ShieldCheck className="w-12 h-12 text-red-500 mx-auto mb-3" />
              <h3 className="text-lg font-bold">Accès refusé</h3>
              <p className="text-sm text-red-600 mt-1">
                Seuls les super-administrateurs de la plateforme peuvent accéder à la console de gestion des utilisateurs.
              </p>
              <button
                type="button"
                onClick={() => {
                  setActiveTab('list');
                  window.history.pushState({}, '', '/admin');
                  setIsUsersRoute(false);
                }}
                className="mt-5 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl text-sm font-semibold transition"
              >
                Retour aux événements
              </button>
            </div>
          )
        ) : activeTab === 'create' ? (
          <div className="max-w-3xl mx-auto">
            <EventForm onSuccess={handleCreated} />
          </div>
        ) : activeTab === 'calibrate' && selectedEvent ? (
          <div className="max-w-6xl mx-auto">
            <MapCalibration
              event={selectedEvent}
              onBack={() => setActiveTab('list')}
              onSaved={handleSavedCalibration}
              onProceedToEditor={handleOpenEditor}
            />
          </div>
        ) : activeTab === 'editor' && selectedEvent ? (
          <div className="max-w-7xl mx-auto">
            <SpotEditor
              event={selectedEvent}
              onBack={() => setActiveTab('list')}
              onNavigateToCalibration={() => setActiveTab('calibrate')}
            />
          </div>
        ) : activeTab === 'inscriptions' && selectedEvent ? (
          <div className="max-w-7xl mx-auto">
            <RegistrationsPage
              event={selectedEvent}
              onBack={() => {
                setActiveTab('list');
                window.history.pushState({}, '', '/admin');
              }}
              onOpenEditor={() => handleOpenEditor(selectedEvent)}
            />
          </div>
        ) : activeTab === 'settings' && selectedEvent ? (
          <div className="max-w-6xl mx-auto">
            <EventSettingsPage
              event={selectedEvent}
              onBack={() => setActiveTab('list')}
              onSaved={handleSavedSettings}
              onViewPublic={navigateToPublic}
            />
          </div>
        ) : (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-900">Tableau de bord Organisateur</h2>
                <p className="text-sm text-gray-500 mt-0.5">
                  Consultez et préparez les plans de vos vide-greniers et brocantes.
                </p>
              </div>

              <button
                onClick={loadEvents}
                disabled={loading}
                className="p-2 text-gray-500 hover:text-gray-700 rounded-lg hover:bg-gray-100 transition"
                title="Actualiser la liste"
              >
                <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>

            {loading && events.length === 0 ? (
              <div className="py-20 text-center text-gray-500">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-3 text-emerald-600" />
                <p className="text-sm">Chargement des événements...</p>
              </div>
            ) : events.length === 0 ? (
              <div className="bg-white rounded-2xl border-2 border-dashed border-gray-200 p-12 text-center max-w-md mx-auto my-12">
                <div className="w-16 h-16 bg-emerald-50 text-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Map className="w-8 h-8" />
                </div>
                <h3 className="text-lg font-bold text-gray-900">Aucun événement configuré</h3>
                <p className="text-sm text-gray-500 mt-2">
                  Créez votre premier vide-grenier pour commencer à configurer les horaires et
                  tracer les emplacements sur le plan.
                </p>
                <button
                  onClick={() => setActiveTab('create')}
                  className="mt-6 inline-flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg shadow-sm transition"
                >
                  <PlusCircle className="w-4 h-4" />
                  <span>Créer mon premier vide-grenier</span>
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {events.map((event) => (
                  <EventCard
                    key={event.id}
                    event={event}
                    onConfigurePlan={handleConfigurePlan}
                    onOpenEditor={handleOpenEditor}
                    onViewPublic={navigateToPublic}
                    onOpenInscriptions={handleOpenInscriptions}
                    onEditSettings={handleEditSettings}
                    onDelete={
                      user?.role === 'super_admin' ? (evt) => setEventToDelete(evt) : undefined
                    }
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      <DeleteEventModal
        event={eventToDelete}
        isOpen={Boolean(eventToDelete)}
        onClose={() => setEventToDelete(null)}
        onSuccess={() => {
          if (eventToDelete) {
            setNotification(`L'événement « ${eventToDelete.title} » a été supprimé avec succès.`);
            setEvents(events.filter((e) => e.id !== eventToDelete.id));
          }
          setEventToDelete(null);
        }}
      />

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-gray-400">
          GVG &copy; 2026 &mdash; Plateforme libre et open-source de gestion de vide-greniers et
          brocantes.
        </div>
      </footer>
    </div>
  );
  }

  return (
    <HomePage
      onViewEvent={navigateToPublic}
      onReserveEvent={navigateToReservation}
      onNavigateAdmin={navigateToAdmin}
      onNavigateLogin={navigateToLogin}
    />
  );
};

export const App: React.FC = () => {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
};

export default App;
