import React, { useState, useEffect } from 'react';
import { X, Tag, Ruler, Euro, Trash2, Check, AlertCircle, Sparkles, Copy } from 'lucide-react';
import { SpotFeature } from '../types/spot';

export interface SpotFormData {
  label: string;
  linear_meters: number;
  price_cents: number;
  isPriceOverridden: boolean;
}

interface SpotPropertyDrawerProps {
  isOpen: boolean;
  isNew: boolean;
  spot: SpotFeature | null;
  defaultLabel?: string;
  eventPricePerMeterCents: number;
  onClose: () => void;
  onSave: (data: SpotFormData) => Promise<void>;
  onDelete?: (spotId: string) => Promise<void>;
  onOpenDuplicateModal?: (spot: SpotFeature) => void;
  isSaving: boolean;
  isDeleting: boolean;
}

export const SpotPropertyDrawer: React.FC<SpotPropertyDrawerProps> = ({
  isOpen,
  isNew,
  spot,
  defaultLabel = 'Stand 1',
  eventPricePerMeterCents,
  onClose,
  onSave,
  onDelete,
  onOpenDuplicateModal,
  isSaving,
  isDeleting,
}) => {
  const [label, setLabel] = useState<string>('');
  const [linearMeters, setLinearMeters] = useState<number>(2.0);
  const [manualPriceEuros, setManualPriceEuros] = useState<string>('');
  const [isPriceOverridden, setIsPriceOverridden] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState<boolean>(false);

  // Sync state when spot or open state changes
  useEffect(() => {
    if (isOpen) {
      setError(null);
      setShowDeleteConfirm(false);
      if (spot) {
        setLabel(spot.properties.label);
        setLinearMeters(spot.properties.linear_meters);
        const autoPriceCents = Math.round(spot.properties.linear_meters * eventPricePerMeterCents);
        if (spot.properties.price_cents !== autoPriceCents) {
          setIsPriceOverridden(true);
          setManualPriceEuros((spot.properties.price_cents / 100).toFixed(2));
        } else {
          setIsPriceOverridden(false);
          setManualPriceEuros('');
        }
      } else {
        setLabel(defaultLabel);
        setLinearMeters(2.0);
        setIsPriceOverridden(false);
        setManualPriceEuros('');
      }
    }
  }, [isOpen, spot, defaultLabel, eventPricePerMeterCents]);

  if (!isOpen) return null;

  const calculatedAutoPriceCents = Math.round(linearMeters * eventPricePerMeterCents);
  const currentPriceEuros = isPriceOverridden
    ? parseFloat(manualPriceEuros) || 0
    : calculatedAutoPriceCents / 100;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedLabel = label.trim();
    if (!trimmedLabel) {
      setError('Le numéro ou libellé du stand est requis.');
      return;
    }

    if (isNaN(linearMeters) || linearMeters <= 0) {
      setError('Le métrage doit être supérieur à 0');
      return;
    }

    let finalPriceCents = calculatedAutoPriceCents;
    if (isPriceOverridden) {
      const parsedManual = parseFloat(manualPriceEuros);
      if (isNaN(parsedManual) || parsedManual < 0) {
        setError('Le tarif personnalisé doit être un montant positif ou nul.');
        return;
      }
      finalPriceCents = Math.round(parsedManual * 100);
    }

    try {
      await onSave({
        label: trimmedLabel,
        linear_meters: linearMeters,
        price_cents: finalPriceCents,
        isPriceOverridden,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erreur lors de l'enregistrement");
    }
  };

  const handleDelete = async () => {
    if (!spot || !onDelete) return;
    try {
      await onDelete(spot.id);
      setShowDeleteConfirm(false);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la suppression');
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-96 bg-white shadow-2xl border-l border-gray-200 flex flex-col animate-slide-in">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between bg-gray-50">
        <div>
          <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
            <Tag className="w-5 h-5 text-emerald-600" />
            <span>{isNew ? 'Nouveau stand' : `Stand ${spot?.properties.label || ''}`}</span>
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">
            {isNew
              ? 'Définissez le libellé et le métrage linéaire'
              : 'Modifier les caractéristiques du stand'}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-200 transition"
          title="Fermer"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Form Content */}
      <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-6">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl flex items-start gap-2.5 text-sm">
            <AlertCircle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {/* Spot status badge if existing */}
        {!isNew && spot && (
          <div className="flex items-center justify-between bg-gray-50 px-3.5 py-2.5 rounded-lg border border-gray-200 text-xs">
            <span className="text-gray-500 font-medium">Statut actuel :</span>
            <span
              className={`px-2 py-0.5 rounded-full font-semibold ${
                spot.properties.status === 'available'
                  ? 'bg-emerald-100 text-emerald-800'
                  : spot.properties.status === 'reserved'
                  ? 'bg-blue-100 text-blue-800'
                  : spot.properties.status === 'locked'
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-gray-100 text-gray-800'
              }`}
            >
              {spot.properties.status === 'available'
                ? 'Disponible'
                : spot.properties.status === 'reserved'
                ? 'Réservé'
                : spot.properties.status === 'locked'
                ? 'Verrouillé (en cours)'
                : 'Bloqué'}
            </span>
          </div>
        )}

        {/* Label field */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-1.5 flex items-center gap-1.5">
            <Tag className="w-4 h-4 text-gray-500" />
            <span>Numéro / Libellé de l'emplacement</span>
          </label>
          <input
            type="text"
            required
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Ex : Stand 1, A01, Allée B-04"
            className="w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-lg text-sm text-gray-900 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition"
          />
          <p className="text-xs text-gray-400 mt-1">
            Identifiant unique affiché sur le plan et la réservation.
          </p>
        </div>

        {/* Linear meters field */}
        <div>
          <label className="block text-sm font-semibold text-gray-800 mb-1.5 flex items-center gap-1.5">
            <Ruler className="w-4 h-4 text-gray-500" />
            <span>Métrage linéaire (mètres)</span>
          </label>
          <div className="relative">
            <input
              type="number"
              step="0.5"
              min="0.1"
              required
              value={linearMeters}
              onChange={(e) => {
                const val = parseFloat(e.target.value);
                setLinearMeters(isNaN(val) ? 0 : val);
              }}
              className="w-full px-3.5 py-2.5 bg-white border border-gray-300 rounded-lg text-sm text-gray-900 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition pr-12"
            />
            <span className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-sm font-medium text-gray-400 pointer-events-none">
              m
            </span>
          </div>
          {linearMeters <= 0 && (
            <p className="text-xs text-red-600 mt-1 font-medium">Le métrage doit être supérieur à 0</p>
          )}
          <p className="text-xs text-gray-400 mt-1">
            Définit la longueur allouée à l'exposant (ex : 2m, 3m, 4m).
          </p>
        </div>

        {/* Price calculation block */}
        <div className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs text-emerald-800 font-semibold">
              <Euro className="w-4 h-4 text-emerald-600" />
              <span>Tarif calculé</span>
            </div>
            <div className="text-xs text-gray-500 font-medium">
              Base : {(eventPricePerMeterCents / 100).toFixed(2)} €/m
            </div>
          </div>

          <div className="flex items-baseline justify-between pt-1">
            <span className="text-sm font-medium text-gray-700">Prix total stand :</span>
            <span className="text-2xl font-black text-emerald-700">
              {currentPriceEuros.toFixed(2)} €
            </span>
          </div>

          {/* Manual override toggle */}
          <div className="pt-2 border-t border-emerald-200/60">
            <label className="flex items-center gap-2 cursor-pointer text-xs font-medium text-gray-700 select-none">
              <input
                type="checkbox"
                checked={isPriceOverridden}
                onChange={(e) => {
                  const checked = e.target.checked;
                  setIsPriceOverridden(checked);
                  if (checked && !manualPriceEuros) {
                    setManualPriceEuros((calculatedAutoPriceCents / 100).toFixed(2));
                  }
                }}
                className="w-4 h-4 rounded text-emerald-600 focus:ring-emerald-500 border-gray-300"
              />
              <span className="flex items-center gap-1">
                <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                <span>Personnaliser le tarif (emplacement premium / d'angle)</span>
              </span>
            </label>

            {isPriceOverridden && (
              <div className="mt-3 pt-2">
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Montant personnalisé (€)
                </label>
                <div className="relative">
                  <input
                    type="number"
                    step="1"
                    min="0"
                    value={manualPriceEuros}
                    onChange={(e) => setManualPriceEuros(e.target.value)}
                    placeholder="Ex : 25.00"
                    className="w-full px-3 py-1.5 bg-white border border-gray-300 rounded-lg text-sm text-gray-900 focus:ring-2 focus:ring-emerald-500 outline-none pr-8"
                  />
                  <span className="absolute inset-y-0 right-0 flex items-center pr-3 text-xs font-medium text-gray-400 pointer-events-none">
                    €
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Duplication action for existing spot */}
        {!isNew && spot && onOpenDuplicateModal && (
          <div className="pt-2">
            <button
              type="button"
              onClick={() => onOpenDuplicateModal(spot)}
              className="w-full flex items-center justify-center gap-2 py-2.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-300 rounded-xl text-xs font-bold transition shadow-xs"
            >
              <Copy className="w-4 h-4 text-emerald-600" />
              <span>Dupliquer ce stand (× N)</span>
            </button>
          </div>
        )}

        {/* Delete confirmation or action button */}
        {!isNew && spot && onDelete && (
          <div className="pt-4 border-t border-gray-200">
            {showDeleteConfirm ? (
              <div className="bg-red-50 border border-red-200 rounded-xl p-3.5 space-y-2">
                <p className="text-xs font-semibold text-red-800">
                  Confirmer la suppression de « {spot.properties.label} » ?
                </p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={isDeleting}
                    onClick={handleDelete}
                    className="flex-1 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold shadow-xs transition"
                  >
                    {isDeleting ? 'Suppression...' : 'Oui, supprimer'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowDeleteConfirm(false)}
                    className="px-3 py-1.5 bg-white border border-gray-300 hover:bg-gray-100 text-gray-700 rounded-lg text-xs font-semibold transition"
                  >
                    Annuler
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(true)}
                className="w-full flex items-center justify-center gap-1.5 py-2 text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg text-xs font-semibold transition"
              >
                <Trash2 className="w-4 h-4" />
                <span>Supprimer cet emplacement</span>
              </button>
            )}
          </div>
        )}
      </form>

      {/* Footer Actions */}
      <div className="p-4 border-t border-gray-200 bg-gray-50 flex items-center gap-3">
        <button
          type="button"
          onClick={onClose}
          className="flex-1 px-4 py-2.5 bg-white border border-gray-300 hover:bg-gray-100 text-gray-700 font-semibold text-sm rounded-lg shadow-xs transition"
        >
          Annuler
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isSaving || linearMeters <= 0}
          className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm rounded-lg shadow-sm transition disabled:opacity-50"
        >
          <Check className="w-4 h-4" />
          <span>{isSaving ? 'Enregistrement...' : 'Enregistrer'}</span>
        </button>
      </div>
    </div>
  );
};

