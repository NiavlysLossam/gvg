import React, { useState } from 'react';
import { Copy, X, Calendar, AlertCircle, Info } from 'lucide-react';
import { EventModel, EventDuplicateInput } from '../types/event';
import { duplicateEvent } from '../lib/api';

interface DuplicateEventModalProps {
  event: EventModel;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (duplicatedEvent: EventModel) => void;
}

export const DuplicateEventModal: React.FC<DuplicateEventModalProps> = ({
  event,
  isOpen,
  onClose,
  onSuccess,
}) => {
  // Compute default +1 year dates
  const defaultTitle = `${event.title} - Copie`;
  
  const getPlusOneYearDateTimeLocal = (isoString: string): string => {
    try {
      const d = new Date(isoString);
      d.setFullYear(d.getFullYear() + 1);
      const pad = (n: number) => n.toString().padStart(2, '0');
      const year = d.getFullYear();
      const month = pad(d.getMonth() + 1);
      const day = pad(d.getDate());
      const hours = pad(d.getHours());
      const minutes = pad(d.getMinutes());
      return `${year}-${month}-${day}T${hours}:${minutes}`;
    } catch {
      return '';
    }
  };

  const [title, setTitle] = useState<string>(defaultTitle);
  const [startDate, setStartDate] = useState<string>(getPlusOneYearDateTimeLocal(event.start_date));
  const [endDate, setEndDate] = useState<string>(getPlusOneYearDateTimeLocal(event.end_date));
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError('Veuillez renseigner un nom pour le nouvel événement.');
      return;
    }

    if (startDate && endDate && endDate < startDate) {
      setError('La date de fin doit être postérieure ou égale à la date de début.');
      return;
    }

    setLoading(true);
    setError(null);

    const payload: EventDuplicateInput = {
      title: title.trim(),
      start_date: startDate ? new Date(startDate).toISOString() : undefined,
      end_date: endDate ? new Date(endDate).toISOString() : undefined,
    };

    try {
      const duplicated = await duplicateEvent(event.id, payload);
      onSuccess(duplicated);
      onClose();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Une erreur inattendue est survenue lors de la duplication.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-emerald-50/50">
          <div className="flex items-center gap-2 text-emerald-800">
            <div className="p-2 rounded-lg bg-emerald-100 text-emerald-700">
              <Copy className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-lg text-gray-900 leading-tight">
                Dupliquer l'événement
              </h3>
              <p className="text-xs text-gray-500">
                Créer une nouvelle édition à partir de « {event.title} »
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={loading}
            className="text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4 overflow-y-auto">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Clean Slate Information Banner */}
          <div className="p-4 bg-emerald-50/60 border border-emerald-100 rounded-xl space-y-2 text-xs text-emerald-900">
            <div className="flex items-center gap-1.5 font-bold text-emerald-800">
              <Info className="w-4 h-4 shrink-0 text-emerald-600" />
              <span>Duplication à blanc (Nouvelle édition)</span>
            </div>
            <ul className="space-y-1 list-disc list-inside text-emerald-800/90 pl-1">
              <li>Le nouvel événement sera initialisé au statut <strong>Brouillon</strong>.</li>
              <li>Tous les stands, dimensions et fonds de plan seront copiés.</li>
              <li>Tous les emplacements seront remis au statut <strong>Disponible</strong>.</li>
              <li><strong>Zéro commande ou réservation</strong> ne sera copiée (données exposants vierges).</li>
            </ul>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-1">
              Titre du nouvel événement *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              disabled={loading}
              placeholder="Ex: Vide-Grenier de la Mairie 2027"
              className="w-full px-3.5 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 text-sm"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-gray-500" />
                <span>Date et heure de début</span>
              </label>
              <input
                type="datetime-local"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                disabled={loading}
                className="w-full px-3.5 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-1 flex items-center gap-1">
                <Calendar className="w-3.5 h-3.5 text-gray-500" />
                <span>Date et heure de fin</span>
              </label>
              <input
                type="datetime-local"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                disabled={loading}
                className="w-full px-3.5 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 text-sm"
              />
            </div>
          </div>

          {/* Modal Actions */}
          <div className="pt-4 border-t border-gray-100 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-100 rounded-lg transition"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-bold rounded-lg shadow-sm transition disabled:opacity-50"
            >
              {loading ? (
                <span>Duplication en cours...</span>
              ) : (
                <>
                  <Copy className="w-4 h-4" />
                  <span>Confirmer la duplication</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
