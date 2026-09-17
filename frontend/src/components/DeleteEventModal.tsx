import React, { useState, useEffect } from 'react';
import { AlertTriangle, Loader2, Trash2, X } from 'lucide-react';
import { EventModel } from '../types/event';
import { deleteEvent } from '../lib/api';

interface DeleteEventModalProps {
  event: EventModel | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const DeleteEventModal: React.FC<DeleteEventModalProps> = ({
  event,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [typedTitle, setTypedTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setTypedTitle('');
      setError(null);
      setLoading(false);
    }
  }, [isOpen, event]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen && !loading) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, loading, onClose]);

  if (!isOpen || !event) return null;

  const isConfirmed = typedTitle.trim() === event.title.trim();

  const handleDelete = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isConfirmed || loading) return;

    setLoading(true);
    setError(null);
    try {
      await deleteEvent(event.id);
      onSuccess();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors de la suppression de l'événement");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-xs flex items-center justify-center p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget && !loading) onClose();
      }}
    >
      <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-red-100 relative animate-in fade-in zoom-in duration-200">
        <button
          type="button"
          onClick={onClose}
          disabled={loading}
          className="absolute top-4 right-4 text-gray-400 hover:text-gray-600 p-1.5 rounded-lg hover:bg-gray-100 transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-start gap-4">
          <div className="p-3 bg-red-100 text-red-600 rounded-xl flex-shrink-0">
            <AlertTriangle className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-gray-900">
              Supprimer définitivement l'événement
            </h3>
            <p className="text-sm text-gray-500 mt-1">
              Cette action est <span className="font-semibold text-red-600">irréversible</span>.
              Toutes les données associées seront définitivement détruites.
            </p>
          </div>
        </div>

        <div className="mt-4 bg-red-50/70 border border-red-200 rounded-xl p-3.5 text-xs text-red-800 space-y-1">
          <p className="font-semibold">Données supprimées en cascade :</p>
          <ul className="list-disc pl-4 space-y-0.5 text-red-700">
            <li>L'ensemble des emplacements / stands dessinés</li>
            <li>Toutes les réservations et commandes d'exposants</li>
            <li>L'historique des emails et attestations</li>
            <li>Le fichier de fond de plan téléversé</li>
          </ul>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 font-medium">
            {error}
          </div>
        )}

        <form onSubmit={handleDelete} className="mt-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-700 mb-1">
              Pour confirmer, veuillez saisir le nom exact de l'événement :
            </label>
            <div className="bg-gray-100 px-3 py-1.5 rounded-lg text-xs font-mono text-gray-800 select-all mb-2 border border-gray-200">
              {event.title}
            </div>
            <input
              type="text"
              required
              value={typedTitle}
              onChange={(e) => setTypedTitle(e.target.value)}
              placeholder="Retapez le titre de l'événement ici"
              className="w-full px-3.5 py-2.5 text-sm border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-red-500 outline-hidden transition"
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-xl transition"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={!isConfirmed || loading}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-red-600 hover:bg-red-700 disabled:bg-gray-300 disabled:cursor-not-allowed rounded-xl shadow-xs transition"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Suppression en cours...</span>
                </>
              ) : (
                <>
                  <Trash2 className="w-4 h-4" />
                  <span>Supprimer définitivement</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

