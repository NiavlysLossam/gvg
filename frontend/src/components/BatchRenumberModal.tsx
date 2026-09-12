import React, { useState, useEffect, useMemo } from 'react';
import { Hash, X, AlertCircle, Sparkles, Check, ArrowRight } from 'lucide-react';
import { SpotFeature, SpotBatchRenumberInput } from '../types/spot';

interface BatchRenumberModalProps {
  isOpen: boolean;
  selectedSpots: SpotFeature[];
  onClose: () => void;
  onRenumber: (input: SpotBatchRenumberInput) => Promise<void>;
  isRenumbering: boolean;
}

export const BatchRenumberModal: React.FC<BatchRenumberModalProps> = ({
  isOpen,
  selectedSpots,
  onClose,
  onRenumber,
  isRenumbering,
}) => {
  const [prefix, setPrefix] = useState<string>('Allée B - ');
  const [startNumber, setStartNumber] = useState<number>(1);
  const [zeroPadding, setZeroPadding] = useState<number>(2);
  const [error, setError] = useState<string | null>(null);

  // Reset/initialize when modal opens
  useEffect(() => {
    if (isOpen && selectedSpots.length > 0) {
      setError(null);
      // Try detecting prefix from first selected spot
      const firstLabel = selectedSpots[0].properties.label;
      const match = firstLabel.match(/^(.*?)(\d+)$/);
      if (match && match[1]) {
        setPrefix(match[1]);
      } else {
        setPrefix('Allée B - ');
      }
      setStartNumber(1);
      setZeroPadding(2);
    }
  }, [isOpen, selectedSpots]);

  // Preview generated label mappings
  const previewItems = useMemo(() => {
    return selectedSpots.map((spot, idx) => {
      const num = startNumber + idx;
      const numStr = zeroPadding > 1 ? String(num).padStart(zeroPadding, '0') : String(num);
      return {
        spot,
        oldLabel: spot.properties.label,
        newLabel: `${prefix}${numStr}`,
      };
    });
  }, [selectedSpots, prefix, startNumber, zeroPadding]);

  if (!isOpen || selectedSpots.length === 0) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const spotIds = selectedSpots.map((s) => s.id);
    try {
      await onRenumber({
        spot_ids: spotIds,
        prefix,
        start_number: startNumber,
        zero_padding: zeroPadding,
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la renumérotation des stands.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 animate-fade-in">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-indigo-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-xs">
              <Hash className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-black text-gray-900 text-base">Renumérotation groupée</h3>
              <p className="text-xs text-gray-500">
                {selectedSpots.length} {selectedSpots.length === 1 ? 'stand sélectionné' : 'stands sélectionnés'}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 p-1.5 hover:bg-gray-100 rounded-lg transition"
            title="Fermer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Form */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-5 flex-1">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-xl flex items-start gap-2.5 text-xs font-medium">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">{error}</div>
            </div>
          )}

          {/* Settings Grid */}
          <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl space-y-3">
            <div className="flex items-center gap-1.5 text-xs font-bold text-gray-800">
              <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
              <span>Modèle de séquence</span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                  Préfixe d'allée
                </label>
                <input
                  type="text"
                  value={prefix}
                  onChange={(e) => setPrefix(e.target.value)}
                  placeholder="Ex: Allée B - "
                  className="w-full px-2.5 py-1.5 text-xs font-semibold border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-hidden bg-white"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                  Premier numéro
                </label>
                <input
                  type="number"
                  min={0}
                  value={startNumber}
                  onChange={(e) => setStartNumber(parseInt(e.target.value, 10) || 0)}
                  className="w-full px-2.5 py-1.5 text-xs font-semibold border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-hidden bg-white"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                  Format zéros (padding)
                </label>
                <select
                  value={zeroPadding}
                  onChange={(e) => setZeroPadding(parseInt(e.target.value, 10) || 1)}
                  className="w-full px-2.5 py-1.5 text-xs font-semibold border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-hidden bg-white"
                >
                  <option value={1}>1 chiffre (1, 2, 3)</option>
                  <option value={2}>2 chiffres (01, 02, 03)</option>
                  <option value={3}>3 chiffres (001, 002, 003)</option>
                </select>
              </div>
            </div>
          </div>

          {/* Preview Mapping List */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-gray-700 uppercase tracking-wider">
                Aperçu des modifications
              </span>
              <span className="text-[11px] text-gray-400">
                Ordre de sélection
              </span>
            </div>

            <div className="border border-gray-200 rounded-xl divide-y divide-gray-100 max-h-48 overflow-y-auto bg-white shadow-xs">
              {previewItems.map((item, idx) => (
                <div
                  key={item.spot.id}
                  className="px-3.5 py-2 flex items-center justify-between text-xs hover:bg-gray-50 transition"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-gray-400 font-mono text-[11px] w-5">#{idx + 1}</span>
                    <span className="text-gray-500 line-through font-medium">{item.oldLabel}</span>
                  </div>
                  <ArrowRight className="w-3.5 h-3.5 text-gray-400" />
                  <span className="font-bold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                    {item.newLabel}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Footer Actions */}
          <div className="pt-2 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isRenumbering}
              className="px-4 py-2 text-xs font-semibold text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={isRenumbering}
              className="px-5 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-lg shadow-sm transition flex items-center gap-2"
            >
              {isRenumbering ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  <span>Renumérotation...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>Renuméroter {selectedSpots.length} stands</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

