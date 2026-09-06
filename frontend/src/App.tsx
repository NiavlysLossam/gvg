import React, { useState, useEffect } from 'react';
import { PlusCircle, ListFilter, Map, CheckCircle2, RefreshCw, AlertCircle } from 'lucide-react';
import { EventModel } from './types/event';
import { fetchEvents } from './lib/api';
import { EventForm } from './components/EventForm';
import { EventCard } from './components/EventCard';
import { MapCalibration } from './components/MapCalibration';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'list' | 'create' | 'calibrate'>('list');
  const [selectedEvent, setSelectedEvent] = useState<EventModel | null>(null);
  const [events, setEvents] = useState<EventModel[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [notification, setNotification] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const loadEvents = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const data = await fetchEvents();
      setEvents(data.items);
    } catch (err: unknown) {
      setFetchError(err instanceof Error ? err.message : 'Erreur lors du chargement des événements');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadEvents();
  }, []);

  const handleCreated = (newEvent: EventModel) => {
    setEvents([newEvent, ...events]);
    setSelectedEvent(newEvent);
    setActiveTab('calibrate');
    setNotification(`L'événement « ${newEvent.title} » a été créé avec succès ! Vous pouvez maintenant calibrer son plan.`);
    setTimeout(() => setNotification(null), 6000);
  };

  const handleConfigurePlan = (event: EventModel) => {
    setSelectedEvent(event);
    setActiveTab('calibrate');
  };

  const handleSavedCalibration = (updatedEvent: EventModel) => {
    setEvents(events.map((e) => (e.id === updatedEvent.id ? updatedEvent : e)));
    setSelectedEvent(updatedEvent);
    setNotification(`Le plan de l'événement « ${updatedEvent.title} » a été calibré avec succès !`);
    setTimeout(() => setNotification(null), 6000);
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Top Navigation */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center font-bold text-lg shadow-sm">
              <Map className="w-5 h-5" />
            </div>
            <div>
              <h1 className="font-extrabold text-gray-900 text-lg leading-tight">GVG</h1>
              <p className="text-xs text-gray-500 font-medium">Gestion de Vide-Greniers</p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => setActiveTab('list')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition flex items-center gap-2 ${
                activeTab === 'list'
                  ? 'bg-gray-100 text-gray-900'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <ListFilter className="w-4 h-4" />
              <span>Événements ({events.length})</span>
            </button>

            {activeTab === 'calibrate' && selectedEvent && (
              <div className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1.5">
                <Map className="w-3.5 h-3.5 text-emerald-600" />
                <span className="truncate max-w-[160px]">{selectedEvent.title}</span>
              </div>
            )}

            <button
              onClick={() => setActiveTab('create')}
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition flex items-center gap-2 shadow-sm ${
                activeTab === 'create'
                  ? 'bg-emerald-700 text-white'
                  : 'bg-emerald-600 hover:bg-emerald-700 text-white'
              }`}
            >
              <PlusCircle className="w-4 h-4" />
              <span>Nouvel Événement</span>
            </button>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {fetchError && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-xl flex items-center justify-between shadow-xs">
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
          <div className="mb-6 bg-emerald-50 border border-emerald-200 text-emerald-800 px-4 py-3 rounded-xl flex items-center justify-between shadow-xs animate-fade-in">
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

        {activeTab === 'create' ? (
          <div className="max-w-3xl mx-auto">
            <EventForm onSuccess={handleCreated} />
          </div>
        ) : activeTab === 'calibrate' && selectedEvent ? (
          <div className="max-w-6xl mx-auto">
            <MapCalibration
              event={selectedEvent}
              onBack={() => setActiveTab('list')}
              onSaved={handleSavedCalibration}
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
                  Créez votre premier vide-grenier pour commencer à configurer les horaires et tracer les emplacements sur le plan.
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
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-6 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-gray-400">
          GVG &copy; 2026 &mdash; Plateforme libre et open-source de gestion de vide-greniers et brocantes.
        </div>
      </footer>
    </div>
  );
};

export default App;

