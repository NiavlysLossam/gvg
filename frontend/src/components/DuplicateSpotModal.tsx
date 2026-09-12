import React, { useState, useEffect, useMemo } from 'react';
import { Copy, X, AlertCircle, Sparkles, Check } from 'lucide-react';
import { SpotFeature, SpotCreateInput, DuplicateDirection, GeoJSONPolygon } from '../types/spot';

interface DuplicateSpotModalProps {
  isOpen: boolean;
  sourceSpot: SpotFeature | null;
  eventPricePerMeterCents: number;
  onClose: () => void;
  onDuplicate: (spots: SpotCreateInput[]) => Promise<void>;
  isDuplicating: boolean;
}

export function parseLabelPrefixAndNumber(label: string): {
  prefix: string;
  startNum: number;
  padding: number;
} {
  const match = label.match(/^(.*?)(\d+)$/);
  if (match) {
    const prefix = match[1];
    const numStr = match[2];
    const num = parseInt(numStr, 10);
    return {
      prefix: prefix,
      startNum: num + 1,
      padding: numStr.length >= 2 ? numStr.length : 2,
    };
  }
  return {
    prefix: 'Allée A - ',
    startNum: 1,
    padding: 2,
  };
}

export const DuplicateSpotModal: React.FC<DuplicateSpotModalProps> = ({
  isOpen,
  sourceSpot,
  eventPricePerMeterCents,
  onClose,
  onDuplicate,
  isDuplicating,
}) => {
  const [count, setCount] = useState<number>(10);
  const [direction, setDirection] = useState<DuplicateDirection>('stand_axis_right');
  const [spacing, setSpacing] = useState<number>(0.0);
  const [prefix, setPrefix] = useState<string>('Allée A - ');
  const [startNumber, setStartNumber] = useState<number>(1);
  const [zeroPadding, setZeroPadding] = useState<number>(2);
  const [error, setError] = useState<string | null>(null);

  // Initialize defaults from source spot when modal opens
  useEffect(() => {
    if (isOpen && sourceSpot) {
      const parsed = parseLabelPrefixAndNumber(sourceSpot.properties.label);
      setPrefix(parsed.prefix);
      setStartNumber(parsed.startNum);
      setZeroPadding(parsed.padding);
      setCount(10);
      setSpacing(0.0);
      setDirection('stand_axis_right');
      setError(null);
    }
  }, [isOpen, sourceSpot]);

  // Preview generated labels
  const previewLabels = useMemo(() => {
    const labels: string[] = [];
    const maxPreview = Math.min(count, 8);
    for (let i = 0; i < maxPreview; i++) {
      const num = startNumber + i;
      const numStr = zeroPadding > 1 ? String(num).padStart(zeroPadding, '0') : String(num);
      labels.push(`${prefix}${numStr}`);
    }
    return labels;
  }, [prefix, startNumber, zeroPadding, count]);

  if (!isOpen || !sourceSpot) return null;

  const linearMeters = sourceSpot.properties.linear_meters;
  const priceCents =
    sourceSpot.properties.price_cents ?? Math.round(linearMeters * eventPricePerMeterCents);
  const priceEuros = (priceCents / 100).toFixed(2);

  // Calculate step vector in coordinate space
  const calculateStepVector = (ring: number[][]): [number, number] => {
    const p0 = ring[0];
    const p1 = ring[1] || ring[0];
    const p3 = ring[3] || ring[ring.length - 2] || ring[0];

    // Primary axis u: from p0 to p1
    const ux = p1[0] - p0[0];
    const uy = p1[1] - p0[1];
    const lenU = Math.sqrt(ux * ux + uy * uy) || 1e-9;
    const unitUx = ux / lenU;
    const unitUy = uy / lenU;

    // Secondary axis v: from p0 to p3
    const vx = p3[0] - p0[0];
    const vy = p3[1] - p0[1];
    const lenV = Math.sqrt(vx * vx + vy * vy) || 1e-9;
    const unitVx = vx / lenV;
    const unitVy = vy / lenV;

    // Meter scale in coordinate units (1m = lenU / linearMeters)
    const meterScale = linearMeters > 0 ? lenU / linearMeters : lenU;
    const extraSpacingUnits = spacing * meterScale;

    // Bounding box for cardinal offsets
    const xs = ring.map((p) => p[0]);
    const ys = ring.map((p) => p[1]);
    const bboxW = Math.max(...xs) - Math.min(...xs);
    const bboxH = Math.max(...ys) - Math.min(...ys);

    switch (direction) {
      case 'stand_axis_right':
        return [ux + extraSpacingUnits * unitUx, uy + extraSpacingUnits * unitUy];
      case 'stand_axis_left':
        return [-(ux + extraSpacingUnits * unitUx), -(uy + extraSpacingUnits * unitUy)];
      case 'stand_axis_front':
        return [vx + extraSpacingUnits * unitVx, vy + extraSpacingUnits * unitVy];
      case 'stand_axis_back':
        return [-(vx + extraSpacingUnits * unitVx), -(vy + extraSpacingUnits * unitVy)];
      case 'cardinal_east':
        return [bboxW + extraSpacingUnits, 0];
      case 'cardinal_west':
        return [-(bboxW + extraSpacingUnits), 0];
      case 'cardinal_north':
        return [0, bboxH + extraSpacingUnits];
      case 'cardinal_south':
        return [0, -(bboxH + extraSpacingUnits)];
      default:
        return [ux, uy];
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (count < 1) {
      setError('Le nombre de stands à dupliquer doit être au moins de 1.');
      return;
    }
    if (count > 100) {
      setError('Le nombre maximum de stands dupliqués en une fois est de 100.');
      return;
    }

    setError(null);

    const baseCoords = sourceSpot.geometry.coordinates;
    const primaryRing = baseCoords[0];
    if (!primaryRing || primaryRing.length < 4) {
      setError('La géométrie du stand source est invalide.');
      return;
    }

    const [stepX, stepY] = calculateStepVector(primaryRing);
    const spotsToCreate: SpotCreateInput[] = [];

    for (let k = 1; k <= count; k++) {
      const num = startNumber + (k - 1);
      const numStr = zeroPadding > 1 ? String(num).padStart(zeroPadding, '0') : String(num);
      const label = `${prefix}${numStr}`;

      const translatedRings: number[][][] = baseCoords.map((ring) =>
        ring.map(([x, y]) => [x + k * stepX, y + k * stepY])
      );

      const geom: GeoJSONPolygon = {
        type: 'Polygon',
        coordinates: translatedRings,
      };

      spotsToCreate.push({
        label,
        linear_meters: linearMeters,
        price_cents: priceCents,
        geometry: geom,
      });
    }

    try {
      await onDuplicate(spotsToCreate);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la duplication des stands.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 animate-fade-in">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl w-full max-w-xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-emerald-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-emerald-600 text-white flex items-center justify-center shadow-xs">
              <Copy className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-black text-gray-900 text-base">Dupliquer le stand</h3>
              <p className="text-xs text-gray-500">
                Source : <span className="font-semibold text-emerald-700">« {sourceSpot.properties.label} »</span> ({linearMeters}m • {priceEuros} €)
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

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto space-y-5 flex-1">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded-xl flex items-start gap-2.5 text-xs font-medium">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">{error}</div>
            </div>
          )}

          {/* Quick presets for Count */}
          <div>
            <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">
              Nombre de stands à créer (N)
            </label>
            <div className="flex items-center gap-2">
              {[5, 10, 15, 20].map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setCount(preset)}
                  className={`px-3 py-1.5 text-xs font-bold rounded-lg border transition ${
                    count === preset
                      ? 'bg-emerald-600 text-white border-emerald-600 shadow-xs'
                      : 'bg-gray-50 text-gray-700 border-gray-200 hover:bg-gray-100'
                  }`}
                >
                  × {preset}
                </button>
              ))}
              <div className="relative flex-1">
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={count}
                  onChange={(e) => setCount(parseInt(e.target.value, 10) || 1)}
                  className="w-full px-3 py-1.5 text-sm font-bold border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
                />
              </div>
            </div>
          </div>

          {/* Direction & Spacing */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">
                Direction d'alignement
              </label>
              <select
                value={direction}
                onChange={(e) => setDirection(e.target.value as DuplicateDirection)}
                className="w-full px-3 py-2 text-xs font-semibold bg-white border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
              >
                <optgroup label="Axe d'orientation du stand (Recommandé)">
                  <option value="stand_axis_right">Axe stand — Droite / Suivant</option>
                  <option value="stand_axis_left">Axe stand — Gauche / Précédent</option>
                  <option value="stand_axis_front">Axe stand — Avant / Profondeur</option>
                  <option value="stand_axis_back">Axe stand — Arrière</option>
                </optgroup>
                <optgroup label="Axes cardinaux">
                  <option value="cardinal_east">Est (+X)</option>
                  <option value="cardinal_west">Ouest (-X)</option>
                  <option value="cardinal_north">Nord (+Y)</option>
                  <option value="cardinal_south">Sud (-Y)</option>
                </optgroup>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-1.5">
                Espacement entre stands
              </label>
              <div className="relative">
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="10"
                  value={spacing}
                  onChange={(e) => setSpacing(Math.max(0, parseFloat(e.target.value) || 0))}
                  className="w-full px-3 py-2 text-xs font-semibold border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-hidden pr-12"
                />
                <span className="absolute right-3 top-2 text-xs text-gray-400 font-medium">
                  {spacing === 0 ? '0m (bord à bord)' : `${spacing}m`}
                </span>
              </div>
            </div>
          </div>

          {/* Sequential Numbering Config */}
          <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl space-y-3">
            <div className="flex items-center gap-1.5 text-xs font-bold text-gray-800">
              <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
              <span>Numérotation automatique séquentielle</span>
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
                  placeholder="Ex: Allée A - "
                  className="w-full px-2.5 py-1.5 text-xs font-semibold border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-hidden bg-white"
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
                  className="w-full px-2.5 py-1.5 text-xs font-semibold border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-hidden bg-white"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-gray-600 mb-1">
                  Format zéros (padding)
                </label>
                <select
                  value={zeroPadding}
                  onChange={(e) => setZeroPadding(parseInt(e.target.value, 10) || 1)}
                  className="w-full px-2.5 py-1.5 text-xs font-semibold border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:outline-hidden bg-white"
                >
                  <option value={1}>1 chiffre (1, 2, 3)</option>
                  <option value={2}>2 chiffres (01, 02, 03)</option>
                  <option value={3}>3 chiffres (001, 002, 003)</option>
                </select>
              </div>
            </div>

            {/* Label preview badge list */}
            <div className="pt-2 border-t border-gray-200">
              <span className="text-[11px] font-semibold text-gray-500">Aperçu des libellés : </span>
              <div className="flex flex-wrap items-center gap-1.5 mt-1.5">
                {previewLabels.map((lbl, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 text-[11px] font-bold rounded-md bg-emerald-100 text-emerald-800 border border-emerald-200"
                  >
                    {lbl}
                  </span>
                ))}
                {count > previewLabels.length && (
                  <span className="text-[11px] text-gray-400 font-medium">
                    ... +{count - previewLabels.length} suivants
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Summary Box */}
          <div className="px-4 py-3 bg-emerald-50/70 border border-emerald-200 rounded-xl flex items-center justify-between text-xs">
            <span className="text-emerald-900 font-medium">
              Total créé : <b>{count} stands</b> × {linearMeters}m = <b>{(count * linearMeters).toFixed(1)}m</b>
            </span>
            <span className="text-emerald-950 font-black">
              + {((count * priceCents) / 100).toFixed(2)} €
            </span>
          </div>

          {/* Footer Actions */}
          <div className="pt-2 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={isDuplicating}
              className="px-4 py-2 text-xs font-semibold text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={isDuplicating}
              className="px-5 py-2 text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 rounded-lg shadow-sm transition flex items-center gap-2"
            >
              {isDuplicating ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  <span>Création en cours...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>Créer {count} stands</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
