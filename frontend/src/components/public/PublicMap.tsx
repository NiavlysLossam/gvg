import React, { useEffect, useRef, useState, useCallback } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { Crosshair, Layers } from 'lucide-react';
import { PublicEventResponse, PublicSpotFeature } from '../../types/public';
import { getImageUrl } from '../../lib/api';

interface PublicMapProps {
  event: PublicEventResponse;
  spots: PublicSpotFeature[];
  selectedSpot?: PublicSpotFeature | null;
  cartSpotIds?: Set<string>;
  onSpotSelect: (spot: PublicSpotFeature) => void;
  onMapError?: (error: string) => void;
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

export const PublicMap: React.FC<PublicMapProps> = ({
  event,
  spots,
  selectedSpot,
  cartSpotIds,
  onSpotSelect,
  onMapError,
}) => {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const spotsGroupRef = useRef<L.LayerGroup | null>(null);
  const spotLayersMapRef = useRef<Map<string, L.Polygon>>(new Map());
  const imageBoundsRef = useRef<L.LatLngBounds | null>(null);
  const initialFitDoneRef = useRef<string | null>(null);
  const [mapReady, setMapReady] = useState<boolean>(false);
  const [mapLoadError, setMapLoadError] = useState<string | null>(null);
  const [tileLayerType, setTileLayerType] = useState<'osm' | 'satellite'>('osm');
  const tileLayerRef = useRef<L.TileLayer | null>(null);

  // Recenter / fitBounds handler
  const handleRecenter = useCallback(() => {
    const map = mapInstanceRef.current;
    if (!map) return;

    if (spots.length > 0) {
      try {
        const tempLayer = L.geoJSON(spots as any);
        const bounds = tempLayer.getBounds();
        if (bounds.isValid()) {
          const maxZoom = event.map_type === 'planar' ? 4 : 19;
          map.fitBounds(bounds.pad(0.15), {
            animate: true,
            duration: 0.8,
            maxZoom: maxZoom,
          });
          return;
        }
      } catch {
        // Fallback to default bounds below
      }
    }

    // Default fallback if 0 spots or bounds not calculated
    if (event.map_type === 'geographic') {
      const lat = event.center_latitude ?? 46.603354;
      const lng = event.center_longitude ?? 1.888334;
      const zoom = event.default_zoom ?? 16;
      map.setView([lat, lng], zoom, { animate: true });
    } else {
      if (imageBoundsRef.current) {
        map.fitBounds(imageBoundsRef.current, { animate: true });
      } else {
        map.setZoom(0, { animate: true });
      }
    }
  }, [spots, event]);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Planar mode without image yet
    if (event.map_type === 'planar' && !event.background_image_url) {
      return;
    }

    // Cleanup previous map instance
    if (mapInstanceRef.current) {
      mapInstanceRef.current.remove();
      mapInstanceRef.current = null;
    }

    let isMounted = true;

    if (event.map_type === 'geographic') {
      // 1. Geographic mode setup (EPSG:3857)
      const lat = event.center_latitude ?? 46.603354;
      const lng = event.center_longitude ?? 1.888334;
      const zoom = event.default_zoom ?? 16;

      const map = L.map(mapContainerRef.current, {
        center: [lat, lng],
        zoom: zoom,
        maxZoom: 22,
        zoomControl: false, // Custom position or disabled for cleaner mobile view
        tapHold: true,
        touchZoom: true,
        dragging: true,
      });

      // Add zoom control top-left
      L.control.zoom({ position: 'topleft' }).addTo(map);

      const osmUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
      const osmAttr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
      const satUrl =
        'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
      const satAttr =
        'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP';

      const initialUrl = tileLayerType === 'satellite' ? satUrl : osmUrl;
      const initialAttr = tileLayerType === 'satellite' ? satAttr : osmAttr;

      const tileLayer = L.tileLayer(initialUrl, {
        maxZoom: 22,
        maxNativeZoom: 19,
        attribution: initialAttr,
      }).addTo(map);
      tileLayerRef.current = tileLayer;

      const spotsGroup = L.layerGroup().addTo(map);
      spotsGroupRef.current = spotsGroup;
      mapInstanceRef.current = map;
      setMapReady(true);

      setTimeout(() => {
        if (isMounted && mapInstanceRef.current) {
          mapInstanceRef.current.invalidateSize();
        }
      }, 100);
    } else {
      // 2. Planar mode setup (L.CRS.Simple for indoor floorplans)
      const imageUrl = getImageUrl(event.background_image_url);
      const img = new Image();
      img.src = imageUrl;

      img.onerror = () => {
        if (!isMounted) return;
        const msg = "Impossible de charger l'image du fond de plan.";
        setMapLoadError(msg);
        onMapError?.(msg);
      };

      img.onload = () => {
        if (!isMounted || !mapContainerRef.current) return;

        const w = img.naturalWidth;
        const h = img.naturalHeight;

        const map = L.map(mapContainerRef.current, {
          crs: L.CRS.Simple,
          minZoom: -2,
          maxZoom: 6,
          zoomSnap: 0.25,
          zoomDelta: 0.5,
          zoomControl: false,
          tapHold: true,
          touchZoom: true,
          dragging: true,
        });

        L.control.zoom({ position: 'topleft' }).addTo(map);

        const bounds = new L.LatLngBounds([0, 0], [h, w]);
        imageBoundsRef.current = bounds;
        L.imageOverlay(imageUrl, bounds).addTo(map);

        map.fitBounds(bounds);
        map.setMaxBounds(bounds.pad(0.25));

        const spotsGroup = L.layerGroup().addTo(map);
        spotsGroupRef.current = spotsGroup;
        mapInstanceRef.current = map;
        setMapReady(true);

        setTimeout(() => {
          if (isMounted && mapInstanceRef.current) {
            mapInstanceRef.current.invalidateSize();
          }
        }, 100);
      };
    }

    return () => {
      isMounted = false;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [event.map_type, event.background_image_url]);

  // Switch tile layer in geographic mode
  useEffect(() => {
    if (event.map_type !== 'geographic' || !mapInstanceRef.current) return;

    const osmUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
    const osmAttr = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
    const satUrl =
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
    const satAttr =
      'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP';

    if (tileLayerRef.current) {
      mapInstanceRef.current.removeLayer(tileLayerRef.current);
    }

    const newUrl = tileLayerType === 'satellite' ? satUrl : osmUrl;
    const newAttr = tileLayerType === 'satellite' ? satAttr : osmAttr;

    const newLayer = L.tileLayer(newUrl, {
      maxZoom: 22,
      maxNativeZoom: 19,
      attribution: newAttr,
    }).addTo(mapInstanceRef.current);

    tileLayerRef.current = newLayer;
  }, [tileLayerType, event.map_type]);

  // Render stalls on map
  useEffect(() => {
    const map = mapInstanceRef.current;
    const group = spotsGroupRef.current;
    if (!map || !group || !mapReady) return;

    group.clearLayers();
    spotLayersMapRef.current.clear();

    // Semantic palette from Sally's DESIGN.md & spec
    const statusStyles = {
      available: {
        fillColor: '#10B981',
        fillOpacity: 0.65,
        color: '#059669',
        weight: 2,
        dashArray: undefined,
      },
      locked: {
        fillColor: '#F59E0B',
        fillOpacity: 0.65,
        color: '#D97706',
        weight: 2,
        dashArray: undefined,
      },
      reserved: {
        fillColor: '#9CA3AF',
        fillOpacity: 0.4,
        color: '#6B7280',
        weight: 1.5,
        dashArray: '4, 4',
      },
      blocked: {
        fillColor: '#E5E7EB',
        fillOpacity: 0.3,
        color: '#9CA3AF',
        weight: 1,
        dashArray: undefined,
      },
    };

    spots.forEach((spot) => {
      const isInCart = cartSpotIds?.has(spot.id) ?? false;
      const isSelected = selectedSpot?.id === spot.id;
      const baseStyle = statusStyles[spot.properties.status] || statusStyles.available;

      let style: L.PathOptions;
      if (isInCart) {
        // Cobalt Blue per DESIGN.md & spec: '#2563EB', fill '#3B82F6', border '#1D4ED8' 2.5px
        style = {
          fillColor: '#3B82F6',
          fillOpacity: 0.85,
          color: '#1D4ED8',
          weight: 2.5,
          dashArray: undefined,
        };
      } else if (isSelected) {
        // Keep status fillColor for inspected spot, only highlight border
        style = {
          ...baseStyle,
          weight: 3.5,
          color: '#1F2937',
        };
      } else {
        style = baseStyle;
      }

      const geoLayer = L.geoJSON(spot, {
        style,
      });

      geoLayer.eachLayer((layer) => {
        const poly = layer as L.Polygon;
        spotLayersMapRef.current.set(spot.id, poly);

        // Tooltip showing label & details
        const escapedLabel = escapeHtml(spot.properties.label);
        const priceFormatted = `${spot.properties.price.toFixed(2).replace('.', ',')} €`;
        const cartBadge = isInCart
          ? `<div class="mt-0.5"><span class="inline-block px-1 py-0.5 bg-blue-600 text-white text-[9px] font-bold rounded">Mon panier</span></div>`
          : '';
        const offlineBadge =
          spot.properties.status === 'reserved' && spot.properties.is_offline
            ? `<div class="mt-0.5"><span class="inline-block px-1 py-0.5 bg-indigo-100 text-indigo-800 text-[9px] font-bold rounded border border-indigo-200">Hors-ligne</span></div>`
            : '';

        poly.bindTooltip(
          `<div class="text-center font-bold leading-tight select-none pointer-events-none">
            <div class="text-xs text-gray-900">${escapedLabel}</div>
            <div class="text-[10px] text-gray-700 font-medium">${spot.properties.linear_meters}m • ${priceFormatted}</div>
            ${cartBadge}
            ${offlineBadge}
          </div>`,
          {
            permanent: true,
            direction: 'center',
            className: 'spot-label-tooltip',
          }
        );

        // Tap/click handler
        poly.on('click', (e: L.LeafletMouseEvent) => {
          L.DomEvent.stopPropagation(e);
          onSpotSelect(spot);
        });

        // Accessibility attributes on the SVG element
        try {
          const el = (poly as any)._path as SVGElement | undefined;
          if (el) {
            const statusFr = isInCart
              ? 'sélectionné dans mon panier'
              : spot.properties.status === 'available'
              ? 'disponible'
              : spot.properties.status === 'locked'
              ? 'en cours de réservation'
              : 'déjà réservé';
            el.setAttribute(
              'aria-label',
              `Emplacement ${spot.properties.label}, ${spot.properties.linear_meters} mètres, ${statusFr}`
            );
            el.setAttribute('role', 'button');
            el.setAttribute('tabindex', '0');
          }
        } catch {
          // ignore
        }
      });

      group.addLayer(geoLayer);
    });

    // Auto-fit on initial spots load if map has not been framed yet for this event
    if (spots.length > 0 && initialFitDoneRef.current !== event.id) {
      initialFitDoneRef.current = event.id;
      handleRecenter();
    }
  }, [spots, selectedSpot, cartSpotIds, mapReady, onSpotSelect, handleRecenter, event.id]);

  return (
    <div className="relative w-full h-full min-h-[480px] sm:min-h-[600px] bg-[#F0FDF4] overflow-hidden select-none">
      {/* Map Container */}
      <div ref={mapContainerRef} className="w-full h-full z-10" />

      {/* Map Load Error Overlay */}
      {mapLoadError && (
        <div className="absolute inset-0 z-30 flex items-center justify-center p-4 bg-gray-50/90 backdrop-blur-2xs">
          <div className="bg-white rounded-2xl p-6 max-w-sm text-center shadow-lg border border-red-200">
            <p className="text-sm font-semibold text-red-700">{mapLoadError}</p>
          </div>
        </div>
      )}

      {/* Floating Recenter Button */}
      <div className="absolute bottom-6 right-4 z-30 flex flex-col items-end gap-2">
        {event.map_type === 'geographic' && (
          <button
            onClick={() =>
              setTileLayerType((prev) => (prev === 'osm' ? 'satellite' : 'osm'))
            }
            className="bg-white/95 text-gray-700 hover:text-gray-900 shadow-md rounded-full p-3 hover:bg-white active:scale-95 transition flex items-center justify-center border border-gray-200"
            title={
              tileLayerType === 'osm'
                ? 'Basculer vers la vue satellite'
                : 'Basculer vers la vue plan'
            }
            aria-label="Basculer le type de carte"
          >
            <Layers className="w-5 h-5 text-emerald-700" />
          </button>
        )}

        <button
          onClick={handleRecenter}
          className="bg-white text-gray-700 shadow-md rounded-full p-3 hover:bg-gray-50 active:scale-95 transition flex items-center justify-center border border-gray-200 group"
          title="Recentrer la vue sur l'ensemble des stands"
          aria-label="Recentrer la vue sur le vide-grenier"
        >
          <Crosshair className="w-5 h-5 text-emerald-700 group-hover:rotate-45 transition-transform duration-200" />
        </button>
      </div>
    </div>
  );
};

