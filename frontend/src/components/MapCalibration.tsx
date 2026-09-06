import React, { useState, useEffect, useRef, useCallback } from 'react';
import L from 'leaflet';
import {
  MapPin,
  Upload,
  Search,
  Layers,
  Save,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileImage,
  RefreshCw,
  Compass,
  Maximize2
} from 'lucide-react';
import { EventModel, MapType } from '../types/event';
import { updateEvent, uploadBackgroundImage, getImageUrl, ApiError } from '../lib/api';

// Fix Leaflet default marker icons for Vite bundler
import iconRetinaUrl from 'leaflet/dist/images/marker-icon-2x.png';
import iconUrl from 'leaflet/dist/images/marker-icon.png';
import shadowUrl from 'leaflet/dist/images/marker-shadow.png';

// Override default leaflet icon URLs safely
const DefaultIcon = L.icon({
  iconRetinaUrl,
  iconUrl,
  shadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  tooltipAnchor: [16, -28],
  shadowSize: [41, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

// Standard Metropolitan France coordinates
const DEFAULT_FRANCE_LAT = 46.603354;
const DEFAULT_FRANCE_LNG = 1.888334;
const DEFAULT_FRANCE_ZOOM = 6;
const DEFAULT_VENUE_ZOOM = 16;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

interface MapCalibrationProps {
  event: EventModel;
  onBack: () => void;
  onSaved: (updatedEvent: EventModel) => void;
}

export const MapCalibration: React.FC<MapCalibrationProps> = ({
  event,
  onBack,
  onSaved,
}) => {
  const [currentEvent, setCurrentEvent] = useState<EventModel>(event);
  const [mode, setMode] = useState<MapType>(event.map_type || 'geographic');
  const [tileLayerType, setTileLayerType] = useState<'osm' | 'satellite'>('osm');

  // Coordinates & Zoom for geographic mode
  const [lat, setLat] = useState<number>(
    event.center_latitude ?? DEFAULT_FRANCE_LAT
  );
  const [lng, setLng] = useState<number>(
    event.center_longitude ?? DEFAULT_FRANCE_LNG
  );
  const [zoom, setZoom] = useState<number>(
    event.default_zoom ?? (event.center_latitude ? DEFAULT_VENUE_ZOOM : DEFAULT_FRANCE_ZOOM)
  );

  // Address search state
  const [searchQuery, setSearchQuery] = useState<string>(event.location_address || '');
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Upload & Planar state
  const [imageDimensions, setImageDimensions] = useState<{ width: number; height: number } | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);

  // General feedback
  const [saving, setSaving] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Leaflet references
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markerRef = useRef<L.Marker | null>(null);
  const tileLayerRef = useRef<L.TileLayer | null>(null);
  const imageOverlayRef = useRef<L.ImageOverlay | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Geocoding with Nominatim
  const handleGeocode = async (queryToSearch?: string) => {
    const q = (queryToSearch ?? searchQuery).trim();
    if (!q) return;

    setIsSearching(true);
    setSearchError(null);

    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}&limit=1`,
        {
          headers: {
            'Accept-Language': 'fr',
          },
        }
      );

      if (!response.ok) {
        throw new Error('Erreur lors de la recherche cartographique');
      }

      const results = await response.json();
      if (results && results.length > 0) {
        const foundLat = parseFloat(results[0].lat);
        const foundLng = parseFloat(results[0].lon);
        const targetZoom = 16;

        setLat(foundLat);
        setLng(foundLng);
        setZoom(targetZoom);

        if (mapInstanceRef.current && mode === 'geographic') {
          mapInstanceRef.current.flyTo([foundLat, foundLng], targetZoom, {
            duration: 1.2,
          });
          if (markerRef.current) {
            markerRef.current.setLatLng([foundLat, foundLng]);
          }
        }
      } else {
        setSearchError('Aucun résultat trouvé pour cette adresse. Vous pouvez déplacer manuellement la carte.');
      }
    } catch {
      setSearchError('Impossible de joindre le service d’adressage. Positionnez manuellement le repère.');
    } finally {
      setIsSearching(false);
    }
  };

  // Auto-geocode address if no coordinates were ever configured
  useEffect(() => {
    if (
      mode === 'geographic' &&
      event.location_address &&
      (event.center_latitude === null || event.center_latitude === undefined) &&
      (event.center_longitude === null || event.center_longitude === undefined)
    ) {
      handleGeocode(event.location_address);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Initialize and tear down Leaflet map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Clean up previous instance
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
      markerRef.current = null;
      tileLayerRef.current = null;
      imageOverlayRef.current = null;
    }

    if (mode === 'geographic') {
      // 1. Geographic Leaflet setup (EPSG:3857)
      const map = L.map(mapContainerRef.current, {
        center: [lat, lng],
        zoom: zoom,
        zoomControl: true,
      });

      // Layer selection
      const osmUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
      const osmAttr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
      const satUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
      const satAttr = 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP';

      const initialUrl = tileLayerType === 'satellite' ? satUrl : osmUrl;
      const initialAttr = tileLayerType === 'satellite' ? satAttr : osmAttr;

      const tileLayer = L.tileLayer(initialUrl, {
        maxZoom: 19,
        attribution: initialAttr,
      }).addTo(map);
      tileLayerRef.current = tileLayer;

      // Center marker
      const marker = L.marker([lat, lng], {
        draggable: true,
      }).addTo(map);

      marker.bindPopup('<b>Centre de l’événement</b><br />Glissez pour affiner le positionnement');

      marker.on('dragend', () => {
        const pos = marker.getLatLng();
        setLat(pos.lat);
        setLng(pos.lng);
        map.panTo(pos);
      });
      markerRef.current = marker;

      // Update center & zoom on map moves
      map.on('moveend', () => {
        const center = map.getCenter();
        const currentZoom = map.getZoom();
        setLat(center.lat);
        setLng(center.lng);
        setZoom(currentZoom);
        if (markerRef.current) {
          markerRef.current.setLatLng(center);
        }
      });

      mapInstanceRef.current = map;

      // Ensure proper size calculation
      const timer = setTimeout(() => {
        map.invalidateSize();
      }, 100);

      return () => {
        clearTimeout(timer);
        map.remove();
        mapInstanceRef.current = null;
      };
    } else {
      // 2. Planar Mode setup (L.CRS.Simple)
      if (!currentEvent.background_image_url) {
        // No image yet; dropzone UI will be shown, no map needed
        return;
      }

      let active = true;
      const imageUrl = getImageUrl(currentEvent.background_image_url);
      const img = new Image();
      img.src = imageUrl;

      img.onload = () => {
        if (!active || !mapContainerRef.current) return;

        // Cleanup any existing instance
        if (mapInstanceRef.current) {
          mapInstanceRef.current.remove();
          mapInstanceRef.current = null;
        }

        const w = img.naturalWidth;
        const h = img.naturalHeight;
        setImageDimensions({ width: w, height: h });

        const map = L.map(mapContainerRef.current, {
          crs: L.CRS.Simple,
          minZoom: -2,
          maxZoom: 3,
          zoomSnap: 0.25,
          zoomDelta: 0.5,
        });

        const bounds = new L.LatLngBounds([0, 0], [h, w]);
        const overlay = L.imageOverlay(imageUrl, bounds).addTo(map);
        imageOverlayRef.current = overlay;

        map.fitBounds(bounds);
        map.setMaxBounds(bounds.pad(0.2));

        mapInstanceRef.current = map;

        setTimeout(() => {
          if (active && mapInstanceRef.current) {
            mapInstanceRef.current.invalidateSize();
          }
        }, 100);
      };

      img.onerror = () => {
        if (!active) return;
        setUploadError('Erreur de chargement de l’image du plan. Vérifiez le fichier ou téléversez-en un nouveau.');
      };

      return () => {
        active = false;
        if (mapInstanceRef.current) {
          mapInstanceRef.current.remove();
          mapInstanceRef.current = null;
        }
      };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, currentEvent.background_image_url]);

  // Update tile layer when toggling OSM vs Satellite
  const handleToggleTileLayer = (type: 'osm' | 'satellite') => {
    setTileLayerType(type);
    if (!mapInstanceRef.current || mode !== 'geographic') return;

    if (tileLayerRef.current) {
      mapInstanceRef.current.removeLayer(tileLayerRef.current);
    }

    const osmUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
    const osmAttr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
    const satUrl = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
    const satAttr = 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP';

    const url = type === 'satellite' ? satUrl : osmUrl;
    const attr = type === 'satellite' ? satAttr : osmAttr;

    const newLayer = L.tileLayer(url, {
      maxZoom: 19,
      attribution: attr,
    }).addTo(mapInstanceRef.current);

    tileLayerRef.current = newLayer;
  };

  // File upload handler
  const handleFileUpload = async (file: File) => {
    setUploadError(null);

    // Validate mime type
    const validMimes = ['image/png', 'image/jpeg', 'image/webp'];
    if (!validMimes.includes(file.type)) {
      setUploadError('Format non supporté (PNG, JPEG, WebP uniquement)');
      return;
    }

    // Validate size limit (10 MB)
    if (file.size > MAX_FILE_SIZE) {
      setUploadError("L'image dépasse la taille maximale autorisée de 10 Mo");
      return;
    }

    setIsUploading(true);
    try {
      const updated = await uploadBackgroundImage(currentEvent.id, file);
      setCurrentEvent(updated);
      setMode('planar');
      setStatusMessage({
        type: 'success',
        text: 'Image du plan téléversée avec succès !',
      });
      onSaved(updated);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setUploadError(typeof err.detail === 'string' ? err.detail : 'Erreur lors du téléversement');
      } else {
        setUploadError('Erreur de connexion lors du téléversement du fichier');
      }
    } finally {
      setIsUploading(false);
    }
  };

  // Drag & drop handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentEvent.id]);

  // Save calibration
  const handleSaveCalibration = async () => {
    setStatusMessage(null);

    if (mode === 'planar' && !currentEvent.background_image_url) {
      setStatusMessage({
        type: 'error',
        text: 'Veuillez d’abord téléverser une image de plan pour activer le mode intérieur.',
      });
      return;
    }

    setSaving(true);

    try {
      const safeZoom = Math.max(1, Math.min(22, Math.round(zoom)));
      const safeLng = parseFloat((((lng + 180) % 360 + 360) % 360 - 180).toFixed(6));
      const safeLat = parseFloat(Math.max(-90, Math.min(90, lat)).toFixed(6));

      const payload =
        mode === 'geographic'
          ? {
              map_type: 'geographic' as const,
              center_latitude: safeLat,
              center_longitude: safeLng,
              default_zoom: safeZoom,
            }
          : {
              map_type: 'planar' as const,
            };

      const updated = await updateEvent(currentEvent.id, payload);
      setCurrentEvent(updated);
      setStatusMessage({
        type: 'success',
        text: 'Calibrage du plan enregistré avec succès !',
      });
      onSaved(updated);
    } catch (err: unknown) {
      setStatusMessage({
        type: 'error',
        text: err instanceof ApiError ? (typeof err.detail === 'string' ? err.detail : 'Erreur lors de la sauvegarde') : 'Erreur lors de l’enregistrement du calibrage',
      });
    } finally {
      setSaving(false);
    }
  };

  // Reset to current event location / France center
  const handleResetLocation = () => {
    if (mode === 'geographic') {
      const resetLat = event.center_latitude ?? DEFAULT_FRANCE_LAT;
      const resetLng = event.center_longitude ?? DEFAULT_FRANCE_LNG;
      const resetZoom = event.default_zoom ?? (event.center_latitude ? DEFAULT_VENUE_ZOOM : DEFAULT_FRANCE_ZOOM);

      setLat(resetLat);
      setLng(resetLng);
      setZoom(resetZoom);

      if (mapInstanceRef.current) {
        mapInstanceRef.current.setView([resetLat, resetLng], resetZoom);
        if (markerRef.current) {
          markerRef.current.setLatLng([resetLat, resetLng]);
        }
      }
    } else if (mapInstanceRef.current && imageDimensions) {
      const bounds = new L.LatLngBounds([0, 0], [imageDimensions.height, imageDimensions.width]);
      mapInstanceRef.current.fitBounds(bounds);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header & Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 bg-white p-6 rounded-2xl border border-gray-200 shadow-sm">
        <div className="flex items-center space-x-4">
          <button
            type="button"
            onClick={onBack}
            className="p-2 rounded-xl text-gray-500 hover:text-gray-900 hover:bg-gray-100 transition"
            title="Retour aux événements"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-gray-900">
                Calibrage du Plan &mdash; {currentEvent.title}
              </h2>
              <span className="text-xs px-2.5 py-0.5 rounded-full font-medium bg-emerald-100 text-emerald-800">
                Fond de plan
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Configurez le point de vue géographique ou le schéma intérieur avant le tracé vectoriel des emplacements.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onBack}
            className="px-4 py-2 text-sm font-semibold text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition"
          >
            Retour
          </button>
          <button
            type="button"
            onClick={handleSaveCalibration}
            disabled={saving || isUploading}
            className="inline-flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-sm transition disabled:opacity-50"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Enregistrement...</span>
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                <span>Enregistrer le calibrage</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Status Notifications */}
      {statusMessage && (
        <div
          className={`p-4 rounded-xl flex items-center justify-between shadow-sm ${
            statusMessage.type === 'success'
              ? 'bg-emerald-50 border border-emerald-200 text-emerald-800'
              : 'bg-red-50 border border-red-200 text-red-800'
          }`}
        >
          <div className="flex items-center space-x-3">
            {statusMessage.type === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
            )}
            <p className="text-sm font-medium">{statusMessage.text}</p>
          </div>
          <button
            type="button"
            onClick={() => setStatusMessage(null)}
            className="text-xs font-semibold hover:underline"
          >
            Fermer
          </button>
        </div>
      )}

      {/* Mode Selector & Configuration Toolbar */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Mode Switcher */}
          <div className="flex items-center space-x-2 bg-gray-100 p-1.5 rounded-xl self-start md:self-auto">
            <button
              type="button"
              onClick={() => setMode('geographic')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition ${
                mode === 'geographic'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Compass className="w-4 h-4 text-emerald-600" />
              <span>Extérieur (GPS / Satellite)</span>
            </button>
            <button
              type="button"
              onClick={() => setMode('planar')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition ${
                mode === 'planar'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <FileImage className="w-4 h-4 text-indigo-600" />
              <span>Plan de Salle / Intérieur</span>
            </button>
          </div>

          {/* Mode-specific Controls */}
          {mode === 'geographic' ? (
            <div className="flex flex-wrap items-center gap-3">
              {/* Tile Type Switcher */}
              <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden text-xs font-semibold">
                <button
                  type="button"
                  onClick={() => handleToggleTileLayer('osm')}
                  className={`px-3 py-1.5 transition ${
                    tileLayerType === 'osm'
                      ? 'bg-emerald-600 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Rues (OSM)
                </button>
                <button
                  type="button"
                  onClick={() => handleToggleTileLayer('satellite')}
                  className={`px-3 py-1.5 transition ${
                    tileLayerType === 'satellite'
                      ? 'bg-emerald-600 text-white'
                      : 'bg-white text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  Vue Satellite
                </button>
              </div>

              {/* Reset view */}
              <button
                type="button"
                onClick={handleResetLocation}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition"
                title="Recentrer la carte"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Recentrer</span>
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              {currentEvent.background_image_url && (
                <>
                  <button
                    type="button"
                    onClick={handleResetLocation}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition"
                    title="Ajuster le plan aux bords"
                  >
                    <Maximize2 className="w-3.5 h-3.5" />
                    <span>Ajuster au cadre</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-indigo-700 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    <span>Remplacer l'image</span>
                  </button>
                </>
              )}
            </div>
          )}
        </div>

        {/* Address Search in Geographic Mode */}
        {mode === 'geographic' && (
          <div className="pt-3 border-t border-gray-100 space-y-2">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleGeocode();
              }}
              className="flex items-center gap-2 max-w-xl"
            >
              <div className="relative flex-1">
                <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Rechercher une adresse (ex: Place de la République, Paris)..."
                  className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none"
                />
              </div>
              <button
                type="submit"
                disabled={isSearching}
                className="px-4 py-2 bg-gray-900 hover:bg-gray-800 text-white text-sm font-semibold rounded-lg transition flex items-center gap-2 disabled:opacity-50 flex-shrink-0"
              >
                {isSearching ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Recherche...</span>
                  </>
                ) : (
                  <span>Rechercher</span>
                )}
              </button>
            </form>

            {searchError && (
              <p className="text-xs text-amber-700 bg-amber-50 p-2 rounded-lg flex items-center gap-1.5">
                <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 text-amber-600" />
                <span>{searchError}</span>
              </p>
            )}
          </div>
        )}
      </div>

      {/* Hidden File Input for Planar Mode Upload */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
          }
          e.target.value = '';
        }}
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
      />

      {/* Calibration Viewport / Canvas */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden flex flex-col">
        {mode === 'planar' && !currentEvent.background_image_url ? (
          /* Planar Mode: Dropzone when no image is uploaded */
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`m-8 p-12 border-2 border-dashed rounded-2xl text-center transition flex flex-col items-center justify-center ${
              isDragging
                ? 'border-indigo-500 bg-indigo-50/50'
                : 'border-gray-300 bg-gray-50/50 hover:bg-gray-50'
            }`}
          >
            <div className="w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mb-4">
              {isUploading ? (
                <Loader2 className="w-8 h-8 animate-spin" />
              ) : (
                <Upload className="w-8 h-8" />
              )}
            </div>

            <h3 className="text-lg font-bold text-gray-900">
              {isUploading ? 'Téléversement du plan en cours...' : 'Téléverser le plan intérieur (PNG, JPEG, WebP)'}
            </h3>
            <p className="text-sm text-gray-500 max-w-md mt-1 mb-6">
              Glissez et déposez l'image de votre salle des fêtes, gymnase ou terrain couvert, ou sélectionnez-la sur votre appareil (10 Mo maximum).
            </p>

            {uploadError && (
              <div className="mb-4 text-xs font-semibold text-red-700 bg-red-50 border border-red-200 px-3 py-2 rounded-lg flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
                <span>{uploadError}</span>
              </div>
            )}

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-semibold rounded-lg shadow-sm transition disabled:opacity-50"
            >
              <FileImage className="w-4 h-4" />
              <span>Choisir une image sur mon disque</span>
            </button>
          </div>
        ) : (
          /* Map Viewport for Outdoor OSM or Indoor Leaflet L.CRS.Simple */
          <div className="relative">
            <div
              ref={mapContainerRef}
              className="w-full h-[580px] bg-slate-100 z-0"
              style={{ minHeight: '580px' }}
            />

            {/* Bottom Floating Info Bar */}
            <div className="absolute bottom-4 left-4 z-[400] bg-white/95 backdrop-blur-sm border border-gray-200/80 px-4 py-2.5 rounded-xl shadow-md text-xs text-gray-700 flex flex-wrap items-center gap-4">
              {mode === 'geographic' ? (
                <>
                  <div className="flex items-center gap-1.5 font-medium">
                    <MapPin className="w-3.5 h-3.5 text-emerald-600" />
                    <span>Centre :</span>
                    <code className="bg-gray-100 px-1.5 py-0.5 rounded font-mono text-gray-900">
                      {lat.toFixed(5)}, {lng.toFixed(5)}
                    </code>
                  </div>
                  <div className="flex items-center gap-1.5 font-medium">
                    <Layers className="w-3.5 h-3.5 text-gray-500" />
                    <span>Zoom :</span>
                    <code className="bg-gray-100 px-1.5 py-0.5 rounded font-mono text-gray-900">
                      {Math.round(zoom)}
                    </code>
                  </div>
                </>
              ) : (
                <>
                  <div className="flex items-center gap-1.5 font-medium">
                    <FileImage className="w-3.5 h-3.5 text-indigo-600" />
                    <span>Mode Planaire L.CRS.Simple</span>
                  </div>
                  {imageDimensions && (
                    <div className="flex items-center gap-1.5 font-medium">
                      <span>Dimensions :</span>
                      <code className="bg-gray-100 px-1.5 py-0.5 rounded font-mono text-gray-900">
                        {imageDimensions.width} &times; {imageDimensions.height} px
                      </code>
                    </div>
                  )}
                  {currentEvent.background_image_url && (
                    <div className="text-gray-400 truncate max-w-xs">
                      {currentEvent.background_image_url}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MapCalibration;

